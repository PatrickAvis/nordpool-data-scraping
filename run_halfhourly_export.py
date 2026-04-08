"""
Convenience runner for multi-day half-hourly CSV output.

Usage:
    python run_halfhourly_export.py
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta

from scrape_n2ex_prices import write_pivot_excel


def main() -> None:
    # Date window: last 7 days through tomorrow.
    days_back = 7
    days_forward = 1

    # Change these defaults if needed.
    aggregation = "Hourly"
    delivery_areas = "UK"
    currency = "GBP"
    output_csv = "prices_halfhourly_window.csv"
    output_pivot = "prices_pivot.xlsx"
    fieldnames = ["start_dt", "deliverydate", "start_t", "settlement_period", "price_gbp_mwh"]

    all_rows: list[dict[str, str]] = []
    today = date.today()

    for offset in range(-days_back, days_forward + 1):
        delivery_date = (today + timedelta(days=offset)).isoformat()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        cmd = [
            sys.executable,
            "scrape_n2ex_prices.py",
            "--delivery-date",
            delivery_date,
            "--aggregation",
            aggregation,
            "--delivery-areas",
            delivery_areas,
            "--currency",
            currency,
            "--use-edge",
            "--half-hourly",
            "-o",
            tmp_path,
        ]
        try:
            subprocess.run(cmd, check=True)
            with open(tmp_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                all_rows.extend(reader)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    all_rows.sort(key=lambda r: (r["start_dt"], r["deliverydate"], r["start_t"]))
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    write_pivot_excel(all_rows, output_pivot)
    print(
        f"Wrote {output_csv} and {output_pivot} with {len(all_rows)} rows "
        f"for {days_back} days back through +{days_forward} day."
    )


if __name__ == "__main__":
    main()
