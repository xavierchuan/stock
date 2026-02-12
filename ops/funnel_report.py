#!/usr/bin/env python3
import csv
import sys
from collections import Counter


def pct(num, den):
    if den == 0:
        return "0.00%"
    return f"{(num / den) * 100:.2f}%"


def to_bool(v):
    return str(v).strip() in {"1", "true", "True", "YES", "yes"}


def has_value(v):
    return str(v).strip() != ""


def main(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total = len(rows)
    if total == 0:
        print("No lead data found.")
        return

    trial_sent = sum(to_bool(r.get("trial_sent", 0)) for r in rows)
    opened = sum(
        to_bool(r.get("opened_success", 0)) or has_value(r.get("trial_opened_at", ""))
        for r in rows
    )
    limit_hit = sum(to_bool(r.get("limit_hit", 0)) for r in rows)
    followup = sum(to_bool(r.get("followup_24h", 0)) for r in rows)
    tripwire = sum(to_bool(r.get("tripwire_paid", 0)) for r in rows)
    main_paid = sum(to_bool(r.get("main_paid", 0)) for r in rows)
    refunded = sum(to_bool(r.get("refund_flag", 0)) for r in rows)

    status_counter = Counter(r.get("status", "UNKNOWN") for r in rows)

    print("=== Funnel Report ===")
    print(f"Total leads: {total}")
    print(f"Trial sent: {trial_sent} ({pct(trial_sent, total)})")
    print(f"Trial opened: {opened} ({pct(opened, total)})")
    print(f"Limit hit: {limit_hit} ({pct(limit_hit, total)})")
    print(f"24h follow-up done: {followup} ({pct(followup, total)})")
    print(f"Tripwire paid (19-39): {tripwire} ({pct(tripwire, total)})")
    print(f"Main paid (299): {main_paid} ({pct(main_paid, total)})")
    print(f"Refunded: {refunded} ({pct(refunded, total)})")
    print()
    print("=== Key Conversion ===")
    print(f"Comment -> DM proxy (trial_sent / total): {pct(trial_sent, total)}")
    print(f"Trial sent -> Trial opened (opened / trial_sent): {pct(opened, trial_sent)}")
    print(f"Trial opened -> 19-39 (tripwire / opened): {pct(tripwire, opened)}")
    print(f"19-39 -> 299 (main_paid / tripwire): {pct(main_paid, tripwire)}")
    print()
    print("=== Status Distribution ===")
    for k, v in sorted(status_counter.items()):
        print(f"{k}: {v}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 funnel_report.py <lead_csv_path>")
        sys.exit(1)
    main(sys.argv[1])
