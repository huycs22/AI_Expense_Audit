import json
from unittest.mock import AsyncMock

import pytest

from app.features.audits.reviewer import review


@pytest.mark.asyncio
@pytest.mark.parametrize("correction_succeeds", [True, False])
async def test_semantic_correction_is_bounded_and_preserves_source_identity(correction_succeeds):
    observations = [
        {
            "id": f"original:{i}",
            "document_id": "document",
            "field_key": "amount",
            "value_type": "money",
            "unit": "EUR",
            "raw_value": value,
            "normalized_value": value,
            "quote": value,
        }
        for i, value in enumerate(["91", "93", "17", "19"], 1)
    ]

    async def response(audit, stage, model, messages, **kwargs):
        corrected = stage.endswith("_refinement")
        refs = ["o3", "o4"] if corrected else ["o1", "o2"]
        if "plan" in stage:
            payload = {
                "checks": [
                    {
                        "id": "check",
                        "purpose": "Compare amounts",
                        "left": {"observation_id": refs[0]},
                        "right": {"observation_id": refs[1]},
                        "relation": "equals",
                    }
                ],
                "unresolved_checks": [],
            }
        elif "findings" in stage:
            payload = {
                "findings": [
                    {
                        "title": "Difference",
                        "explanation": "Different amounts",
                        "category": "amount",
                        "severity": "high",
                        "kind": "numerical",
                        "observation_ids": refs,
                        "check_ids": ["check"],
                        "policy_refs": [],
                    }
                ],
                "assessed_topics": ["amount"],
                "unresolved_checks": [],
                "links": [],
            }
        else:
            # The semantic interface has short aliases, original quotes, and no
            # arithmetic-validity label that could bias independent adjudication.
            evidence = json.loads(messages[1]["content"])
            selected = next(o for o in evidence["observations"] if o["id"] == refs[0])
            quote_id = selected["quote_id"]
            assert evidence["source_quotes"][quote_id] == ("17" if corrected else "91")
            assert "semantic_refinement_feedback" not in evidence["context"]
            assert "verification" not in evidence["proposed_findings"][0]
            accepted = corrected and correction_succeeds
            payload = {
                "checks": [
                    {
                        "id": "check",
                        "verdict": "valid" if accepted else "invalid",
                        "observation_ids": refs,
                        "reason": "Obligation assessment",
                    }
                ],
                "findings": [
                    {
                        "id": "0",
                        "verdict": "supported" if accepted else "unsupported",
                        "observation_ids": refs,
                        "reason": "Claim assessment",
                    }
                ],
            }
        return {"content": json.dumps(payload)}

    client = type("Client", (), {})()
    client.complete = AsyncMock(side_effect=response)
    result = await review(client, "audit", "internal", observations, {})
    assert client.complete.await_count == 6
    assert result["semantic_refinement"]["attempts"] == 1
    if correction_succeeds:
        assert not result["unresolved_checks"]
        assert result["findings"][0]["observation_ids"] == ["original:3", "original:4"]
        assert result["semantic_refinement"]["initial_checks"][0]["left"] == {
            "observation_id": "original:1"
        }
        assert (
            result["semantic_refinement"]["initial_decisions"]["checks"][0]["verdict"] == "invalid"
        )
    else:
        assert not result["findings"]
        assert result["unresolved_checks"]


@pytest.mark.asyncio
async def test_correction_repairs_a_plan_that_drops_a_previously_valid_obligation():
    observations = [
        {
            "id": f"source:{i}",
            "document_id": "doc",
            "field_key": "amount",
            "value_type": "money",
            "unit": "EUR",
            "raw_value": value,
            "normalized_value": value,
            "quote": value,
        }
        for i, value in enumerate(["71", "73", "29", "31"], 1)
    ]

    def check(identifier, refs):
        return {
            "id": identifier,
            "purpose": "Compare source amounts",
            "relation": "equals",
            "left": {"observation_id": refs[0]},
            "right": {"observation_id": refs[1]},
        }

    corrective_plans = 0

    async def response(audit, stage, model, messages, **kwargs):
        nonlocal corrective_plans
        refined = stage.endswith("_refinement")
        entries = [("keep", ["o1", "o2"]), ("fixed" if refined else "invalid", ["o3", "o4"])]
        if "plan" in stage:
            if refined:
                corrective_plans += 1
                if corrective_plans == 1:
                    entries = entries[1:]
                else:
                    assert "previously valid check" in messages[-2]["content"]
            payload = {
                "checks": [check(identifier, refs) for identifier, refs in entries],
                "unresolved_checks": [],
            }
        elif "findings" in stage:
            payload = {
                "findings": [
                    {
                        "title": identifier,
                        "explanation": "Different source amounts",
                        "category": "amount",
                        "severity": "high",
                        "kind": "numerical",
                        "observation_ids": refs,
                        "check_ids": [identifier],
                        "policy_refs": [],
                    }
                    for identifier, refs in entries
                ],
                "assessed_topics": [],
                "unresolved_checks": [],
                "links": [],
            }
        else:
            payload = {
                "checks": [
                    {
                        "id": identifier,
                        "verdict": "invalid" if identifier == "invalid" else "valid",
                        "observation_ids": refs,
                        "reason": "Obligation reviewed",
                    }
                    for identifier, refs in entries
                ],
                "findings": [
                    {
                        "id": str(i),
                        "verdict": "unsupported" if identifier == "invalid" else "supported",
                        "observation_ids": refs,
                        "reason": "Claim reviewed",
                    }
                    for i, (identifier, refs) in enumerate(entries)
                ],
            }
        return {"content": json.dumps(payload)}

    client = type("Client", (), {})()
    client.complete = AsyncMock(side_effect=response)
    result = await review(client, "audit", "internal", observations, {})
    assert corrective_plans == 1
    assert client.complete.await_count == 6
    assert {check["id"] for check in result["check_definitions"]} == {"keep", "fixed"}
    assert {f["title"] for f in result["findings"]} == {"keep", "fixed"}
    assert not result["unresolved_checks"]


@pytest.mark.asyncio
async def test_missing_failed_proof_gets_one_output_repair():
    observations = [
        dict(
            id=f"source:{i}",
            document_id="doc",
            field_key="amount",
            value_type="money",
            unit="EUR",
            raw_value=value,
            normalized_value=value,
            quote=value,
        )
        for i, value in enumerate(["81", "84", "11", "13"], 1)
    ]
    checks = [
        dict(
            id=identifier,
            purpose=identifier,
            left={"observation_id": refs[0]},
            right={"observation_id": refs[1]},
            relation="equals",
        )
        for identifier, refs in [("first", ["o1", "o2"]), ("second", ["o3", "o4"])]
    ]
    findings_calls = 0

    async def response(audit, stage, model, messages, **kwargs):
        nonlocal findings_calls
        if "plan" in stage:
            payload = dict(checks=checks, unresolved_checks=[])
        elif "findings" in stage:
            findings_calls += 1
            if findings_calls == 2:
                assert "not covered" in messages[-2]["content"]
            findings = [
                dict(
                    kind="numerical",
                    severity="high",
                    category="amount",
                    title=c["id"],
                    explanation="Mismatch",
                    observation_ids=[c["left"]["observation_id"], c["right"]["observation_id"]],
                    check_ids=[c["id"]],
                    policy_refs=[],
                )
                for c in checks[:findings_calls]
            ]
            payload = dict(findings=findings, assessed_topics=[], unresolved_checks=[], links=[])
        else:
            payload = dict(
                checks=[
                    dict(
                        id=c["id"],
                        verdict="valid",
                        observation_ids=[c["left"]["observation_id"], c["right"]["observation_id"]],
                        reason="Checked",
                    )
                    for c in checks
                ],
                findings=[
                    dict(
                        id=str(i),
                        verdict="supported",
                        observation_ids=[c["left"]["observation_id"], c["right"]["observation_id"]],
                        reason="Checked",
                    )
                    for i, c in enumerate(checks)
                ],
            )
        return {"content": json.dumps(payload)}

    client = type("Client", (), {})()
    client.complete = AsyncMock(side_effect=response)
    result = await review(client, "audit", "internal", observations, {})
    assert findings_calls == 2
    assert client.complete.await_count == 4
    assert not result["unresolved_checks"]
    assert len(result["findings"]) == 2
