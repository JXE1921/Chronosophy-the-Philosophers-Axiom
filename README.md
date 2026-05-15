# Philosopher Timeline & Daily Wisdom System

A premium dark-themed desktop application for exploring the history of philosophy.

---

## Quick Start

### 1. Install dependencies

```bash
pip install PyQt6
```

### 2. Run the application

```bash
python main.py
```

The database (`philosophers.db`) is created automatically on first run and seeded
with 15 philosophers.

---

## Features

| Feature | Details |
|---|---|
| **Daily Quote** | Rotates once per day from all stored quotes; refresh button for instant new quote |
| **Timeline View** | Horizontal scrollable canvas with proportional year positioning and era colour bands |
| **Country View** | Card grid grouped by country with colour-coded sections |
| **Search & Filter** | Live search by name, filter by country or era, sort by lifespan or name |
| **CRUD** | Add, edit, delete philosophers with multiple quotes per philosopher |
| **Persistence** | SQLite database survives between sessions |

---

## Project Structure

```
philosopher_timeline/
├── main.py                  # Entry point
├── database.py              # All SQLite logic + data classes
├── styles.py                # Dark theme colour tokens + QSS stylesheet
├── requirements.txt
└── ui/
    ├── main_window.py       # Root window — orchestrates all views
    ├── quote_widget.py      # Daily wisdom panel (custom painted)
    ├── timeline_widget.py   # Chronological canvas (custom painted)
    ├── country_widget.py    # Country card view
    ├── search_bar.py        # Filter / sort toolbar
    ├── philosopher_form.py  # Add / Edit dialog
    └── detail_dialog.py     # Read-only detail view
```

---

## Database Schema

```sql
philosophers  (id, name, birth_year, death_year, birth_city, birth_country,
               teachers, contributions)

quotes        (id, philosopher_id FK, text)

daily_quote   (id=1, quote_id, selected_on)   -- singleton row
```

---

## Keyboard Shortcuts

| Action | Shortcut |
|---|---|
| Add philosopher | Click **＋ Add Philosopher** button |
| View details | Double-click sidebar item or click timeline/card |
| Edit | Select item → click **✏ Edit** |
| Delete | Select item → click **✕** |

---

## Extending the App

- **New fields** — add columns to `philosophers` table in `database.py`, update
  `Philosopher` dataclass, and add inputs in `philosopher_form.py`
- **New views** — add a new widget in `ui/`, import in `main_window.py`, and add
  a tab in `_build_tabs()`
- **Map view** — install `folium` or `plotly` and render into a `QWebEngineView`
  replacing the country cards
- **Export** — add a menu bar with CSV/PDF export in `main_window.py`

---

## Dependencies

- **PyQt6** — GUI framework (LGPL licensed)
- **sqlite3** — standard library, no install needed
- Python 3.10+ required (uses `int | None` union syntax)
