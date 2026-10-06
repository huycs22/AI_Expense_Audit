"""Evidence coverage checks and source-preserving semantic review patches."""

import re
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.features.extraction.normalization import compact, ground
from app.features.extraction.schemas import Observation


class Correction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str
    replacement: Observation


class BlockCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str
    disposition: Literal["extracted", "context", "unreadable"]
    reason: str = Field(min_length=1)


class QualityReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    corrections: list[Correction] = Field(max_length=150)
    additions: list[Observation] = Field(max_length=200)
    block_coverage: list[BlockCoverage]
    reviewed_page_ids: list[str]
    unresolved_checks: list[str]


def grounded_additions(review, pages, document_id, reverse_pages, reverse_blocks):
    """Reject unsupported proposed extras independently; do not discard original facts.

    Full patched grounding, block coverage and identifier-occurrence validation
    still run afterward. A rejected proposal never establishes a source fact.
    """
    accepted, rejected = [], []
    for addition in review.additions:
        source = addition.model_dump()
        try:
            source["page_id"] = reverse_pages[source["page_id"]]
            source["block_ids"] = [reverse_blocks[ref] for ref in source["block_ids"]]
            ground(
                {
                    "observations": [source],
                    "page_coverage": [p["page_id"] for p in pages],
                    "uncertainties": [],
                },
                pages,
                document_id,
            )
        except (ValueError, KeyError) as exc:
            rejected.append({"proposal": addition.model_dump(), "reason": str(exc)})
        else:
            accepted.append(addition)
    return review.model_copy(update={"additions": accepted}), rejected


def apply_review(extraction: dict, review: QualityReview) -> dict:
    result = deepcopy(extraction)
    seen = set()
    for correction in review.corrections:
        ref = correction.observation_id
        if not re.fullmatch(r"o[1-9]\d*", ref) or ref in seen:
            raise ValueError("Review correction needs a unique supplied observation ID")
        index = int(ref[1:]) - 1
        if index >= len(result["observations"]):
            raise ValueError("Review correction cites an unknown observation")
        replacement = correction.replacement.model_dump()
        original = result["observations"][index]
        if (
            replacement["raw_value"] != original["raw_value"]
            or replacement["page_id"] != original["page_id"]
        ):
            raise ValueError(
                "A semantic correction must preserve original raw_value and source page"
            )
        result["observations"][index] = replacement
        seen.add(ref)
    result["observations"].extend(addition.model_dump() for addition in review.additions)
    result["uncertainties"] = list(
        dict.fromkeys(result["uncertainties"] + review.unresolved_checks)
    )
    return result


def block_matches(observation: dict, page: dict, block: dict) -> bool:
    if observation["page_id"] != page["page_id"]:
        return False
    quote = compact(observation.get("quote", ""))
    if not quote:
        return False
    citations = observation.get("block_ids", [])
    if citations and block["block_id"] not in citations:
        return False
    # A model cannot claim coverage merely by listing unrelated block IDs.
    # Locate the grounded contiguous quote in page text, including multi-line spans.
    texts = [compact(item["text"]) for item in page["blocks"]]
    index = next(
        i for i, item in enumerate(page["blocks"]) if item["block_id"] == block["block_id"]
    )
    start = sum(len(text) for text in texts[:index])
    end = start + len(texts[index])
    source = "".join(texts)
    position = source.find(quote)
    while position >= 0:
        if position < end and position + len(quote) > start:
            return True
        position = source.find(quote, position + 1)
    return False


def validate_coverage(extraction: dict, review: QualityReview, pages: list[dict]):
    expected_pages = {page["page_id"] for page in pages}
    if (
        len(review.reviewed_page_ids) != len(expected_pages)
        or set(review.reviewed_page_ids) != expected_pages
    ):
        raise ValueError("Semantic review must cover each supplied original page exactly once")
    native_blocks = {
        block["block_id"]: (page, block)
        for page in pages
        if page["input_method"] == "native_text"
        for block in page["blocks"]
    }
    if len(review.block_coverage) != len(native_blocks) or {
        item.block_id for item in review.block_coverage
    } != set(native_blocks):
        raise ValueError("Review must classify every native source block exactly once")
    errors = []
    for item in review.block_coverage:
        page, block = native_blocks[item.block_id]
        represented = any(
            block_matches(observation, page, block) for observation in extraction["observations"]
        )
        if item.disposition == "extracted" and not represented:
            errors.append(f"Block {item.block_id} claimed extracted but has no cited observation")
        if item.disposition == "context" and represented:
            errors.append(
                f"Block {item.block_id} contains extracted facts; classify it as extracted"
            )
    if errors:
        raise ValueError(
            "; ".join(errors)
            + ". Resolve every mismatch in one response. A standalone section/field label can "
            "be context when its associated facts are represented elsewhere; it does not need "
            "an invented value. An actual omitted fact requires a grounded addition. Never "
            "label a factual amount, identifier, date, party value or unit as context to hide it."
        )


def missing_identifier_occurrences(extraction: dict, pages: list[dict]) -> list[dict]:
    """Require a grounded observation on every page containing each known identifier.

    Repeated mentions in several blocks on the same page are not separate document
    identity facts. Repetition across pages is retained because each page is checked
    independently and needs its own grounded occurrence.
    """
    identifiers = {
        observation["raw_value"]
        for observation in extraction["observations"]
        if observation["value_type"] == "identifier" and observation.get("raw_value")
    }
    missing = []
    for page in pages:
        if page["input_method"] != "native_text":
            continue
        for value in sorted(identifiers):
            source_blocks = [
                block
                for block in page["blocks"]
                if re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", block["text"])
            ]
            if not source_blocks:
                continue
            observed_on_page = any(
                observation.get("raw_value") == value
                and any(block_matches(observation, page, block) for block in source_blocks)
                for observation in extraction["observations"]
            )
            if not observed_on_page:
                missing.append(
                    {
                        "page_id": page["page_id"],
                        "block_id": source_blocks[0]["block_id"],
                        "raw_value": value,
                    }
                )
    return missing
