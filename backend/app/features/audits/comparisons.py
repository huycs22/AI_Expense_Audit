"""Source-pair contracts shared by consolidated and legacy cross review."""

from pydantic import BaseModel, ConfigDict, Field


class IdentityComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1)
    observation_ids: list[str] = Field(min_length=2, max_length=2)


class IdentityPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparisons: list[IdentityComparison] = Field(max_length=24)
    unresolved_checks: list[str]


def validate_identity_plan(payload, observations, links):
    plan = IdentityPlan.model_validate(payload)
    registry = {o["id"]: o for o in observations}
    graph = {}
    for link in links:
        if link["status"] == "supported":
            a, b = link["from_document"], link["to_document"]
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
    seen = set()
    for comparison in plan.comparisons:
        refs = comparison.observation_ids
        if len(set(refs)) != 2 or not set(refs).issubset(registry):
            raise ValueError("Identity comparison requires two distinct registered source values")
        sources = [registry[ref] for ref in refs]
        if any(
            o["value_type"] not in {"text", "identifier"}
            or not o.get("raw_value")
            or not o.get("quote")
            for o in sources
        ):
            raise ValueError(
                "Qualitative comparisons accept only readable text/identifier observations; "
                "move dates/numbers/money to checks with source formulas. Invalid pair: "
                + repr(
                    [
                        {
                            key: o.get(key)
                            for key in ("id", "field_key", "value_type", "document_id")
                        }
                        for o in sources
                    ]
                )
                + "; eligible observation IDs: "
                + repr(
                    [
                        o["id"]
                        for o in observations
                        if o["value_type"] in {"text", "identifier"}
                        and o.get("raw_value")
                        and o.get("quote")
                    ]
                )
            )
        a, b = [o["document_id"] for o in sources]
        reached, pending = set(), [a]
        while pending:
            current = pending.pop()
            if current not in reached:
                reached.add(current)
                pending.extend(graph.get(current, set()) - reached)
        if a == b or b not in reached:
            raise ValueError("Identity comparisons require different, explicitly related documents")
        key = frozenset(refs)
        if key in seen:
            raise ValueError("Repeated identity comparison")
        seen.add(key)
    return plan
