import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation


def compact(text: str) -> str:
    return "".join(unicodedata.normalize("NFC", text).split()).casefold()


def unique_source_span(quote: str, blocks: list[dict]) -> list[str] | None:
    """Resolve a verbatim quote to a unique minimal contiguous native-text span.

    Repeated occurrences stay ambiguous. This retrieves source locations only;
    it never changes the quoted value, page or business interpretation.
    """
    needle = compact(quote)
    if not needle:
        return None
    if "".join(compact(block["text"]) for block in blocks).count(needle) != 1:
        return None
    spans = []
    for start in range(len(blocks)):
        joined = ""
        for end in range(start, len(blocks)):
            joined += compact(blocks[end]["text"])
            if needle in joined:
                spans.append((start, end))
                break
    minimal = [
        span
        for span in spans
        if not any(span[0] <= other[0] <= other[1] <= span[1] and other != span for other in spans)
    ]
    if len(minimal) != 1:
        return None
    start, end = minimal[0]
    return [block["block_id"] for block in blocks[start : end + 1]]


def inferred_unit(observation: dict) -> str | None:
    if observation.get("unit"):
        return observation["unit"]
    if observation.get("value_type") == "number" and observation.get("raw_value") is not None:
        if "%" in observation["raw_value"] or re.search(
            re.escape(observation["raw_value"]) + r"\s*%", observation.get("quote", "")
        ):
            return "%"
    return None


def normalize(raw: str | None, value_type: str) -> str | None:
    """Keep identifiers verbatim; return None rather than guessing ambiguous separators."""
    if raw is None:
        return None
    value = raw.strip()
    if value_type in {"identifier", "text"}:
        return value
    if value_type == "date":
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return None
    number = re.sub(r"\s*(VND|USD|EUR|₫|đ|%)\s*", "", value, flags=re.I).replace(" ", "")
    if re.fullmatch(r"[+-]?\d{1,3}([,.]\d{3})+", number):
        number = number.replace(",", "").replace(".", "")
    elif re.fullmatch(r"[+-]?\d+\.\d{1,2}", number):
        pass
    elif not re.fullmatch(r"[+-]?\d+", number):
        return None
    try:
        parsed = Decimal(number)
        return format(parsed, "f") if parsed.is_finite() else None
    except InvalidOperation:
        return None


def ground(
    extraction: dict, pages: list[dict], document_id: str, *, narrow_citations: bool = False
) -> dict:
    page_map = {p["page_id"]: p for p in pages}
    expected = set(page_map)
    if set(extraction["page_coverage"]) != expected:
        raise ValueError("Model response did not cover exactly the supplied pages")
    observations = []
    uncertainties = list(extraction["uncertainties"])
    for index, source in enumerate(extraction["observations"]):
        obs = dict(source)
        page = page_map.get(obs["page_id"])
        if page is None:
            raise ValueError("Observation references an unknown page")
        block_map = {b["block_id"]: b for b in page["blocks"]}
        if any(b not in block_map for b in obs["block_ids"]):
            raise ValueError("Observation references an unknown source block")
        quote = obs["quote"]
        if obs["raw_value"] is not None and (
            not quote or compact(obs["raw_value"]) not in compact(quote)
        ):
            raise ValueError(
                f"Observation #{index + 1} ({obs['field_key']}): raw_value must occur verbatim in quote, including number separators. Do not normalize raw_value or append a currency absent from the quoted span."
            )
        if page["input_method"] == "native_text":
            source_text = " ".join(b["text"] for b in page["blocks"])
            if quote and compact(quote) not in compact(source_text):
                candidates = [
                    b["block_id"]
                    for b in page["blocks"]
                    if obs["raw_value"] and compact(obs["raw_value"]) in compact(b["text"])
                ]
                raise ValueError(
                    f"Observation #{index + 1} ({obs['field_key']}): quote not found in source page text. "
                    f"Blocks containing the raw value: {candidates}. Copy an exact contiguous "
                    "source span; never join a header/heading with a nonadjacent row. "
                    "Candidate blocks locate the value only, not its business role."
                )
            resolved = unique_source_span(quote, page["blocks"]) if narrow_citations else None
            if resolved is not None and obs["block_ids"] != resolved:
                obs["citation_resolution"] = {
                    "original_block_ids": list(obs["block_ids"]),
                    "method": "unique_verbatim_source_span",
                }
                obs["block_ids"] = resolved
            if obs["block_ids"] and compact(quote) not in compact(
                " ".join(block_map[b]["text"] for b in obs["block_ids"])
            ):
                resolved = unique_source_span(quote, page["blocks"])
                if resolved is None:
                    raise ValueError(
                        "Observation quote not found in cited blocks; no unique exact source span"
                    )
                obs["citation_resolution"] = {
                    "original_block_ids": list(obs["block_ids"]),
                    "method": "unique_verbatim_source_span",
                }
                obs["block_ids"] = resolved
            obs["grounding"] = "text_verified" if quote else "unreadable"
        else:
            obs["grounding"] = "visual_unverified"
        obs["id"] = f"{document_id}:o{index + 1}"
        obs["document_id"] = document_id
        if (
            obs["value_type"] == "text"
            and obs["raw_value"] is not None
            and re.fullmatch(r"[+-]?\d+(?:\.\d{1,2})?\s*%", obs["raw_value"].strip())
        ):
            obs["extracted_value_type"] = "text"
            obs["value_type"], obs["unit"] = "number", "%"
        obs["normalized_value"] = normalize(obs["raw_value"], obs["value_type"])
        obs["unit"] = inferred_unit(obs)
        if obs["raw_value"] is None or obs["normalized_value"] is None:
            uncertainties.append(f"Không đọc/chuẩn hóa được {obs['field_key']} ({obs['page_id']})")
        observations.append(obs)
    if not any(o["normalized_value"] is not None for o in observations):
        uncertainties.append("Không có thông tin đọc được để kiểm tra chứng từ")
    currencies = [
        o
        for o in observations
        if o["field_key"] == "currency"
        and re.fullmatch(r"[A-Z]{3}", o.get("normalized_value") or "")
    ]
    if len({o["normalized_value"] for o in currencies}) == 1:
        for observation in observations:
            if observation["value_type"] == "money" and not observation.get("unit"):
                observation["unit"] = currencies[0]["normalized_value"]
                observation["unit_observation_ids"] = [o["id"] for o in currencies]
    return {
        **extraction,
        "observations": observations,
        "uncertainties": list(dict.fromkeys(uncertainties)),
    }
