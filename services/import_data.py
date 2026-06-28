"""
services/import_data.py — JSON and CSV import for the philosopher archive.

Import strategy: FULL REPLACE.
The entire database is cleared and rebuilt from the import file.
Whatever is in the file wins — no conflict resolution, no merging.
This mirrors how a database restore works.

Called from the File menu in main_window.py.
Returns (ok: bool, message: str).
"""

import csv
import json
import base64

from database import (
    Philosopher,
    add_philosopher_with_quotes,
    clear_all_philosophers,
    set_portrait,
    save_works,
)


# ─── JSON import ─────────────────────────────────────────────────────────────

def import_json(path: str) -> tuple[bool, str]:
    """Replace the entire database with philosophers from a Chronosophy JSON export.

    Expected structure (matches export_json output):
    {
      "philosophers": [
        {
          "name":          "...",
          "birth_year":    int,
          "death_year":    int | null,
          "birth_city":    "...",
          "birth_country": "...",
          "era":           "...",   <- computed field, ignored on import
          "teachers":      "...",
          "contributions": "...",
          "quotes": [
            {"id": int, "text": "...", "is_favourite": bool}
          ]
        },
        ...
      ]
    }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "philosophers" not in data:
            return False, (
                "Invalid file format.\n"
                "Expected a Chronosophy JSON export with a top-level "
                "\"philosophers\" array."
            )

        records = data["philosophers"]
        if not isinstance(records, list):
            return False, "Invalid file format: 'philosophers' must be an array."

        # ── Validate first so we don't wipe the DB on a bad file ────────────
        errors = _validate_json_records(records)
        if errors:
            return False, (
                "Import aborted — file contains errors (database unchanged):\n\n"
                + "\n".join(f"  • {e}" for e in errors[:10])
                + (f"\n  … and {len(errors) - 10} more" if len(errors) > 10 else "")
            )

        # ── All good — replace ───────────────────────────────────────────────
        clear_all_philosophers()

        added = 0
        errors = []
        for idx, rec in enumerate(records, start=1):
            try:
                _insert_json_record(rec)
                added += 1
            except Exception as exc:
                errors.append(f"Record {idx} ({rec.get('name', '?')}): {exc}")

        msg = f"Import complete.\n  ✓  {added} philosopher(s) imported."
        if errors:
            msg += f"\n  ✕  {len(errors)} error(s):\n"
            msg += "\n".join(f"      • {e}" for e in errors)
        return True, msg

    except json.JSONDecodeError as exc:
        return False, f"Could not parse JSON file:\n{exc}"
    except OSError as exc:
        return False, f"Could not open file:\n{exc}"
    except Exception as exc:
        return False, f"Import failed unexpectedly:\n{exc}"


def _validate_json_records(records: list) -> list[str]:
    """Return a list of error strings for any records missing required fields.
    Called before touching the database so nothing is wiped on a corrupt file."""
    errors = []
    for idx, rec in enumerate(records, start=1):
        name = str(rec.get("name", "")).strip()
        if not name:
            errors.append(f"Record {idx}: missing name")
            continue
        try:
            _parse_int(rec.get("birth_year"), required=True)
        except ValueError as exc:
            errors.append(f"Record {idx} ({name}): {exc}")
    return errors


def _insert_json_record(rec: dict) -> None:
    """Build a Philosopher (+ quotes, portrait, works) from a JSON record and insert it."""
    p = Philosopher(
        id=0,
        name=str(rec["name"]).strip(),
        birth_year=_parse_int(rec.get("birth_year"), required=True),
        death_year=_parse_int(rec.get("death_year"), required=False),
        birth_city=str(rec.get("birth_city", "")).strip(),
        birth_country=str(rec.get("birth_country", "")).strip(),
        teachers=str(rec.get("teachers", "")).strip(),
        contributions=str(rec.get("contributions", "")).strip(),
    )

    quotes = []
    for q in rec.get("quotes", []):
        if isinstance(q, dict):
            text   = str(q.get("text", "")).strip()
            is_fav = bool(q.get("is_favourite", False))
        else:
            text   = str(q).strip()
            is_fav = False
        if text:
            quotes.append({"text": text, "is_favourite": is_fav})

    pid = add_philosopher_with_quotes(p, quotes)

    # Restore the portrait (base64) if the backup carried one
    portrait = rec.get("portrait")
    if isinstance(portrait, dict) and portrait.get("data"):
        try:
            data = base64.b64decode(portrait["data"])
            set_portrait(pid, data, str(portrait.get("ext", "png")))
        except Exception:
            pass   # a corrupt image must not abort the whole import

    # Restore works + any embedded files
    specs = []
    for w in rec.get("works", []):
        if not isinstance(w, dict):
            continue
        title = str(w.get("title", "")).strip()
        if not title:
            continue
        spec = {"id": None, "title": title, "file": "none"}
        if w.get("file_data"):
            try:
                spec["data"] = base64.b64decode(w["file_data"])
                spec["filename"] = str(w.get("filename", "file"))
                spec["file"] = "bytes"
            except Exception:
                spec["file"] = "none"
        specs.append(spec)
    if specs:
        save_works(pid, specs)


# ─── CSV import ──────────────────────────────────────────────────────────────

_CSV_COLUMNS = [
    "Name", "Birth Year", "Death Year",
    "Birth City", "Birth Country", "Era",
    "Teachers", "Contributions", "Quotes",
]

_QUOTE_SEP = " | "   # matches export_csv


def import_csv(path: str) -> tuple[bool, str]:
    """Replace the entire database with philosophers from a Chronosophy CSV export.

    Expected columns (matches export_csv output):
        Name, Birth Year, Death Year, Birth City, Birth Country,
        Era, Teachers, Contributions, Quotes

    Multiple quotes are pipe-separated (" | ") in the Quotes column.
    The Era column is derived and ignored on import.
    CSV exports do not store is_favourite, so all imported quotes are
    non-favourited by default.
    """
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return False, "The CSV file appears to be empty."

            actual_cols = [c.strip() for c in reader.fieldnames]
            missing = [c for c in _CSV_COLUMNS if c not in actual_cols]
            if missing:
                return False, (
                    "CSV is missing required columns: " + ", ".join(missing)
                    + "\n\nExpected:\n" + ", ".join(_CSV_COLUMNS)
                )

            rows = list(reader)   # read all rows before touching the DB

        # ── Validate ─────────────────────────────────────────────────────────
        errors = _validate_csv_rows(rows)
        if errors:
            return False, (
                "Import aborted — file contains errors (database unchanged):\n\n"
                + "\n".join(f"  • {e}" for e in errors[:10])
                + (f"\n  … and {len(errors) - 10} more" if len(errors) > 10 else "")
            )

        # ── Replace ───────────────────────────────────────────────────────────
        clear_all_philosophers()

        added = 0
        errors = []
        for idx, row in enumerate(rows, start=2):
            try:
                _insert_csv_row(row)
                added += 1
            except Exception as exc:
                errors.append(f"Row {idx} ({row.get('Name', '?')}): {exc}")

        msg = f"Import complete.\n  ✓  {added} philosopher(s) imported."
        if errors:
            msg += f"\n  ✕  {len(errors)} error(s):\n"
            msg += "\n".join(f"      • {e}" for e in errors)
        return True, msg

    except OSError as exc:
        return False, f"Could not open file:\n{exc}"
    except Exception as exc:
        return False, f"Import failed unexpectedly:\n{exc}"


def _validate_csv_rows(rows: list) -> list[str]:
    errors = []
    for idx, row in enumerate(rows, start=2):
        name = str(row.get("Name", "")).strip()
        if not name:
            errors.append(f"Row {idx}: missing name")
            continue
        try:
            _parse_int(row.get("Birth Year"), required=True)
        except ValueError as exc:
            errors.append(f"Row {idx} ({name}): {exc}")
    return errors


def _insert_csv_row(row: dict) -> None:
    death_raw = str(row.get("Death Year", "")).strip()

    p = Philosopher(
        id=0,
        name=str(row["Name"]).strip(),
        birth_year=_parse_int(row.get("Birth Year"), required=True),
        death_year=int(death_raw) if death_raw else None,
        birth_city=str(row.get("Birth City", "")).strip(),
        birth_country=str(row.get("Birth Country", "")).strip(),
        teachers=str(row.get("Teachers", "")).strip(),
        contributions=str(row.get("Contributions", "")).strip(),
    )

    quotes = []
    for text in str(row.get("Quotes", "")).split(_QUOTE_SEP):
        text = text.strip()
        if text:
            quotes.append({"text": text, "is_favourite": False})

    pid = add_philosopher_with_quotes(p, quotes)

    # "Works" is an optional column (older CSVs predate it). Titles only — CSV
    # cannot carry the attached files.
    specs = []
    for title in str(row.get("Works", "")).split(_QUOTE_SEP):
        title = title.strip()
        if title:
            specs.append({"id": None, "title": title, "file": "none"})
    if specs:
        save_works(pid, specs)


# ─── Shared helper ────────────────────────────────────────────────────────────

def _parse_int(value, required: bool = False) -> int | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError("required integer field is empty")
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        if required:
            raise ValueError(f"expected integer, got {value!r}")
        return None
