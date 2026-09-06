"""Phase 05 manifest verification and historical research decision gate."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from .phase01_sources import sha256_file


class HistoricalGateError(RuntimeError):
    """Upstream evidence or gate configuration violates a mandatory invariant."""


class HistoricalDecision(StrEnum):
    NOT_TESTED = "NOT_TESTED"
    DO_NOT_PROCEED = "DO_NOT_PROCEED_WITH_TSMOM_V1"
    PROCEED = "PROCEED_TO_PROSPECTIVE_OBSERVATION_TSMOM_V1"


@dataclass(frozen=True)
class GateConfig:
    config_version: str
    contract_version: str
    generated_at_utc: str
    required_phase01_decision: str
    required_phase02_scope: str
    required_total_return_status: str
    required_phase03_decision: str
    required_hypotheses: tuple[str, ...]
    supported_status: str
    failed_status: str
    integrity_requirement: str
    prospective_required_decision: str


@dataclass(frozen=True)
class HistoricalEvidence:
    phase01_decision: str
    phase02_claim_scope: str
    phase02_total_return_status: str
    phase03_decision: str
    hypotheses: dict[str, str]
    integrity_status: str


@dataclass(frozen=True)
class ManifestAudit:
    phase: str
    manifest_path: str
    listed_files: int
    status: str
    manifest_sha256: str


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HistoricalGateError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise HistoricalGateError(f"{label} must be an array")
    return cast(list[object], value)


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise HistoricalGateError(f"{label} must be a non-empty string")
    return value


def load_gate_config(path: Path) -> GateConfig:
    """Load and validate the exact historical-decision vocabulary."""

    raw = _dict(json.loads(path.read_text(encoding="utf-8")), "gate config")
    decisions = _dict(raw.get("decisions"), "decisions")
    required = _dict(raw.get("required_upstream"), "required upstream")
    expected_decisions = {
        "not_tested": HistoricalDecision.NOT_TESTED.value,
        "do_not_proceed": HistoricalDecision.DO_NOT_PROCEED.value,
        "proceed": HistoricalDecision.PROCEED.value,
    }
    actual_decisions = {
        key: _str(decisions.get(key), f"decision {key}")
        for key in expected_decisions
    }
    if actual_decisions != expected_decisions:
        raise HistoricalGateError("historical decision vocabulary changed")
    if raw.get("challenger_can_change_primary_decision") is not False:
        raise HistoricalGateError("challenger cannot change the primary decision")
    hypotheses = tuple(
        _str(item, "hypothesis")
        for item in _list(raw.get("required_hypotheses"), "hypotheses")
    )
    if len(hypotheses) != 5 or len(set(hypotheses)) != 5:
        raise HistoricalGateError("exactly five unique hypotheses are required")
    result = GateConfig(
        config_version=_str(raw.get("config_version"), "config version"),
        contract_version=_str(raw.get("contract_version"), "contract version"),
        generated_at_utc=_str(raw.get("generated_at_utc"), "generated_at_utc"),
        required_phase01_decision=_str(
            required.get("phase01_decision"), "Phase 01 requirement"
        ),
        required_phase02_scope=_str(
            required.get("phase02_claim_scope"), "Phase 02 requirement"
        ),
        required_total_return_status=_str(
            required.get("phase02_monthly_total_return"), "total-return requirement"
        ),
        required_phase03_decision=_str(
            required.get("phase03_evaluated_decision"), "Phase 03 requirement"
        ),
        required_hypotheses=hypotheses,
        supported_status=_str(
            raw.get("supported_hypothesis_status"), "supported status"
        ),
        failed_status=_str(raw.get("failed_hypothesis_status"), "failed status"),
        integrity_requirement=_str(
            raw.get("integrity_requirement"), "integrity requirement"
        ),
        prospective_required_decision=_str(
            raw.get("prospective_activation_requires_exact_decision"),
            "prospective requirement",
        ),
    )
    if result.prospective_required_decision != HistoricalDecision.PROCEED.value:
        raise HistoricalGateError("prospective activation rule changed")
    return result


def verify_evidence_manifest(evidence_root: Path, phase: str) -> ManifestAudit:
    """Verify every committed file listed by a phase and reject extras."""

    manifest_path = evidence_root / "manifest.json"
    manifest = _dict(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        f"{phase} manifest",
    )
    files = _list(manifest.get("files"), f"{phase} manifest files")
    listed: set[str] = set()
    root_resolved = evidence_root.resolve()
    for index, raw_item in enumerate(files):
        item = _dict(raw_item, f"{phase} manifest item {index}")
        relative = _str(item.get("path"), "manifest path")
        if relative in listed:
            raise HistoricalGateError(f"duplicate manifest path: {phase}/{relative}")
        listed.add(relative)
        target = (evidence_root / relative).resolve()
        if target.parent != root_resolved:
            raise HistoricalGateError(f"unsafe manifest path: {relative}")
        if not target.is_file():
            raise HistoricalGateError(f"missing manifest file: {phase}/{relative}")
        expected_hash = _str(item.get("sha256"), "manifest SHA-256")
        if sha256_file(target) != expected_hash:
            raise HistoricalGateError(f"manifest hash mismatch: {phase}/{relative}")
        expected_bytes = item.get("bytes")
        if (
            not isinstance(expected_bytes, int)
            or target.stat().st_size != expected_bytes
        ):
            raise HistoricalGateError(f"manifest size mismatch: {phase}/{relative}")
    actual = {
        path.name
        for path in evidence_root.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != listed:
        raise HistoricalGateError(
            f"manifest inventory mismatch: {phase}; "
            f"unlisted={sorted(actual - listed)}, missing={sorted(listed - actual)}"
        )
    return ManifestAudit(
        phase=phase,
        manifest_path=manifest_path.as_posix(),
        listed_files=len(listed),
        status="PASS",
        manifest_sha256=sha256_file(manifest_path),
    )


def decide_historical_gate(
    evidence: HistoricalEvidence, config: GateConfig
) -> HistoricalDecision:
    """Apply the frozen precedence: inadequate data means NOT_TESTED."""

    source_ready = (
        evidence.phase01_decision == config.required_phase01_decision
        and evidence.phase02_claim_scope == config.required_phase02_scope
        and evidence.phase02_total_return_status
        == config.required_total_return_status
    )
    if not source_ready:
        return HistoricalDecision.NOT_TESTED
    if evidence.phase03_decision != config.required_phase03_decision:
        return HistoricalDecision.NOT_TESTED
    if set(evidence.hypotheses) != set(config.required_hypotheses):
        raise HistoricalGateError("Phase 03 hypothesis set changed")
    statuses = set(evidence.hypotheses.values())
    permitted = {config.supported_status, config.failed_status, "NOT_TESTED"}
    if not statuses.issubset(permitted):
        raise HistoricalGateError(f"unknown hypothesis status: {sorted(statuses)}")
    if "NOT_TESTED" in statuses:
        return HistoricalDecision.NOT_TESTED
    if (
        config.failed_status in statuses
        or evidence.integrity_status != config.integrity_requirement
    ):
        return HistoricalDecision.DO_NOT_PROCEED
    if statuses == {config.supported_status}:
        return HistoricalDecision.PROCEED
    raise HistoricalGateError("historical gate reached an impossible state")


def _load_current_evidence(root: Path) -> HistoricalEvidence:
    phase01_path = root / "evidence/phase01/decision.json"
    phase01 = _dict(
        json.loads(phase01_path.read_text(encoding="utf-8")),
        "Phase 01 decision",
    )
    phase02_path = root / "evidence/phase02/summary.json"
    phase02 = _dict(
        json.loads(phase02_path.read_text(encoding="utf-8")),
        "Phase 02 summary",
    )
    schema = _dict(
        json.loads(
            (root / "evidence/phase02/schema_coverage.json").read_text(
                encoding="utf-8"
            )
        ),
        "Phase 02 schema",
    )
    phase03_path = root / "evidence/phase03/summary.json"
    phase03 = _dict(
        json.loads(phase03_path.read_text(encoding="utf-8")),
        "Phase 03 summary",
    )
    hypotheses_raw = _dict(phase03.get("hypotheses"), "Phase 03 hypotheses")
    hypotheses = {
        key: _str(value, f"hypothesis {key}")
        for key, value in hypotheses_raw.items()
    }
    return HistoricalEvidence(
        phase01_decision=_str(
            phase01.get("phase_decision"), "Phase 01 decision value"
        ),
        phase02_claim_scope=_str(
            phase02.get("claim_scope"), "Phase 02 claim scope"
        ),
        phase02_total_return_status=_str(
            schema.get("monthly_total_return"), "total return status"
        ),
        phase03_decision=_str(phase03.get("decision"), "Phase 03 decision"),
        hypotheses=hypotheses,
        integrity_status="PASS",
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest(root: Path, generated_at: str) -> None:
    rows = [
        {
            "path": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    _write_json(
        root / "manifest.json",
        {
            "phase": "05-historical-decision",
            "generated_at_utc": generated_at,
            "files": rows,
        },
    )


def run_phase05(
    *,
    root: Path,
    config_path: Path,
    evidence_root: Path,
) -> dict[str, object]:
    """Verify Phases 01-04 and emit exactly one historical v1 decision."""

    config = load_gate_config(config_path)
    audits = tuple(
        verify_evidence_manifest(root / f"evidence/phase{number:02d}", phase)
        for number, phase in (
            (1, "01-source-qualification"),
            (2, "02-canonical-reference-layer"),
            (3, "03-tsmom-replication"),
            (4, "04-cross-sectional-challenger"),
        )
    )
    current = _load_current_evidence(root)
    decision = decide_historical_gate(current, config)
    phase04_path = root / "evidence/phase04/summary.json"
    phase04 = _dict(
        json.loads(phase04_path.read_text(encoding="utf-8")),
        "Phase 04 summary",
    )
    prospective_activated = decision.value == config.prospective_required_decision
    if prospective_activated:
        raise HistoricalGateError(
            "prospective activation needs power analysis and a reviewed lockbox"
        )

    phase_rows = [
        {
            "phase": "00",
            "status": "COMPLETE",
            "decision": "CONTRACT_FROZEN",
            "outcome_read": "false",
        },
        {
            "phase": "01",
            "status": "COMPLETE",
            "decision": current.phase01_decision,
            "outcome_read": "false",
        },
        {
            "phase": "02",
            "status": "COMPLETE_PREDICTABILITY_ONLY",
            "decision": current.phase02_claim_scope,
            "outcome_read": "false",
        },
        {
            "phase": "03",
            "status": "COMPLETE_BLOCKED_BEFORE_OUTCOME",
            "decision": current.phase03_decision,
            "outcome_read": "false",
        },
        {
            "phase": "04",
            "status": _str(phase04.get("phase_status"), "Phase 04 status"),
            "decision": _str(phase04.get("decision"), "Phase 04 decision"),
            "outcome_read": "false",
        },
        {
            "phase": "05",
            "status": "COMPLETE",
            "decision": decision.value,
            "outcome_read": "false",
        },
        {
            "phase": "06",
            "status": "NOT_ACTIVATED",
            "decision": "REQUIRES_HISTORICAL_PROCEED",
            "outcome_read": "false",
        },
    ]
    summary: dict[str, object] = {
        "phase": "05-historical-decision",
        "phase_status": "COMPLETE",
        "generated_at_utc": config.generated_at_utc,
        "historical_decision": decision.value,
        "trading_claim_status": "NOT_TESTED",
        "primary_hypotheses": current.hypotheses,
        "candidate_signal_evaluated": False,
        "candidate_pnl_computed": False,
        "challenger_signal_evaluated": False,
        "prospective_phase_activated": prospective_activated,
        "decision_reason": (
            "Executable total-return and cost data did not pass Phase 01; "
            "Phase 03 therefore stopped before actual outcome access."
        ),
    }
    prospective_gate = {
        "phase": "06-prospective-lockbox",
        "activated": prospective_activated,
        "required_decision": config.prospective_required_decision,
        "actual_decision": decision.value,
        "prospective_start_timestamp": None,
        "power_analysis_performed": False,
        "minimum_observations": None,
        "reason": "Historical proceed decision was not produced.",
    }
    manifest_audit = {
        "status": "PASS",
        "phases": [
            {
                "phase": audit.phase,
                "manifest_path": Path(audit.manifest_path)
                .resolve()
                .relative_to(root.resolve())
                .as_posix(),
                "listed_files": audit.listed_files,
                "status": audit.status,
                "manifest_sha256": audit.manifest_sha256,
            }
            for audit in audits
        ],
    }
    input_manifest = {
        "gate_config_sha256": sha256_file(config_path),
        "research_contract_sha256": sha256_file(
            root / "docs/RESEARCH_DECISION_CONTRACT.md"
        ),
        "trial_registry_sha256": sha256_file(root / "config/trial_registry.jsonl"),
        "upstream_manifest_sha256": {
            audit.phase: audit.manifest_sha256 for audit in audits
        },
    }
    report = f"""# Phase 05 - Historical research decision

Decision: `{decision.value}`

## Readable result

The mechanical strategy has not failed an alpha test. It has not received an
executable alpha test. Phase 01 found excellent free G10 reference-rate coverage
but no free source stack with complete holding return or financing, transaction
costs, and instrument mechanics. Phase 02 therefore built a causal price-only
panel, while Phases 03 and 04 stopped before reading actual outcomes.

All five TSMOM hypotheses remain `NOT_TESTED`. There are no realized strategy
returns, Sharpe ratios, confidence intervals, cost headroom estimates, or
multiple-testing results to interpret.

## Engineering result

The research controls succeeded: source hashes, causal timestamps, quote
orientation, month-end selection, schema boundaries, trial registration,
paper anchoring, pre-outcome gates, and all Phase 01-04 evidence manifests pass
their integrity checks. A future executable data source can enter through the
existing schemas without relabelling the current reference-rate panel.

## Phase 06

Phase 06 is `NOT_ACTIVATED`. No prospective start timestamp or observation
target has been invented because the required historical proceed decision is
absent. Activating it would violate contract v0.1.

## Next research choices

1. Acquire or qualify executable currency futures/forward history and rerun the
   frozen lineage without changing the signal.
2. Write a dated pre-outcome amendment for a narrower predictability study,
   whose conclusion cannot be trading profitability.
3. Close v1 as `NOT_TESTED` and preregister a different mechanical hypothesis.
"""
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_json(evidence_root / "decision.json", summary)
    _write_json(evidence_root / "prospective_gate.json", prospective_gate)
    _write_json(evidence_root / "manifest_audit.json", manifest_audit)
    _write_json(evidence_root / "input_manifest.json", input_manifest)
    _write_csv(evidence_root / "phase_summary.csv", phase_rows)
    (evidence_root / "REPORT.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )
    _write_manifest(evidence_root, config.generated_at_utc)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/historical_gate_v0_1.json"),
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("evidence/phase05"),
    )
    args = parser.parse_args()
    result = run_phase05(
        root=Path.cwd(),
        config_path=args.config,
        evidence_root=args.evidence_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
