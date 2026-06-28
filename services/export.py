"""
services/export.py — CSV and JSON export for the philosopher archive.

Called from the File menu in main_window.py. Returns (success, message).

JSON exports are *complete backups*: each philosopher's portrait and every
attached work file are embedded as base64, so a JSON export can be re-imported
on another machine and restore the pictures and files exactly. CSV stays a
lightweight, human-readable summary (work titles only — no embedded files).
"""

import csv
import json
import os
import base64
from database import get_all_philosophers, get_works
import library


def export_csv(path: str) -> tuple[bool, str]:
    """Export all philosophers (one row each) plus their quotes and work titles."""
    try:
        philosophers = get_all_philosophers()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow([
                "Name", "Birth Year", "Death Year",
                "Birth City", "Birth Country", "Era",
                "Teachers", "Contributions", "Quotes", "Works"
            ])
            for p in philosophers:
                quotes_joined = " | ".join(q.text for q in p.quotes)
                works_joined = " | ".join(w.title for w in get_works(p.id))
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
                    works_joined,
                ])
        return True, f"Exported {len(philosophers)} philosophers to:\n{path}"
    except Exception as e:
        return False, f"Export failed: {e}"


def _encode_file(rel: str) -> tuple[str, str] | tuple[None, None]:
    """Return (base64_data, ext) for a stored file, or (None, None) if missing."""
    data = library.read_bytes(rel)
    if data is None:
        return None, None
    ext = os.path.splitext(rel)[1].lstrip(".").lower() or "bin"
    return base64.b64encode(data).decode("ascii"), ext


def export_json(path: str) -> tuple[bool, str]:
    """Export all philosophers — with portraits and work files — to a JSON backup."""
    try:
        philosophers = get_all_philosophers()
        data = []
        embedded_files = 0
        for p in philosophers:
            # Portrait (base64) — a complete, restorable copy
            portrait_obj = None
            if p.portrait_path:
                b64, ext = _encode_file(p.portrait_path)
                if b64 is not None:
                    portrait_obj = {"ext": ext, "data": b64}
                    embedded_files += 1

            # Works, each with its file embedded when present
            works_data = []
            for w in get_works(p.id):
                wobj = {"title": w.title}
                if w.has_file:
                    fb = library.read_bytes(w.file_path)
                    if fb is not None:
                        wobj["filename"] = w.original_filename or os.path.basename(w.file_path)
                        wobj["file_data"] = base64.b64encode(fb).decode("ascii")
                        embedded_files += 1
                works_data.append(wobj)

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
                "portrait": portrait_obj,
                "quotes": [
                    {"id": q.id, "text": q.text, "is_favourite": q.is_favourite}
                    for q in p.quotes
                ],
                "works": works_data,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"philosophers": data}, f, ensure_ascii=False, indent=2)
        extra = f" (including {embedded_files} embedded file(s))" if embedded_files else ""
        return True, f"Exported {len(philosophers)} philosophers to:\n{path}{extra}"
    except Exception as e:
        return False, f"Export failed: {e}"
