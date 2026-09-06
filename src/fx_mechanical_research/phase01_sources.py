"""Phase 01 free-source and instrument qualification.

This module audits source capability and BIS coverage only.  It deliberately
contains no return, signal, or PnL calculation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import cast


class QualificationError(RuntimeError):
    """A source registry or raw source fails structural validation."""


class CheckStatus(StrEnum):
    """Result of one evidence requirement."""

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    DYNAMIC_BIS = "DYNAMIC_BIS"


class Verdict(StrEnum):
    """Frozen Phase 01 decision vocabulary."""

    EXECUTABLE = "PASS_EXECUTABLE_TOTAL_RETURN"
    PREDICTABILITY = "PASS_PREDICTABILITY_ONLY"
    REVIEW = "REVIEW_REQUIRED"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Candidate:
    """One candidate source or compatible source stack."""

    candidate_id: str
    source_class: str
    instrument_model: str
    checks: dict[str, CheckStatus]
    evidence_urls: tuple[str, ...]
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceOverlap:
    """Outcome exposure inherited from an earlier workspace repository."""

    repository: str
    source: str
    exposed_scope: str
    impact: str


@dataclass(frozen=True)
class Registry:
    """Frozen inputs used by the qualification rules."""

    registry_version: str
    contract_version: str
    generated_at_utc: str
    window_start: date
    minimum_latest_date: date
    window_selection_rule: str
    required_currency_areas: dict[str, str]
    exact_tsmom_previously_computed: bool
    historical_fx_outcomes_previously_exposed: bool
    prior_evidence_overlap: tuple[EvidenceOverlap, ...]
    predictability_gate: tuple[str, ...]
    executable_gate: tuple[str, ...]
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class CurrencyCoverage:
    """Coverage evidence for one BIS daily currency series."""

    currency: str
    ref_area: str
    first_date: date | None
    last_date: date | None
    valid_observations: int
    observations_in_common_window: int
    missing_status_rows: int
    invalid_normal_rows: int
    duplicate_dates: int
    non_free_rows: int

    def passes(self, *, start: date, minimum_latest: date) -> bool:
        """Return whether coverage satisfies the registered diagnostic window."""

        return (
            self.first_date is not None
            and self.first_date <= start
            and self.last_date is not None
            and self.last_date >= minimum_latest
            and self.observations_in_common_window > 0
            and self.invalid_normal_rows == 0
            and self.duplicate_dates == 0
            and self.non_free_rows == 0
        )


@dataclass(frozen=True)
class BisAudit:
    """Machine audit of the official BIS XRU bulk file."""

    coverage: tuple[CurrencyCoverage, ...]
    passed: bool
    csv_sha256: str
    csv_bytes: int


REQUIRED_BIS_COLUMNS = {
    "FREQ:Frequency",
    "REF_AREA:Reference area",
    "CURRENCY:Currency",
    "COLLECTION:Collection",
    "TIME_PERIOD:Time period or range",
    "OBS_VALUE:Observation Value",
    "AVAILABILITY:Availability",
    "OBS_STATUS:Observation Status",
    "OBS_CONF:Observation confidentiality",
}


def _as_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise QualificationError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _as_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise QualificationError(f"{label} must be an array")
    return cast(list[object], value)


def _as_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise QualificationError(f"{label} must be a non-empty string")
    return value


def _as_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise QualificationError(f"{label} must be a Boolean")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    return tuple(_as_str(item, label) for item in _as_list(value, label))


def _token(value: str) -> str:
    """Return the SDMX code preceding its human-readable label."""

    return value.split(":", maxsplit=1)[0].strip()


def sha256_file(path: Path) -> str:
    """Hash a file without loading the complete source into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_registry(path: Path) -> Registry:
    """Read and strictly validate the frozen source registry."""

    raw = _as_dict(json.loads(path.read_text(encoding="utf-8")), "registry")
    window = _as_dict(raw.get("common_diagnostic_window"), "window")
    gates = _as_dict(raw.get("gates"), "gates")
    overlap = _as_dict(raw.get("prior_evidence_overlap"), "prior overlap")
    areas_raw = _as_dict(raw.get("required_currency_areas"), "currency areas")
    currency_areas = {
        _as_str(currency, "currency"): _as_str(area, f"area for {currency}")
        for currency, area in areas_raw.items()
    }
    if len(currency_areas) != 9 or len(set(currency_areas.values())) != 9:
        raise QualificationError("exactly nine unique non-USD G10 areas are required")

    predictability = _string_tuple(gates.get("predictability"), "predictability")
    executable = _string_tuple(
        gates.get("executable_total_return"), "executable_total_return"
    )
    if not predictability or not executable:
        raise QualificationError("both source gates must be non-empty")
    if not set(predictability).issubset(executable):
        raise QualificationError("predictability checks must be a subset of execution")

    candidates: list[Candidate] = []
    identifiers: set[str] = set()
    for index, item in enumerate(_as_list(raw.get("candidates"), "candidates")):
        spec = _as_dict(item, f"candidate {index}")
        candidate_id = _as_str(spec.get("id"), f"candidate {index} id")
        if candidate_id in identifiers:
            raise QualificationError(f"duplicate candidate id: {candidate_id}")
        identifiers.add(candidate_id)
        checks_raw = _as_dict(spec.get("checks"), f"checks for {candidate_id}")
        if set(checks_raw) != set(executable):
            missing = sorted(set(executable) - set(checks_raw))
            extra = sorted(set(checks_raw) - set(executable))
            raise QualificationError(
                f"{candidate_id} check mismatch; missing={missing}, extra={extra}"
            )
        try:
            checks = {
                name: CheckStatus(_as_str(value, f"{candidate_id}:{name}"))
                for name, value in checks_raw.items()
            }
        except ValueError as exc:
            raise QualificationError(
                f"{candidate_id} contains an invalid check status"
            ) from exc
        candidates.append(
            Candidate(
                candidate_id=candidate_id,
                source_class=_as_str(spec.get("source_class"), "source_class"),
                instrument_model=_as_str(
                    spec.get("instrument_model"), "instrument_model"
                ),
                checks=checks,
                evidence_urls=_string_tuple(
                    spec.get("evidence_urls"), f"evidence_urls for {candidate_id}"
                ),
                conditions=_string_tuple(
                    spec.get("conditions"), f"conditions for {candidate_id}"
                ),
            )
        )
    if not candidates:
        raise QualificationError("at least one candidate is required")

    overlap_rows = tuple(
        EvidenceOverlap(
            repository=_as_str(item.get("repository"), "overlap repository"),
            source=_as_str(item.get("source"), "overlap source"),
            exposed_scope=_as_str(item.get("exposed_scope"), "exposed scope"),
            impact=_as_str(item.get("impact"), "overlap impact"),
        )
        for raw_item in _as_list(overlap.get("repositories"), "overlap repositories")
        for item in (_as_dict(raw_item, "overlap repository"),)
    )
    if not overlap_rows:
        raise QualificationError("prior evidence overlap audit cannot be empty")

    return Registry(
        registry_version=_as_str(raw.get("registry_version"), "registry_version"),
        contract_version=_as_str(raw.get("contract_version"), "contract_version"),
        generated_at_utc=_as_str(
            raw.get("qualification_run_time_utc"), "qualification_run_time_utc"
        ),
        window_start=date.fromisoformat(_as_str(window.get("start"), "start")),
        minimum_latest_date=date.fromisoformat(
            _as_str(window.get("minimum_latest_date"), "minimum_latest_date")
        ),
        window_selection_rule=_as_str(
            window.get("selection_rule"), "selection_rule"
        ),
        required_currency_areas=currency_areas,
        exact_tsmom_previously_computed=_as_bool(
            overlap.get("exact_tsmom_v1_previously_computed"),
            "exact_tsmom_v1_previously_computed",
        ),
        historical_fx_outcomes_previously_exposed=_as_bool(
            overlap.get("historical_fx_outcomes_previously_exposed"),
            "historical_fx_outcomes_previously_exposed",
        ),
        prior_evidence_overlap=overlap_rows,
        predictability_gate=predictability,
        executable_gate=executable,
        candidates=tuple(candidates),
    )


def audit_bis_csv(path: Path, registry: Registry) -> BisAudit:
    """Verify actual daily G10 coverage in the BIS XRU flat CSV."""

    if not path.is_file():
        raise QualificationError(f"BIS CSV not found: {path}")
    mutable: dict[str, dict[str, object]] = {
        currency: {
            "dates": set(),
            "first": None,
            "last": None,
            "valid": 0,
            "window": 0,
            "missing": 0,
            "invalid": 0,
            "duplicates": 0,
            "non_free": 0,
        }
        for currency in registry.required_currency_areas
    }
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        missing_columns = sorted(REQUIRED_BIS_COLUMNS - fieldnames)
        if missing_columns:
            raise QualificationError(f"BIS CSV missing columns: {missing_columns}")
        for row in reader:
            if _token(row["FREQ:Frequency"]) != "D":
                continue
            currency = _token(row["CURRENCY:Currency"])
            required_area = registry.required_currency_areas.get(currency)
            if required_area is None:
                continue
            if _token(row["REF_AREA:Reference area"]) != required_area:
                continue
            state = mutable[currency]
            observed = date.fromisoformat(row["TIME_PERIOD:Time period or range"])
            status = _token(row["OBS_STATUS:Observation Status"])
            if status != "A":
                state["missing"] = cast(int, state["missing"]) + 1
                continue
            try:
                value = float(row["OBS_VALUE:Observation Value"])
            except ValueError:
                state["invalid"] = cast(int, state["invalid"]) + 1
                continue
            if not math.isfinite(value) or value <= 0:
                state["invalid"] = cast(int, state["invalid"]) + 1
                continue
            dates = cast(set[date], state["dates"])
            if observed in dates:
                state["duplicates"] = cast(int, state["duplicates"]) + 1
            dates.add(observed)
            state["valid"] = cast(int, state["valid"]) + 1
            if registry.window_start <= observed <= registry.minimum_latest_date:
                state["window"] = cast(int, state["window"]) + 1
            first = cast(date | None, state["first"])
            last = cast(date | None, state["last"])
            state["first"] = observed if first is None else min(first, observed)
            state["last"] = observed if last is None else max(last, observed)
            if _token(row["OBS_CONF:Observation confidentiality"]) != "F":
                state["non_free"] = cast(int, state["non_free"]) + 1

    coverage = tuple(
        CurrencyCoverage(
            currency=currency,
            ref_area=registry.required_currency_areas[currency],
            first_date=cast(date | None, state["first"]),
            last_date=cast(date | None, state["last"]),
            valid_observations=cast(int, state["valid"]),
            observations_in_common_window=cast(int, state["window"]),
            missing_status_rows=cast(int, state["missing"]),
            invalid_normal_rows=cast(int, state["invalid"]),
            duplicate_dates=cast(int, state["duplicates"]),
            non_free_rows=cast(int, state["non_free"]),
        )
        for currency, state in sorted(mutable.items())
    )
    passed = all(
        item.passes(
            start=registry.window_start,
            minimum_latest=registry.minimum_latest_date,
        )
        for item in coverage
    )
    return BisAudit(
        coverage=coverage,
        passed=passed,
        csv_sha256=sha256_file(path),
        csv_bytes=path.stat().st_size,
    )


def resolve_checks(
    candidate: Candidate, *, bis_coverage_passed: bool
) -> dict[str, CheckStatus]:
    """Replace raw-data-dependent checks with their machine audit result."""

    resolution = CheckStatus.PASS if bis_coverage_passed else CheckStatus.FAIL
    return {
        name: resolution if status is CheckStatus.DYNAMIC_BIS else status
        for name, status in candidate.checks.items()
    }


def derive_verdict(
    checks: dict[str, CheckStatus],
    *,
    predictability_gate: tuple[str, ...],
    executable_gate: tuple[str, ...],
) -> Verdict:
    """Derive a verdict from evidence checks without subjective scoring."""

    if all(checks[name] is CheckStatus.PASS for name in executable_gate):
        return Verdict.EXECUTABLE
    if all(checks[name] is CheckStatus.PASS for name in predictability_gate):
        return Verdict.PREDICTABILITY
    predictability_states = {checks[name] for name in predictability_gate}
    if CheckStatus.REVIEW in predictability_states:
        return Verdict.REVIEW
    return Verdict.FAIL


def derive_phase_verdict(verdicts: tuple[Verdict, ...]) -> Verdict:
    """Select the strongest supported claim across candidate source stacks."""

    for verdict in (
        Verdict.EXECUTABLE,
        Verdict.PREDICTABILITY,
        Verdict.REVIEW,
        Verdict.FAIL,
    ):
        if verdict in verdicts:
            return verdict
    raise QualificationError("no candidate verdicts were produced")


def _coverage_dict(
    item: CurrencyCoverage, registry: Registry
) -> dict[str, object]:
    return {
        "currency": item.currency,
        "ref_area": item.ref_area,
        "first_date": item.first_date.isoformat() if item.first_date else None,
        "last_date": item.last_date.isoformat() if item.last_date else None,
        "valid_observations": item.valid_observations,
        "observations_in_common_window": item.observations_in_common_window,
        "missing_status_rows": item.missing_status_rows,
        "invalid_normal_rows": item.invalid_normal_rows,
        "duplicate_dates": item.duplicate_dates,
        "non_free_rows": item.non_free_rows,
        "coverage_pass": item.passes(
            start=registry.window_start,
            minimum_latest=registry.minimum_latest_date,
        ),
    }


def _coverage_label(item: CurrencyCoverage, registry: Registry) -> str:
    passed = item.passes(
        start=registry.window_start,
        minimum_latest=registry.minimum_latest_date,
    )
    return "PASS" if passed else "FAIL"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_matrix(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise QualificationError("source matrix cannot be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _render_report(
    *,
    registry: Registry,
    audit: BisAudit,
    matrix: list[dict[str, str]],
    phase_verdict: Verdict,
) -> str:
    candidate_rows = "\n".join(
        f"| `{row['candidate_id']}` | {row['source_class']} | "
        f"`{row['verdict']}` | {row['execution_blockers']} |"
        for row in matrix
    )
    coverage_rows = "\n".join(
        f"| {item.currency} | {item.ref_area} | {item.first_date} | "
        f"{item.last_date} | {item.valid_observations:,} | "
        f"{_coverage_label(item, registry)} |"
        for item in audit.coverage
    )
    overlap_rows = "\n".join(
        f"| `{item.repository}` | {item.source} | {item.exposed_scope} |"
        for item in registry.prior_evidence_overlap
    )
    return f"""# Phase 01 - Free source and instrument qualification

Decision: `{phase_verdict.value}`

Trading-claim status: `NOT_TESTED`

## Plain-language result

Free data are sufficient to test whether the frozen 12-month signal predicts
the next reference-rate movement across the G10 basket. They are not sufficient
to claim a tradable net return. No audited free source stack currently combines
historical holding return or financing, transaction costs, and instrument
mechanics for all nine non-USD G10 legs.

This is a data-boundary result, not evidence that TSMOM works or fails. Phase 01
did not calculate a return, signal, Sharpe ratio, confidence interval, or PnL.

## Candidate matrix

| Candidate | Class | Verdict | Missing or unresolved execution fields |
| --- | --- | --- | --- |
{candidate_rows}

`bis_xru_reference_spot` is selected only for a possible price-predictability
diagnostic. It is not selected as the executable v1 instrument.

## Verified BIS coverage

The official bulk CSV was audited rather than trusting a catalog description.
The common diagnostic window was frozen as {registry.window_start} through at
least {registry.minimum_latest_date}, before any candidate return was read.

| Currency | BIS area | First valid date | Last valid date | Valid rows | Gate |
| --- | --- | --- | --- | ---: | --- |
{coverage_rows}

Bulk CSV SHA-256: `{audit.csv_sha256}`

## Prior evidence overlap

The exact TSMOM v1 return was not previously computed, but related repositories
already exposed overlapping FX outcomes. No historical period is labelled an
untouched holdout.

| Repository | Prior source | Exposed scope |
| --- | --- | --- |
{overlap_rows}

## What remains blocked

- CME futures remain the preferred tradable implementation, but credential-free
  bulk contract history, permissions, and continuous liquid coverage for all
  nine legs were not verified.
- Broker bid/ask history can measure spreads, but neither reviewed broker exposes
  a verified public historical financing series for the required period.
- A policy-rate differential is not a substitute for forward points or realized
  broker swap because it omits basis, tenor conventions, and broker markup.
- Reference rates contain no executable bid/ask, commission, roll, or financing.

## Authorized next work

Phase 02 may build a causal canonical layer for a clearly labelled
`PREDICTABILITY_ONLY` diagnostic, including the one-week availability lag and
quote inversion. Under contract v0.1, primary strategy PnL and Phases 03-05 stay
blocked until an executable total-return source passes qualification. An
alternative is a dated contract amendment that explicitly changes the research
claim; it must happen before outcome inspection.
"""


def run_phase01(
    *,
    registry_path: Path,
    bis_csv_path: Path,
    evidence_root: Path,
    bis_archive_path: Path | None = None,
) -> dict[str, object]:
    """Run the complete, PnL-free Phase 01 audit and write compact evidence."""

    registry = load_registry(registry_path)
    audit = audit_bis_csv(bis_csv_path, registry)
    matrix: list[dict[str, str]] = []
    verdicts: list[Verdict] = []
    for candidate in registry.candidates:
        checks = resolve_checks(candidate, bis_coverage_passed=audit.passed)
        verdict = derive_verdict(
            checks,
            predictability_gate=registry.predictability_gate,
            executable_gate=registry.executable_gate,
        )
        verdicts.append(verdict)
        blockers = [
            name
            for name in registry.executable_gate
            if checks[name] is not CheckStatus.PASS
        ]
        matrix.append(
            {
                "candidate_id": candidate.candidate_id,
                "source_class": candidate.source_class,
                "instrument_model": candidate.instrument_model,
                **{name: checks[name].value for name in registry.executable_gate},
                "verdict": verdict.value,
                "execution_blockers": ";".join(blockers) or "none",
                "evidence_urls": " ".join(candidate.evidence_urls),
                "conditions": " | ".join(candidate.conditions),
            }
        )
    phase_verdict = derive_phase_verdict(tuple(verdicts))
    trading_status = (
        "ELIGIBLE_FOR_RETURN_RESEARCH"
        if phase_verdict is Verdict.EXECUTABLE
        else "NOT_TESTED"
    )
    selected_diagnostic = (
        "bis_xru_reference_spot"
        if next(
            row["verdict"]
            for row in matrix
            if row["candidate_id"] == "bis_xru_reference_spot"
        )
        == Verdict.PREDICTABILITY.value
        else None
    )
    summary: dict[str, object] = {
        "phase": "01-source-qualification",
        "phase_status": "COMPLETE",
        "generated_at_utc": registry.generated_at_utc,
        "contract_version": registry.contract_version,
        "registry_version": registry.registry_version,
        "phase_decision": phase_verdict.value,
        "trading_claim_status": trading_status,
        "primary_executable_implementation": None,
        "selected_predictability_source": selected_diagnostic,
        "candidate_pnl_computed": False,
        "historical_window_untouched": False,
        "common_diagnostic_window": {
            "start": registry.window_start.isoformat(),
            "minimum_latest_date": registry.minimum_latest_date.isoformat(),
            "selection_rule": registry.window_selection_rule,
        },
        "candidate_counts": {
            verdict.value: verdicts.count(verdict) for verdict in Verdict
        },
        "blocking_reason": (
            None
            if phase_verdict is Verdict.EXECUTABLE
            else (
                "No verified free G10 source stack contains historical total "
                "return, transaction costs, and complete instrument mechanics."
            )
        ),
    }
    coverage_payload = {
        "source_id": "bis_xru_reference_spot",
        "source_url": "https://data.bis.org/static/bulk/WS_XRU_csv_flat.zip",
        "csv_sha256": audit.csv_sha256,
        "csv_bytes": audit.csv_bytes,
        "coverage_gate_pass": audit.passed,
        "currencies": [_coverage_dict(item, registry) for item in audit.coverage],
    }
    overlap_payload = {
        "exact_tsmom_v1_previously_computed": (
            registry.exact_tsmom_previously_computed
        ),
        "historical_fx_outcomes_previously_exposed": (
            registry.historical_fx_outcomes_previously_exposed
        ),
        "historical_window_untouched": False,
        "repositories": [
            {
                "repository": item.repository,
                "source": item.source,
                "exposed_scope": item.exposed_scope,
                "impact": item.impact,
            }
            for item in registry.prior_evidence_overlap
        ],
    }
    raw_manifest: dict[str, object] = {
        "raw_files_committed": False,
        "source_registry": {
            "filename": registry_path.name,
            "sha256": sha256_file(registry_path),
            "bytes": registry_path.stat().st_size,
        },
        "bis_csv": {
            "filename": bis_csv_path.name,
            "sha256": audit.csv_sha256,
            "bytes": audit.csv_bytes,
        },
    }
    if bis_archive_path is not None:
        raw_manifest["bis_archive"] = {
            "filename": bis_archive_path.name,
            "sha256": sha256_file(bis_archive_path),
            "bytes": bis_archive_path.stat().st_size,
            "url": "https://data.bis.org/static/bulk/WS_XRU_csv_flat.zip",
        }

    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_matrix(evidence_root / "source_matrix.csv", matrix)
    _write_json(evidence_root / "bis_coverage.json", coverage_payload)
    _write_json(evidence_root / "decision.json", summary)
    _write_json(evidence_root / "prior_evidence_overlap.json", overlap_payload)
    _write_json(evidence_root / "raw_source_manifest.json", raw_manifest)
    (evidence_root / "REPORT.md").write_text(
        _render_report(
            registry=registry,
            audit=audit,
            matrix=matrix,
            phase_verdict=phase_verdict,
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest_entries = [
        {
            "path": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(evidence_root.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    _write_json(
        evidence_root / "manifest.json",
        {
            "phase": "01-source-qualification",
            "generated_at_utc": registry.generated_at_utc,
            "files": manifest_entries,
        },
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("config/source_registry_v0_1.json"),
    )
    parser.add_argument(
        "--bis-csv",
        type=Path,
        default=Path("data/raw/phase01/WS_XRU_csv_flat.csv"),
    )
    parser.add_argument(
        "--bis-archive",
        type=Path,
        default=Path("data/raw/phase01/WS_XRU_csv_flat.zip"),
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("evidence/phase01"),
    )
    args = parser.parse_args()
    archive = args.bis_archive if args.bis_archive.is_file() else None
    summary = run_phase01(
        registry_path=args.registry,
        bis_csv_path=args.bis_csv,
        evidence_root=args.evidence_root,
        bis_archive_path=archive,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
