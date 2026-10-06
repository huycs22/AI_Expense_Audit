import hashlib
import json
from pathlib import Path

from app.core.cloudflare import CloudflareClient, ProviderError
from app.core.config import get_settings
from app.features.extraction.normalization import ground
from app.features.extraction.quality import (
    QualityReview,
    apply_review,
    grounded_additions,
    missing_identifier_occurrences,
    validate_coverage,
)
from app.features.extraction.schemas import Extraction, Observation
from app.features.extraction.vision import page_views

PROMPT_DIR = Path(__file__).with_name("prompts")


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def extraction_prompt(pages: list[dict]) -> str:
    return (
        load_prompt("extract")
        + "\n"
        + load_prompt("quality")
        + (
            "\n" + load_prompt("vision")
            if any(p["input_method"] == "vision" for p in pages)
            else ""
        )
    )


def parse_json(content: str | None) -> dict:
    if not content:
        raise ValueError("Empty model response")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0]
    result = json.loads(stripped)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


async def extract_document(
    client: CloudflareClient,
    audit_id: str,
    document_id: str,
    pages: list[dict],
    image_paths: dict[str, str],
    on_source_read=None,
) -> dict:
    settings = get_settings()
    prompt = load_prompt("extract") + (
        "\n" + load_prompt("vision") if any(p["input_method"] == "vision" for p in pages) else ""
    )
    page_ids = {page["page_id"]: f"p{i + 1}" for i, page in enumerate(pages)}
    block_ids = {
        block["block_id"]: f"{page_ids[page['page_id']]}b{i + 1}"
        for page in pages
        for i, block in enumerate(page["blocks"])
    }
    reverse_pages = {alias: original for original, alias in page_ids.items()}
    reverse_blocks = {alias: original for original, alias in block_ids.items()}
    # Measured geometry/table candidates remain stored; the model sees uncluttered evidence.
    compact_pages = [
        {
            "page_id": page_ids[p["page_id"]],
            "input_method": p["input_method"],
            "blocks": [
                {"block_id": block_ids[b["block_id"]], "text": b["text"]} for b in p["blocks"]
            ],
            "tables": p.get("table_candidates", []),
        }
        for p in pages
    ]
    payload = {
        "allowed_page_ids": list(reverse_pages),
        "pages": compact_pages,
        "output_schema": Extraction.model_json_schema(),
    }
    vision_pages = [p for p in pages if p["input_method"] == "vision"]
    # Mixed documents use a single vision-capable request with native evidence plus images.
    model = settings.cloudflare_vision_model if vision_pages else settings.cloudflare_model
    content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    for page in vision_pages:
        content.extend(page_views(page_ids[page["page_id"]], image_paths[page["page_id"]]))
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content if vision_pages else content[0]["text"]},
    ]
    for attempt in range(2):
        try:
            response = await client.complete(
                audit_id,
                "extraction" if not attempt else "extraction_repair",
                model,
                messages,
                schema=None,
            )
        except ProviderError as exc:
            if attempt or exc.code != "truncated_output":
                raise
            # A runaway prefix is not a draft: copying it back encourages continuation
            # of the same citation/date loop and spends the repair budget on that loop.
            messages.append(
                {
                    "role": "user",
                    "content": load_prompt("read_repair")
                    + "\nThe previous extraction exceeded the output limit and was discarded. "
                    "Regenerate a complete compact extraction from the original source; "
                    "do not continue a partial response. Cite only the minimal contiguous "
                    "blocks containing each exact quote, never all subsequent/page blocks. "
                    "Emit each physical field occurrence once; separate real repeated "
                    "occurrences by their source location. Preserve every page, item cell, "
                    "approval row and uncertainty. Do not shorten output by omitting facts.",
                }
            )
            continue
        try:
            extraction = Extraction.model_validate(parse_json(response.get("content"))).model_dump()
            for obs in extraction["observations"]:
                if obs["page_id"] not in reverse_pages or any(
                    b not in reverse_blocks for b in obs["block_ids"]
                ):
                    raise ValueError(
                        "Use supplied page/block IDs only: " + json.dumps(list(reverse_pages))
                    )
                obs["page_id"] = reverse_pages[obs["page_id"]]
                obs["block_ids"] = [reverse_blocks[b] for b in obs["block_ids"]]
            if set(extraction["page_coverage"]) != set(reverse_pages):
                raise ValueError(
                    f"page_coverage must equal {list(reverse_pages)}, got {extraction['page_coverage']}"
                )
            extraction["page_coverage"] = [reverse_pages[p] for p in extraction["page_coverage"]]
            grounded = ground(extraction, pages, document_id, narrow_citations=True)
            break
        except ValueError as exc:
            if attempt:
                failure = ValueError(f"Extraction validation failed: {str(exc)[:300]}")
                failure.partial_response = response
                raise failure from None
            # Regenerate from source rather than anchoring to an invalid, often
            # repetitive draft. Valid completed stages remain independently grounded.
            message = str(exc)
            for original, alias in sorted(
                {**page_ids, **block_ids}.items(), key=lambda item: -len(item[0])
            ):
                message = message.replace(original, alias)
            messages.append(
                {
                    "role": "user",
                    "content": load_prompt("read_repair") + "\nValidation error: " + message[:2000],
                }
            )
    if on_source_read is not None:
        on_source_read(grounded)
    # Independently compare the draft with the original source. Review changes
    # meaning/coverage, while Python preserves values and checks source references.
    draft = {
        **{key: grounded[key] for key in Extraction.model_fields if key != "observations"},
        "page_coverage": [page_ids[ref] for ref in grounded["page_coverage"]],
        "observations": [
            {
                **{key: observation.get(key) for key in Observation.model_fields},
                "page_id": page_ids[observation["page_id"]],
                "block_ids": [block_ids[ref] for ref in observation["block_ids"]],
            }
            for observation in grounded["observations"]
        ],
    }
    missing = missing_identifier_occurrences(grounded, pages)
    review_content = [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "output_schema": QualityReview.model_json_schema(),
                    "pages": compact_pages,
                    "draft": {
                        **draft,
                        "observations": [
                            {"id": f"o{index + 1}", **observation}
                            for index, observation in enumerate(draft["observations"])
                        ],
                    },
                    "missing_identifier_occurrences": [
                        {
                            **item,
                            "page_id": page_ids[item["page_id"]],
                            "block_id": block_ids[item["block_id"]],
                        }
                        for item in missing
                    ],
                },
                ensure_ascii=False,
            ),
        }
    ]
    for page in vision_pages:
        review_content.extend(page_views(page_ids[page["page_id"]], image_paths[page["page_id"]]))
    review_messages = [
        {"role": "system", "content": load_prompt("quality")},
        {"role": "user", "content": review_content if vision_pages else review_content[0]["text"]},
    ]
    for attempt in range(2):
        try:
            review_response = await client.complete(
                audit_id,
                "extraction_quality" if not attempt else "extraction_quality_repair",
                model,
                review_messages,
                max_tokens=4500,
                schema=None,
            )
        except ProviderError as exc:
            if attempt or exc.code != "truncated_output":
                raise
            review_messages.extend(
                [
                    {
                        "role": "assistant",
                        "content": ((exc.partial_response or {}).get("content") or "").rstrip()[
                            :24000
                        ],
                    },
                    {
                        "role": "user",
                        "content": load_prompt("repair")
                        + "\nPrevious review was truncated. Return complete compact JSON with every required field. Include only changed observations, never copy unchanged ones.",
                    },
                ]
            )
            continue
        try:
            review = QualityReview.model_validate(parse_json(review_response.get("content")))
            review, rejected_additions = grounded_additions(
                review, pages, document_id, reverse_pages, reverse_blocks
            )
            patched = apply_review(draft, review)
            for observation in patched["observations"]:
                observation["page_id"] = reverse_pages[observation["page_id"]]
                observation["block_ids"] = [reverse_blocks[ref] for ref in observation["block_ids"]]
            patched["page_coverage"] = [reverse_pages[ref] for ref in patched["page_coverage"]]
            restored_review = review.model_copy(
                update={
                    "reviewed_page_ids": [reverse_pages[ref] for ref in review.reviewed_page_ids],
                    "block_coverage": [
                        entry.model_copy(update={"block_id": reverse_blocks[entry.block_id]})
                        for entry in review.block_coverage
                    ],
                }
            )
            validated = ground(patched, pages, document_id, narrow_citations=True)
            validate_coverage(validated, restored_review, pages)
            gaps = missing_identifier_occurrences(validated, pages)
            if gaps:
                raise ValueError(
                    "Repeated identifier occurrences were omitted: "
                    + json.dumps(
                        [
                            {
                                "page_id": page_ids[gap["page_id"]],
                                "block_id": block_ids[gap["block_id"]],
                                "raw_value": gap["raw_value"],
                            }
                            for gap in gaps
                        ]
                    )
                    + ". Add each as a separate identifier observation with raw_value exactly "
                    + "equal to the supplied identifier, using the exact source block as quote. "
                    + "A terms/attachment sentence containing the identifier does not replace "
                    + "its scalar occurrence. Keep your other valid corrections/additions."
                )
            validated["uncertainties"] = list(
                dict.fromkeys(
                    validated["uncertainties"]
                    + [
                        f"Nội dung nguồn chưa đọc rõ ({entry.block_id}): {entry.reason}"
                        for entry in restored_review.block_coverage
                        if entry.disposition == "unreadable"
                    ]
                )
            )
            validated["schema_version"] = "extraction-v4-source-coverage"
            validated["quality"] = {
                "reviewed_page_ids": restored_review.reviewed_page_ids,
                "block_coverage": [entry.model_dump() for entry in restored_review.block_coverage],
                "correction_count": len(review.corrections),
                "addition_count": len(review.additions),
                "rejected_additions": rejected_additions,
                "citation_resolutions": [
                    {"observation_id": obs["id"], **obs["citation_resolution"]}
                    for obs in grounded["observations"] + validated["observations"]
                    if obs.get("citation_resolution")
                ],
                "visual_independently_verified": False,
            }
            return validated
        except (ValueError, KeyError) as exc:
            message = str(exc)
            for original, alias in {**page_ids, **block_ids}.items():
                message = message.replace(original, alias)
            if attempt:
                failure = ValueError(f"Extraction quality validation failed: {message[:300]}")
                failure.partial_response = review_response
                raise failure from None
            review_messages.extend(
                [
                    {"role": "assistant", "content": review_response.get("content") or ""},
                    {
                        "role": "user",
                        "content": load_prompt("repair") + "\nQuality errors: " + message[:2000],
                    },
                ]
            )
