"""Source-only semantic interpretation, independent of the draft's field labels.

No source vocabulary, sample value, vendor or actor label is parsed in Python.
The model supplies evidence-backed meaning; Python preserves values, separates
physical occurrences and records every change for review.
"""

import json
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.cloudflare import CloudflareClient, ProviderError
from app.core.config import get_settings
from app.features.extraction.normalization import ground, unique_source_span
from app.features.extraction.quality import block_matches
from app.features.extraction.schemas import Observation
from app.features.extraction.service import load_prompt, parse_json
from app.features.extraction.vision import page_views

SEMANTIC_VERSION = "extraction-v6-physical-occurrence-contracts"


class SemanticFact(Observation):
    meaning: Literal[
        "actor_name", "actor_role", "actor_status", "term_text", "term_number", "term_date"
    ]

    @model_validator(mode="after")
    def meaning_contract(self):
        if not self.group_key:
            raise ValueError("Semantic facts need their source actor/term record group")
        expected_types = {
            "actor_name": "text",
            "actor_role": "text",
            "actor_status": "text",
            "term_text": "text",
            "term_number": "number",
            "term_date": "date",
        }
        if self.value_type != expected_types[self.meaning]:
            raise ValueError("Semantic meaning and value_type disagree")
        suffixes = {
            "actor_name": (".name",),
            "actor_role": (".role", ".department"),
            "actor_status": (".status",),
        }
        if self.meaning in suffixes and not self.field_key.endswith(suffixes[self.meaning]):
            raise ValueError("Actor fields must identify name, role/department or status")
        if self.meaning == "term_number" and not self.unit:
            raise ValueError("Source numeric terms require an explicit unit")
        return self


class SemanticInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[SemanticFact] = Field(max_length=80)
    reviewed_page_ids: list[str]
    unresolved_checks: list[str]


def parse_semantic_inventory(payload: dict) -> tuple[SemanticInventory, list[dict]]:
    """Ignore typed standalone identifier/money proposals outside this review's scope.

    Extraction retains those facts. This stage interprets actors and embedded
    terms only; all in-scope proposals still undergo full schema/source checks.
    """
    if not isinstance(payload.get("facts"), list):
        return SemanticInventory.model_validate(payload), []
    outside = [
        fact
        for fact in payload["facts"]
        if isinstance(fact, dict) and fact.get("value_type") in {"identifier", "money"}
    ]
    retained = [fact for fact in payload["facts"] if fact not in outside]
    return SemanticInventory.model_validate({**payload, "facts": retained}), outside


def same_occurrence(left: dict, right: dict, pages: list[dict]) -> bool:
    if left["raw_value"] != right["raw_value"] or left["page_id"] != right["page_id"]:
        return False
    page = next(page for page in pages if page["page_id"] == left["page_id"])
    if page["input_method"] == "vision":
        return left["quote"] == right["quote"]
    return any(
        block_matches(left, page, block) and block_matches(right, page, block)
        for block in page["blocks"]
    )


def physical_value_span(observation: dict, pages: list[dict]) -> list[str] | None:
    """Locate the unique value inside its grounded quote, ignoring draft group labels."""
    page = next(page for page in pages if page["page_id"] == observation["page_id"])
    if page["input_method"] != "native_text":
        return None
    blocks = [b for b in page["blocks"] if b["block_id"] in observation["block_ids"]]
    quote_span = unique_source_span(observation["quote"], blocks)
    if not quote_span:
        return None
    return unique_source_span(
        observation["raw_value"], [b for b in blocks if b["block_id"] in quote_span]
    )


def reconcile_semantics(
    extraction: dict, inventory: SemanticInventory, pages: list[dict], document_id: str
) -> dict:
    expected = {page["page_id"] for page in pages}
    if set(inventory.reviewed_page_ids) != expected or len(inventory.reviewed_page_ids) != len(
        expected
    ):
        raise ValueError("Source semantic inventory must cover every supplied page exactly once")
    facts = (
        ground(
            {
                "observations": [fact.model_dump(exclude={"meaning"}) for fact in inventory.facts],
                "page_coverage": inventory.reviewed_page_ids,
                "uncertainties": inventory.unresolved_checks,
            },
            pages,
            document_id,
        )["observations"]
        if inventory.facts
        else []
    )
    result = deepcopy(extraction)
    changes = []
    visited = set()
    for fact_index, fact in enumerate(facts):
        meaning = inventory.facts[fact_index].meaning
        item_occurrences = [
            obs
            for obs in extraction["observations"]
            if obs["field_key"].startswith("item.") and same_occurrence(obs, fact, pages)
        ]
        if item_occurrences:
            raise ValueError(
                "Semantic scope excludes grounded item row cells; do not repeat or rename them"
            )
        # Compare meaning at the same physical occurrence, never by equal value alone.
        matches = [
            index
            for index, obs in enumerate(result["observations"])
            if same_occurrence(obs, fact, pages)
        ]
        exact = [
            index
            for index in matches
            if result["observations"][index]["field_key"] == fact["field_key"]
        ]
        # Actor interpretation may correct an actor label, never an identifier,
        # table cell or standalone financial field. Terms preserve original facts.
        actor_matches = [
            index for index in matches if result["observations"][index]["value_type"] == "text"
        ]
        candidates = (
            (exact or actor_matches)
            if meaning.startswith("actor_")
            else [
                index
                for index in exact
                if result["observations"][index]["value_type"] == fact["value_type"]
            ]
        )
        if len(candidates) > 1:
            duplicates = [result["observations"][index] for index in candidates]
            span = physical_value_span(fact, pages)
            if span and all(physical_value_span(obs, pages) == span for obs in duplicates):
                if any(index in visited for index in candidates):
                    result["observations"].append(deepcopy(fact))
                    continue
                # Alternative draft labels on the identical physical value are
                # not distinct actors. Correct each label from independent source
                # meaning while retaining every original occurrence and its trace.
                for index in candidates:
                    original = result["observations"][index]
                    fields = ("field_key", "value_type", "unit", "role", "group_key")
                    changes.append(
                        {
                            "source_fact": fact_index + 1,
                            "page_id": fact["page_id"],
                            "before": {key: original.get(key) for key in fields},
                            "after": {key: fact.get(key) for key in fields},
                            "basis": "identical_source_occurrence",
                        }
                    )
                    result["observations"][index] = deepcopy(fact)
                    visited.add(index)
                continue
        if len(candidates) > 1:
            result["uncertainties"].append(
                f"Vai trò nguồn có nhiều ứng viên ({fact['page_id']}, {fact['field_key']})"
            )
            continue
        if candidates:
            index = candidates[0]
            if index in visited:
                # One occurrence can have different legitimate meanings; preserve them.
                result["observations"].append(fact)
            else:
                original = result["observations"][index]
                fields = ("field_key", "value_type", "unit", "role", "group_key")
                before = {key: original.get(key) for key in fields}
                after = {key: fact.get(key) for key in fields}
                if before != after:
                    changes.append(
                        {
                            "source_fact": fact_index + 1,
                            "page_id": fact["page_id"],
                            "before": before,
                            "after": after,
                        }
                    )
                # Prefer the independently interpreted, fully labelled source span.
                result["observations"][index] = fact
                visited.add(index)
        else:
            result["observations"].append(fact)
            changes.append(
                {
                    "source_fact": fact_index + 1,
                    "page_id": fact["page_id"],
                    "added_field": fact["field_key"],
                }
            )
    result["uncertainties"] = list(
        dict.fromkeys(result["uncertainties"] + inventory.unresolved_checks)
    )
    result = ground(result, pages, document_id)
    result["schema_version"] = SEMANTIC_VERSION
    result["semantic_review"] = {
        "basis": "source_only_model_interpretation",
        "reviewed_page_ids": inventory.reviewed_page_ids,
        "facts": [fact.model_dump() for fact in inventory.facts],
        "changes": changes,
    }
    return result


async def review_source_semantics(
    client: CloudflareClient,
    audit_id: str,
    document_id: str,
    extraction: dict,
    pages: list[dict],
    image_paths: dict[str, str],
) -> dict:
    page_aliases = {page["page_id"]: f"p{index + 1}" for index, page in enumerate(pages)}
    block_aliases = {
        block["block_id"]: f"{page_aliases[page['page_id']]}b{index + 1}"
        for page in pages
        for index, block in enumerate(page["blocks"])
    }
    reverse_pages = {alias: original for original, alias in page_aliases.items()}
    reverse_blocks = {alias: original for original, alias in block_aliases.items()}
    source = [
        {
            "page_id": page_aliases[page["page_id"]],
            "input_method": page["input_method"],
            "blocks": [
                {"block_id": block_aliases[block["block_id"]], "text": block["text"]}
                for block in page["blocks"]
            ],
        }
        for page in pages
    ]
    content = [
        {
            "type": "text",
            "text": json.dumps(
                {"pages": source, "output_schema": SemanticInventory.model_json_schema()},
                ensure_ascii=False,
            ),
        }
    ]
    visual = [page for page in pages if page["input_method"] == "vision"]
    for page in visual:
        content.extend(page_views(page_aliases[page["page_id"]], image_paths[page["page_id"]]))
    settings = get_settings()
    # Meaning is a reasoning task, not a second OCR/extraction pass.
    model = settings.cloudflare_vision_model if visual else settings.cloudflare_internal_model
    messages = [
        {"role": "system", "content": load_prompt("semantics")},
        {"role": "user", "content": content if visual else content[0]["text"]},
    ]
    for attempt in range(2):
        response = None
        try:
            response = await client.complete(
                audit_id,
                "extraction_semantics" if not attempt else "extraction_semantics_repair",
                model,
                messages,
                max_tokens=4500,
                schema=None,
            )
            inventory, outside = parse_semantic_inventory(parse_json(response.get("content")))
            inventory.reviewed_page_ids = [
                reverse_pages[ref] for ref in inventory.reviewed_page_ids
            ]
            for fact in inventory.facts:
                fact.page_id = reverse_pages[fact.page_id]
                fact.block_ids = [reverse_blocks[ref] for ref in fact.block_ids]
            result = reconcile_semantics(extraction, inventory, pages, document_id)
            result["semantic_review"]["rejected_out_of_scope_facts"] = outside
            return result
        except (ValueError, KeyError, ProviderError) as exc:
            if isinstance(exc, ProviderError) and exc.code != "truncated_output":
                raise
            if attempt:
                failure = ValueError("Source semantic interpretation could not be validated")
                failure.partial_response = response or getattr(exc, "partial_response", None)
                raise failure from None
            partial = response or getattr(exc, "partial_response", None) or {}
            messages.extend(
                [
                    {
                        "role": "assistant",
                        "content": (partial.get("content") or "").rstrip()[:24000],
                    },
                    {
                        "role": "user",
                        "content": load_prompt("repair")
                        + "\nSource semantic contract failed: "
                        + str(exc)[:2000]
                        + "\nReturn only actor relationships and embedded terms, all required fields in compact JSON, exact supplied page/block IDs and verbatim source quotes. Drop standalone/table cells outside this scope. Do not infer facts.",
                    },
                ]
            )
    raise ValueError("No source semantic result")
