#!/usr/bin/env python3
"""Interactive ETOR resistor-bench acquisition from ESPHome serial diagnostics.

ESPHome firmware is expected to emit one complete measurement per line:
    ETOR_SAMPLE:{"seq":1,"adc_a_forward_v":1.1,"adc_b_forward_v":2.2,
                 "adc_a_reverse_v":2.3,"adc_b_reverse_v":1.2,
                 "metric":0.7,"actual_state":"DRY"}

The script NEVER fabricates sensor readings. The firmware MUST publish a fresh
line after each complete forward/reverse electrode measurement.

Usage:
    python3 tests/capture_etor_serial.py --port /dev/cu.usbserial-210 \
        --output results/etor_run.csv
    python3 tests/capture_etor_serial.py --input-log tests/fixtures/log.txt \
        --cases dry_2m2 --samples 2 --output results/sample.csv

Requires pyserial only when using --port: python3 -m pip install pyserial
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from pathlib import Path

FIELDS = [
    "test_case", "resistance_ohm", "sample",
    "adc_a_forward_v", "adc_b_forward_v",
    "adc_a_reverse_v", "adc_b_reverse_v", "metric",
    "expected_state", "actual_state", "notes",
]
ADC_FIELDS = FIELDS[3:7]
MEASUREMENT_FIELDS = ADC_FIELDS + ["metric"]
CASES = [
    ("open", None, "OBSERVE", "Обрыв"),
    ("dry_2m2", 2200000, "DRY", "2,2 МОм"),
    ("dry_1m", 1000000, "OBSERVE", "1 МОм"),
    ("trans_220k", 220000, "OBSERVE", "220 кОм"),
    ("trans_150k", 150000, "OBSERVE", "150 кОм"),
    ("trans_100k", 100000, "OBSERVE", "100 кОм"),
    ("wet_47k", 47000, "WET", "47 кОм"),
    ("wet_10k", 10000, "WET", "10 кОм"),
    ("short_47", 47, "SHORT", "47 Ом"),
    ("dry_2m2_repeat", 2200000, "DRY", "2,2 МОм повторно"),
]
CASE_BY_ID = {x[0]: x for x in CASES}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PREFIX = "ETOR_SAMPLE:"
STATES = {"DRY", "WET", "SHORT", "FAULT", "UNAVAILABLE"}


def parse_sample(line: str):
    """Parse only firmware-emitted structured measurement lines, not ESPHome chatter."""
    line = ANSI.sub("", line)
    index = line.find(PREFIX)
    if index < 0:
        return None
    payload = line[index + len(PREFIX):].strip()
    obj = json.loads(payload)
    if not isinstance(obj, dict):
        raise ValueError("ETOR_SAMPLE JSON must be an object")
    if "seq" not in obj or isinstance(obj["seq"], bool):
        raise ValueError("ETOR_SAMPLE must contain integer seq")
    seq = int(obj["seq"])
    if seq < 0 or str(seq) != str(obj["seq"]):
        raise ValueError("seq must be a nonnegative integer")
    validated = {"seq": seq}
    for field in MEASUREMENT_FIELDS:
        if field not in obj:
            raise ValueError(f"missing {field}")
        value = float(obj[field])
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite")
        if field in ADC_FIELDS and not (0 <= value <= 3.3):
            raise ValueError(f"{field}={value} is outside preliminary 0..3.3 V range")
        validated[field] = value
    state = str(obj.get("actual_state", "")).strip().upper()
    if state and state not in STATES:
        raise ValueError(f"unknown actual_state={state}")
    validated["actual_state"] = state
    return validated


def select_cases(arg):
    names = arg.split(",") if arg else [x[0] for x in CASES]
    names = [x.strip() for x in names if x.strip()]
    if not names or len(names) != len(set(names)):
        raise ValueError("empty or duplicate --cases")
    unknown = [x for x in names if x not in CASE_BY_ID]
    if unknown:
        raise ValueError("unknown case(s): " + ", ".join(unknown))
    return [CASE_BY_ID[x] for x in names]


def collect_lines_from_serial(port, baud):
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial not installed; run python3 -m pip install pyserial") from exc
    return serial.Serial(port, baudrate=baud, timeout=0.3)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--port", help="USB-UART macOS port, e.g. /dev/cu.usbserial-210")
    input_group.add_argument("--input-log", help="Replay existing serial log for a parser dry-run")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--cases", help="Comma-separated case IDs; default is full T-29 sequence")
    p.add_argument("--samples", type=int, default=10, help="Fresh cycles per case (default: 10)")
    p.add_argument("--timeout", type=float, default=180, help="Wait for each case, in seconds")
    p.add_argument("--output", default="results/etor_run.csv")
    p.add_argument("--non-interactive", action="store_true",
                   help="For --input-log testing only; use nominal resistor values")
    args = p.parse_args(argv)
    if args.samples < 1 or args.timeout <= 0 or args.baud <= 0:
        p.error("--samples, --timeout, --baud must be positive")
    if args.non_interactive and not args.input_log:
        p.error("--non-interactive requires --input-log")
    try:
        cases = select_cases(args.cases)
    except ValueError as exc:
        p.error(str(exc))
    output = Path(args.output)
    if output.exists():
        p.error(f"output exists: {output}; choose a new file (never overwrite recorded results)")
    output.parent.mkdir(parents=True, exist_ok=True)

    link = None
    try:
        if args.port:
            link = collect_lines_from_serial(args.port, args.baud)
            print(f"Открыт {args.port} @ {args.baud}. Закройте miniterm и другие программы.")
        else:
            link = open(args.input_log, "rb")

        total = 0
        blocked = 0
        with output.open("x", newline="", encoding="utf-8") as dest:
            writer = csv.DictWriter(dest, fieldnames=FIELDS)
            writer.writeheader()
            dest.flush()
            for case, nominal, expected, description in cases:
                print(f"\n[{case}] Подключите {description} между входами ETOR A/B.")
                print("Выключите 24 В нагревателя и внешний контактор; меняйте резистор при выключенном питании.")
                if args.non_interactive:
                    measured = nominal
                else:
                    answer = input("Измеренное сопротивление, Ом (Enter=номинал, для обрыва Enter): ").strip()
                    try:
                        measured = float(answer) if answer else nominal
                    except ValueError:
                        print("Неверное сопротивление; остановлено без выдумывания значения.")
                        return 2
                    if measured is not None and (not math.isfinite(measured) or measured <= 0):
                        print("Неверное сопротивление; остановлено.")
                        return 2
                    input("Включите питание, дождитесь ESPHome и нажмите Enter для начала записи... ")
                # Flush buffered logs from the previous case, but not from a replay file.
                if args.port:
                    link.reset_input_buffer()

                seen = set()
                count = 0
                deadline = time.monotonic() + args.timeout
                print(f"Ожидаю {args.samples} новых ETOR_SAMPLE...")
                while count < args.samples and time.monotonic() < deadline:
                    raw = link.readline()
                    if not raw:
                        if args.input_log:
                            break  # EOF
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    if PREFIX not in line:
                        continue
                    try:
                        sample = parse_sample(line)
                    except (ValueError, TypeError, json.JSONDecodeError) as exc:
                        print(f"  Некорректная диагностическая строка: {exc}")
                        continue
                    if sample["seq"] in seen:
                        continue
                    seen.add(sample["seq"])
                    count += 1
                    row = {
                        "test_case": case,
                        "resistance_ohm": "" if measured is None else measured,
                        "sample": count,
                        "expected_state": expected,
                        "notes": f"seq={sample['seq']}; source={'serial' if args.port else 'replay'}",
                    }
                    for field in MEASUREMENT_FIELDS + ["actual_state"]:
                        row[field] = sample[field]
                    writer.writerow(row)
                    dest.flush()
                    total += 1
                    print(f"  {count}/{args.samples}: seq={sample['seq']}, "
                          f"metric={sample['metric']}, state={sample['actual_state'] or 'UNREPORTED'}")
                if count != args.samples:
                    blocked += 1
                    print(f"BLOCKED: {case} — получено {count}/{args.samples} свежих циклов.")
                    if args.input_log:
                        print("Воспроизведение файла завершено; другие тесты не начнутся.")
                        break
        print(f"\nЗаписано {total} настоящих измерений в {output}")
        if blocked:
            print("BLOCKED: некоторые случаи не собрали нужного числа циклов.")
            return 2
        print("Сбор завершён. Теперь запустите tests/check_etor_simulation.py для оценки.")
        return 0
    except (OSError, RuntimeError, KeyboardInterrupt) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    finally:
        if link is not None:
            link.close()


if __name__ == "__main__":
    sys.exit(main())
