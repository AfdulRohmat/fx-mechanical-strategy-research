from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from fx_mechanical_research.phase01_sources import sha256_file
from fx_mechanical_research.phase05_gate import (
    HistoricalDecision,
    HistoricalEvidence,
    HistoricalGateError,
    decide_historical_gate,
    load_gate_config,
    run_phase05,
    verify_evidence_manifest,
)

CONFIG_PATH = Path("config/historical_gate_v0_1.json")


def _executable_evidence(status: str = "SUPPORTED") -> HistoricalEvidence:
    config = load_gate_config(CONFIG_PATH)
    return HistoricalEvidence(
        phase01_decision=config.required_phase01_decision,
        phase02_claim_scope=config.required_phase02_scope,
        phase02_total_return_status=config.required_total_return_status,
        phase03_decision=config.required_phase03_decision,
        hypotheses={name: status for name in config.required_hypotheses},
        integrity_status=config.integrity_requirement,
    )


def test_config_freezes_exact_decision_vocabulary() -> None:
    config = load_gate_config(CONFIG_PATH)

    assert config.required_hypotheses == (
        "TSMOM_H1_NET_PORTFOLIO",
        "TSMOM_H2_INCREMENTAL_SIGNAL",
        "TSMOM_H3_MULTIPLE_TESTING",
        "TSMOM_H4_BREADTH_AND_TIME_STABILITY",
        "TSMOM_H5_COST_CAPACITY",
    )
    assert config.prospective_required_decision == HistoricalDecision.PROCEED.value


def test_all_supported_executable_evidence_can_proceed() -> None:
    config = load_gate_config(CONFIG_PATH)

    assert (
        decide_historical_gate(_executable_evidence(), config)
        is HistoricalDecision.PROCEED
    )


def test_failed_hypothesis_stops_executable_candidate() -> None:
    config = load_gate_config(CONFIG_PATH)
    evidence = _executable_evidence()
    hypotheses = dict(evidence.hypotheses)
    hypotheses["TSMOM_H2_INCREMENTAL_SIGNAL"] = "NOT_SUPPORTED"
    failed = HistoricalEvidence(
        phase01_decision=evidence.phase01_decision,
        phase02_claim_scope=evidence.phase02_claim_scope,
        phase02_total_return_status=evidence.phase02_total_return_status,
        phase03_decision=evidence.phase03_decision,
        hypotheses=hypotheses,
        integrity_status=evidence.integrity_status,
    )

    assert (
        decide_historical_gate(failed, config)
        is HistoricalDecision.DO_NOT_PROCEED
    )


def test_inadequate_source_precedes_apparent_hypothesis_failure() -> None:
    config = load_gate_config(CONFIG_PATH)
    evidence = _executable_evidence(status="NOT_SUPPORTED")
    inadequate = HistoricalEvidence(
        phase01_decision="PASS_PREDICTABILITY_ONLY",
        phase02_claim_scope="PREDICTABILITY_ONLY",
        phase02_total_return_status="NOT_BUILT",
        phase03_decision="NOT_TESTED",
        hypotheses=evidence.hypotheses,
        integrity_status="PASS",
    )

    assert (
        decide_historical_gate(inadequate, config)
        is HistoricalDecision.NOT_TESTED
    )


def test_manifest_verifier_rejects_mutated_evidence(tmp_path: Path) -> None:
    copied = tmp_path / "phase04"
    shutil.copytree(Path("evidence/phase04"), copied)
    report = copied / "REPORT.md"
    report.write_text(
        report.read_text(encoding="utf-8") + "mutation\n",
        encoding="utf-8",
    )

    with pytest.raises(HistoricalGateError, match="manifest hash mismatch"):
        verify_evidence_manifest(copied, "04-cross-sectional-challenger")


def test_current_lineage_finishes_not_tested_without_phase06(tmp_path: Path) -> None:
    evidence = tmp_path / "phase05"

    summary = run_phase05(
        root=Path.cwd(),
        config_path=CONFIG_PATH,
        evidence_root=evidence,
    )

    assert summary["historical_decision"] == "NOT_TESTED"
    assert summary["candidate_pnl_computed"] is False
    assert summary["prospective_phase_activated"] is False
    gate = json.loads(
        (evidence / "prospective_gate.json").read_text(encoding="utf-8")
    )
    assert gate["activated"] is False
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        assert sha256_file(evidence / item["path"]) == item["sha256"]
