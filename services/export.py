"""
services/export.py — CSV and JSON export for the philosopher archive.

Called from the File menu in main_window.py. Returns (success, message).
"""

import csv
import json
import os
from database import get_all_philosophers, Philosopher


def export_csv(path: str) -> tuple[bool, str]:
    """Export all philosophers (one row each) plus their quotes as a pipe-separated list."""
    try:
        philosophers = get_all_philosophers()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow([
                "Name", "Birth Year", "Death Year",
                "Birth City", "Birth Country", "Era",
                "Teachers", "Contributions", "Quotes"
            ])
            for p in philosophers:
                quotes_joined = " | ".join(q.text for q in p.quotes)
                writer.writerow([
                    p.name,
                    p.birth_year,
                    p.death_year if p.death_year is not None else "",
                    p.birth_city,
                    p.birth_country,
                    p.era,
                    p.teachers,
                    p.contributions,
                    quotes_joined,
                ])
        return True, f"Exported {len(philosophers)} philosophers to:\n{path}"
    except Exception as e:
        return False, f"Export failed: {e}"


def export_json(path: str) -> tuple[bool, str]:
    """Export all philosophers with full quote objects to a structured JSON file."""
    try:
        philosophers = get_all_philosophers()
        data = []
        for p in philosophers:
            data.append({
                "id": p.id,
                "name": p.name,
                "birth_year": p.birth_year,
                "death_year": p.death_year,
                "birth_city": p.birth_city,
                "birth_country": p.birth_country,
                "era": p.era,
                "teachers": p.teachers,
                "contributions": p.contributions,
                "quotes": [
                    {"id": q.id, "text": q.text, "is_favourite": q.is_favourite}
                    for q in p.quotes
                ],
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"philosophers": data}, f, ensure_ascii=False, indent=2)
        return True, f"Exported {len(philosophers)} philosophers to:\n{path}"
    except Exception as e:
        return False, f"Export failed: {e}"
