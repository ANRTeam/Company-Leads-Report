#!/usr/bin/env python3
"""
Angi Leads Report Generator (CLI)
==================================
Reads an "Angi Leads" CRM export (CSV) and writes a styled HTML report.

USAGE:
    python3 generate_angi_report.py <input_csv> [output_html]

Example:
    python3 generate_angi_report.py Export_Contacts_Angi_Leads_Aug_2026_11_52_AM.csv angi_report.html

Business assumptions (fake-lead definitions, loss-reason grouping, column
names, etc.) live in angi_report_lib.py's CONFIG section.
"""

import sys
from pathlib import Path
import pandas as pd

from angi_report_lib import COL, build_report, render_html


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_angi_report.py <input_csv> [output_html]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".report.html")

    df = pd.read_csv(input_path, encoding="utf-8-sig", dtype=str)

    missing = [name for name in COL.values() if name not in df.columns]
    if missing:
        print(f"WARNING: the following expected columns are missing from the CSV: {missing}")

    data = build_report(df)
    html = render_html(data, input_path.name)

    output_path.write_text(html, encoding="utf-8")
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
