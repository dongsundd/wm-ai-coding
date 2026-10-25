"""Structured review claims bound to a source snapshot; identity is host asserted."""
from __future__ import annotations

import json
from pathlib import Path

from wm_ai_coding.evidence.inspection import digest, inspect_change, requirement_inventory
from wm_ai_coding.evidence.runs import workspace_digest, latest_run, inputs


def record_review(repo: Path, change: Path, *, reviewer: str, mode: str, findings: list,
                  browser_runs: list[str] | None = None) -> dict:
    if not reviewer.strip() or mode not in {"self", "independent"} or not isinstance(findings, list):
        raise ValueError("review requires reviewer, explicit mode and structured findings")
    for finding in findings:
        if (not isinstance(finding, dict) or finding.get("severity") not in {"blocking", "warning", "info"}
                or not isinstance(finding.get("message"), str) or type(finding.get("resolved")) is not bool):
            raise ValueError("invalid review finding")
    result = {"schema_version": 1, "reviewer": reviewer, "mode": mode, "findings": findings,
              "planning": inspect_change(change)["planning_digest"], "workspace": workspace_digest(repo),
              "browser_runs": browser_runs or [], "trust": "host asserted, not authenticated"}
    (change / "review.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def review_findings(repo: Path, change: Path, frontend: bool, *, change_name: str | None = None) -> list[str]:
    try:
        review = json.loads((change / "review.json").read_text(encoding="utf-8"))
        if (review.get("schema_version") != 1 or not review.get("reviewer")
                or review.get("mode") not in {"self", "independent"}
                or not isinstance(review.get("findings"), list)):
            return ["invalid structured review"]
        findings = []
        if (review.get("planning") != inspect_change(change)["planning_digest"]
                or review.get("workspace") != workspace_digest(repo)):
            findings.append("stale review snapshot")
        for item in review["findings"]:
            if not isinstance(item, dict) or item.get("severity") not in {"blocking", "warning", "info"} or type(item.get("resolved")) is not bool:
                findings.append("invalid review finding")
            elif item["severity"] == "blocking" and not item["resolved"]:
                findings.append("unresolved blocking review finding")
        if frontend:
            successful = []
            from wm_ai_coding.evidence.runs import load_plan
            for check in load_plan(change):
                if check.get("kind") != "browser":
                    continue
                latest = latest_run(repo, change_name or change.name, check["id"])
                if latest:
                    record, directory = latest
                    if (record["id"] in review.get("browser_runs", []) and record.get("status") == "passed"
                            and record.get("inputs") == inputs(repo, change) and record.get("outputs") == inputs(repo, change)
                            and check.get("artifacts") and check.get("target")
                            and record.get("stdout_sha256") == digest(directory / "stdout.log")):
                        successful.append(record)
            if not successful:
                findings.append("missing current browser evidence with target and artifacts")
        return findings
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as exc:
        return [f"review missing or invalid: {exc}"]


def write_verification_summary(repo: Path, change: Path, *, frontend_changed: bool) -> dict:
    """Validate current evidence and persist requirement-to-run coverage."""
    from .runs import load_plan, verification_findings
    from ..lifecycle.common import MachineError

    findings = verification_findings(repo, change) + review_findings(repo, change, frontend_changed)
    if findings:
        raise MachineError('; '.join(findings))
    requirements, scenarios = requirement_inventory(change)
    coverage = {reference: [] for reference in requirements | scenarios}
    for check in load_plan(change):
        latest = latest_run(repo, change.name, check['id'])
        for reference in check.get('requirements', []) + check.get('scenarios', []):
            coverage[reference].append(latest[0]['id'])
    result = {'schema_version': 1, 'status': 'passed', 'coverage': coverage}
    (change / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def verification_summary(repo: Path, change: Path, *, change_name: str | None = None) -> list[str]:
    try:
        data = json.loads((change / "verification.json").read_text(encoding="utf-8"))
        requirements, scenarios = requirement_inventory(change)
        if data.get("status") != "passed" or data.get("schema_version") != 1:
            return ["verification summary is not passed"]
        refs = data.get("coverage", {})
        if not isinstance(refs, dict) or set(refs) != requirements | scenarios:
            return ["structured coverage is incomplete or unknown"]
        from wm_ai_coding.evidence.runs import load_plan
        records = {c["id"]: latest_run(repo, change_name or change.name, c["id"]) for c in load_plan(change)}
        for ref, run_ids in refs.items():
            if not isinstance(run_ids, list) or not run_ids:
                return ["coverage needs run IDs"]
            matching = []
            for c in load_plan(change):
                latest = records[c["id"]]
                if ref in c.get("requirements", []) + c.get("scenarios", []) and latest:
                    matching.append(latest[0]["id"])
            if not set(run_ids) <= set(matching):
                return ["coverage references unrelated or stale run IDs"]
        return []
    except (OSError, ValueError, TypeError, AttributeError):
        return ["structured verification summary missing or invalid"]
