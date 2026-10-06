"""Conservative, evidence-based issue grouping; no text similarity or vendor rules."""

import json
from copy import deepcopy
from hashlib import sha256

from app.features.audits.proofs import CheckDefinition, check_signature


def consolidate_findings(findings: list[dict], observations: list[dict]) -> list[dict]:
    registry = {observation["id"]: observation for observation in observations}
    grouped = {}
    for source in findings:
        finding = deepcopy(source)
        refs = set(finding["observation_ids"])
        rows = {
            (registry[ref]["document_id"], registry[ref].get("group_key"))
            for ref in refs
            if ref in registry
            and registry[ref].get("field_key", "").startswith("item.")
            and registry[ref].get("group_key")
        }
        only_item_sources = all(
            registry[ref].get("field_key", "").startswith("item.")
            for ref in refs
            if ref in registry
        )
        # Quantity, price and amount checks on the same row belong to one issue
        # with individually preserved checks. Different rows/entities remain separate.
        if finding.get("kind") == "numerical" and rows and only_item_sources:
            subject = ("row", sorted(rows))
        elif (
            finding.get("kind") == "policy"
            and refs
            and all(registry[ref].get("group_key") for ref in refs)
        ):
            # Same explicit obligation on the same source record is one issue,
            # even when one explanation cites its name and another its status.
            # Evidence comparisons (e.g. name vs account) remain distinct.
            subject = (
                "policy-record",
                sorted(
                    {(registry[ref]["document_id"], registry[ref]["group_key"]) for ref in refs}
                ),
                sorted(finding.get("policy_refs", [])),
            )
        elif finding.get("verified_checks"):
            subject = (
                "proofs",
                sorted(
                    repr(check_signature(CheckDefinition.model_validate(check), registry))
                    for check in finding["verified_checks"]
                ),
            )
        else:
            subject = ("evidence", sorted(refs), sorted(finding.get("policy_refs", [])))
        key = json.dumps([finding["scope"], finding.get("kind"), subject], sort_keys=True)
        if key not in grouped:
            finding["case_id"] = sha256(key.encode()).hexdigest()[:20]
            finding["supporting_findings"] = []
            finding["related_issues"] = []
            grouped[key] = finding
            continue
        primary = grouped[key]
        primary["supporting_findings"].append(finding)
        for field in ("observation_ids", "calculation_ids", "check_ids", "policy_refs"):
            primary[field] = list(dict.fromkeys(primary.get(field, []) + finding.get(field, [])))
        checks = {check["id"]: check for check in primary.get("verified_checks", [])}
        checks.update({check["id"]: check for check in finding.get("verified_checks", [])})
        primary["verified_checks"] = list(checks.values())
        severity_order = {"low": 0, "medium": 1, "high": 2}
        primary["severity"] = max(
            (primary["severity"], finding["severity"]), key=severity_order.get
        )
    issues = list(grouped.values())
    for index, issue in enumerate(issues):
        for other in issues[index + 1 :]:
            shared = set(issue["observation_ids"]) & set(other["observation_ids"])
            if not shared:
                continue
            relation = "shared_evidence"
            if issue["scope"] == other["scope"]:
                # Calculation IDs are local to each review; across documents or
                # scopes equal calc_N strings are not the same proof.
                if issue["scope"] != "cross":
                    continue
                if not set(issue.get("calculation_ids", [])) & set(
                    other.get("calculation_ids", [])
                ):
                    continue
                relation = "contributing_check"
            for current, related in ((issue, other), (other, issue)):
                current["related_issues"].append(
                    {
                        "case_id": related["case_id"],
                        "title": related["title"],
                        "scope": related["scope"],
                        "relation": relation,
                    }
                )
    return issues
