#!/usr/bin/env python3
"""Verify recorded ETOR-55 resistor-simulation results, without inventing ADC readings.

Usage: python3 tests/check_etor_simulation.py results/etor_run.csv
Exit codes: 0 PASS, 1 FAIL, 2 BLOCKED (missing/insufficient test evidence).
"""
import argparse
import csv
import math
import sys
from collections import defaultdict

REQUIRED_COLUMNS = [
    "test_case", "resistance_ohm", "sample",
    "adc_a_forward_v", "adc_b_forward_v",
    "adc_a_reverse_v", "adc_b_reverse_v",
    "metric", "expected_state", "actual_state", "notes",
]
TEST_CASES = {
    "open": (None, "OBSERVE"),
    "dry_2m2": (2200000, "DRY"),
    "dry_1m": (1000000, "OBSERVE"),
    "trans_220k": (220000, "OBSERVE"),
    "trans_150k": (150000, "OBSERVE"),
    "trans_100k": (100000, "OBSERVE"),
    "wet_47k": (47000, "WET"),
    "wet_10k": (10000, "WET"),
    "low_1k": (1000, "OBSERVE"),
    "low_42": (42, "LOW_RESISTANCE"),
    "jumper_0": (0, "LOW_RESISTANCE"),
    "dry_2m2_repeat": (2200000, "DRY"),
}
ADC_COLUMNS = REQUIRED_COLUMNS[3:7]
STATES = {"DRY", "WET", "SHORT", "FAULT", "UNAVAILABLE", "UNCALIBRATED", "LOW_RESISTANCE"}
KNOWN_RES_TOLERANCE = 0.10  # Allows actual resistor tolerance/multimeter variance


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_file", help="CSV with real ESPHome ADC and state observations")
    ap.add_argument("--min-samples", type=int, default=10,
                    help="Required per test case (default: 10)")
    ap.add_argument("--allow-short-blocked", action="store_true",
                    help="Treat missing SHORT diagnostic as BLOCKED, never PASS")
    args = ap.parse_args()
    if args.min_samples < 1:
        ap.error("--min-samples must be >= 1")

    try:
        with open(args.csv_file, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [col for col in REQUIRED_COLUMNS if col not in (reader.fieldnames or [])]
            if missing:
                print(f"BLOCKED: missing columns: {', '.join(missing)}")
                return 2
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        print(f"BLOCKED: cannot read CSV: {exc}")
        return 2

    if not rows:
        print("BLOCKED: no measurements")
        return 2

    failed = []
    blocked = []
    groups = defaultdict(list)
    for lineno, row in enumerate(rows, start=2):
        case = (row["test_case"] or "").strip()
        if case not in TEST_CASES:
            failed.append(f"line {lineno}: unknown case {case!r}")
            continue
        groups[case].append((lineno, row))

    for case, (nominal, expected) in TEST_CASES.items():
        readings = groups.get(case, [])
        if len(readings) < args.min_samples:
            blocked.append(f"{case}: {len(readings)}/{args.min_samples} measurements")
        samples = set()
        for lineno, row in readings:
            def val(field):
                raw = (row[field] or "").strip()
                if not raw:
                    raise ValueError(f"no {field}")
                v = float(raw)
                if not math.isfinite(v):
                    raise ValueError(f"{field} must be finite")
                return v

            try:
                sample = int(val("sample"))
                if sample <= 0 or sample in samples:
                    failed.append(f"line {lineno}: invalid/duplicate sample {sample}")
                samples.add(sample)
            except ValueError as exc:
                blocked.append(f"line {lineno}: {exc}")

            r_raw = (row["resistance_ohm"] or "").strip()
            if nominal is None:
                if r_raw and r_raw.lower() not in {"inf", "infinity", "open"}:
                    failed.append(f"line {lineno}: open circuit should have no resistance value")
            elif not r_raw:
                blocked.append(f"line {lineno}: no measured resistance_ohm")
            else:
                try:
                    r = float(r_raw)
                    if not math.isfinite(r) or abs(r - nominal) > (KNOWN_RES_TOLERANCE * nominal if nominal else 0):
                        failed.append(f"line {lineno}: resistor {r} Ω differs >10% from {nominal} Ω")
                except ValueError:
                    failed.append(f"line {lineno}: invalid resistance_ohm {r_raw!r}")

            for adc_col in ADC_COLUMNS:
                try:
                    adc = val(adc_col)
                    if not (0 <= adc <= 3.3):
                        failed.append(f"line {lineno}: {adc_col}={adc} V out of preliminary 0..3.3 V range")
                except ValueError as exc:
                    blocked.append(f"line {lineno}: {exc}")

            try:
                val("metric")
            except ValueError as exc:
                blocked.append(f"line {lineno}: {exc}")

            logged_expected = (row["expected_state"] or "").strip().upper()
            if logged_expected != expected:
                failed.append(f"line {lineno}: expected_state={logged_expected!r}, test design requires {expected}")
            actual = (row["actual_state"] or "").strip().upper()
            if not actual:
                blocked.append(f"line {lineno}: actual_state not recorded")
            elif actual not in STATES:
                failed.append(f"line {lineno}: unknown actual_state={actual!r}")
            elif expected != "OBSERVE" and actual != expected:
                message = f"line {lineno}: {case}: expected {expected}, actual {actual}"
                if actual in {"UNAVAILABLE", "UNCALIBRATED"}:
                    # Calibration/firmware classifier is not implemented yet.
                    # It is a missing acceptance requirement, not a wrong measurement.
                    blocked.append(message + " (classifier unavailable; calibration pending)")
                elif expected == "SHORT" and args.allow_short_blocked and actual == "WET":
                    blocked.append(message + " (SHORT diagnostics not validated)")
                else:
                    failed.append(message)

    print(f"ETOR resistor bench: {len(rows)} measurements, {len(groups)} cases")
    for err in failed[:30]:
        print("FAIL:", err)
    for err in blocked[:30]:
        print("BLOCKED:", err)
    if len(failed) > 30:
        print(f"... {len(failed)-30} more failures")
    if len(blocked) > 30:
        print(f"... {len(blocked)-30} more missing requirements")
    if failed:
        print(f"OVERALL: FAIL ({len(failed)} failures; {len(blocked)} blocked observations)")
        return 1
    if blocked:
        print(f"OVERALL: BLOCKED ({len(blocked)} missing/insufficient observations)")
        return 2
    print("OVERALL: PASS — test vectors met; field calibration still required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
