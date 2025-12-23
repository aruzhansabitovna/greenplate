#!/usr/bin/env python3
"""
parse_menu.py — GreenPlate weekly menu parser (Mon–Fri) from a university PDF.

Usage (GitHub Actions):
    python3 parse_menu.py menu.pdf menu.json

Requirements:
    pip install pdfplumber
"""

from __future__ import annotations
import sys, json, re
import datetime as dt
from typing import Dict, List, Optional, Tuple

import pdfplumber


DAY_MAP = {
    "PAZARTESİ": "Monday",
    "PAZARTESI": "Monday",
    "SALI": "Tuesday",
    "ÇARŞAMBA": "Wednesday",
    "CARSAMBA": "Wednesday",
    "PERŞEMBE": "Thursday",
    "PERSEMBE": "Thursday",
    "CUMA": "Friday",
}
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _norm(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = re.sub(r"[ \t]+", " ", s)
    s = s.replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _cell_to_items(cell: str) -> List[str]:
    cell = _norm(cell)
    if not cell:
        return []
    cell = cell.replace("•", " ").strip()

    # In these PDFs, a cell may contain a line break but still be one dish name.
    lines = [ln.strip() for ln in cell.split("\n") if ln.strip()]
    if len(lines) <= 1:
        return [cell]

    # If the first line has "/" it’s usually a continuation (keep as one)
    if "/" in lines[0]:
        return [" ".join(lines)]

    # Default: join lines into one dish name
    return [" ".join(lines)]


def _score_table(table: List[List[str]]) -> int:
    if not table:
        return -10
    max_cols = max((len(r) for r in table if r), default=0)
    score = 0
    if max_cols >= 5:
        score += 10
    # reward day headers presence
    for r in table[:6]:
        rr = [_norm(c).upper() for c in r if c]
        for d in DAY_MAP:
            if d in rr:
                score += 5
    score += min(len(table), 30)
    return score


def extract_menu_from_pdf(pdf_path: str) -> Tuple[Dict[str, List[str]], Optional[str]]:
    days: Dict[str, List[str]] = {d: [] for d in DAYS_EN}
    date_range: Optional[str] = None

    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return days, date_range

        page = pdf.pages[0]

        # Try to read date range like 8.12.2025/12.12.2025
        text = _norm(page.extract_text() or "")
        m = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4}\s*/\s*\d{1,2}\.\d{1,2}\.\d{4})", text)
        if m:
            date_range = m.group(1).replace(" ", "")

        settings_variants = [
            dict(vertical_strategy="lines", horizontal_strategy="lines", intersection_tolerance=5),
            dict(vertical_strategy="lines", horizontal_strategy="text", intersection_tolerance=5),
            dict(vertical_strategy="text", horizontal_strategy="lines", intersection_tolerance=5),
        ]

        best_table = None
        best_score = -10

        for settings in settings_variants:
            try:
                tables = page.extract_tables(table_settings=settings) or []
            except Exception:
                tables = []
            for t in tables:
                sc = _score_table(t)
                if sc > best_score:
                    best_score = sc
                    best_table = t

        if not best_table:
            try:
                t = page.extract_table()  # fallback
                if t:
                    best_table = t
            except Exception:
                best_table = None

        if not best_table:
            return days, date_range

        # Find header row that contains day names
        header_row_idx = None
        for i, row in enumerate(best_table[:10]):
            r = [_norm(c).upper() for c in row]
            hits = sum(1 for k in DAY_MAP if k in r)
            if hits >= 3:
                header_row_idx = i
                break
        if header_row_idx is None:
            header_row_idx = 0

        # Map day -> column index
        col_idx_for_day: Dict[str, int] = {}
        hdr = best_table[header_row_idx]
        hdr_norm = [_norm(c).upper() for c in hdr]
        for j, cell in enumerate(hdr_norm):
            if cell in DAY_MAP:
                col_idx_for_day[DAY_MAP[cell]] = j

        # If mapping incomplete, assume first 5 columns are Mon..Fri
        if len(col_idx_for_day) < 5:
            col_idx_for_day = {DAYS_EN[k]: k for k in range(5)}

        # Read content rows
        for row in best_table[header_row_idx + 1 :]:
            if not row or sum(1 for c in row if _norm(c)) <= 1:
                continue

            row_cells = list(row) + [""] * (5 - len(row))

            for day_en in DAYS_EN:
                j = col_idx_for_day.get(day_en)
                if j is None or j >= len(row_cells):
                    continue

                for dish in _cell_to_items(row_cells[j]):
                    dish = _norm(dish)
                    if not dish:
                        continue
                    up = dish.upper()

                    # Skip obvious non-dish labels
                    if up.startswith("ÖĞRENCİ") or up.startswith("PERSONEL"):
                        continue
                    if up.startswith("ASÇIBAŞI") or up.startswith("NOT:"):
                        continue
                    if dish not in days[day_en]:
                        days[day_en].append(dish)

        # extra safety: remove any accidental day tokens
        for d in DAYS_EN:
            days[d] = [x for x in days[d] if _norm(x).upper() not in DAY_MAP]

    return days, date_range


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python3 parse_menu.py <menu.pdf> <menu.json>", file=sys.stderr)
        return 2

    pdf_path = sys.argv[1]
    out_path = sys.argv[2]

    days, date_range = extract_menu_from_pdf(pdf_path)

    payload = {
        "updated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "pdf_filename": "menu.pdf",
        "date_range": date_range,
        "days": days,  # Monday..Friday only
        "notes": "Parsed from official weekly PDF (table extraction).",
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Wrote", out_path)
    for d in DAYS_EN:
        print(f"{d}: {len(days[d])} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
