# Chronosophy — The Philosopher's Axiom  ·  v5

A premium dark-themed desktop application for exploring the history of philosophy.
Custom-painted views, a force-directed influence graph, a painted world map,
quote favouriting, export, and a daily wisdom widget with smooth fade transitions.

---

## Quick Start

### 1. Install dependencies

```bash
pip install PyQt6
```

### 2. Run

```bash
python main.py
```

The database (`philosophers.db`) is created automatically on first run and seeded
with 15 philosophers. Existing v1 databases are migrated automatically — all your
data is preserved.

---

## What's New in v5

| Feature | Details |
|---|---|
| **Influence Graph** | Force-directed node graph of teacher → student links. Drag nodes, zoom, re-layout. |
| **World Map** | Custom-painted stylised world map. Dots per country; click a dot to filter. |
| **Statistics tab** | Summary tiles, era & country bar charts, top-quoted list. |
| **Timeline zoom** | `Ctrl + Scroll` to zoom the timeline; `+/−` buttons and a log-scale slider in the legend bar. |
| **Timeline tooltips** | Hover a philosopher bar to see a contribution preview. |
| **Animated quotes** | "New Quote" now fades the panel out → in (wired `QPropertyAnimation`). |
| **Quote favourites** | Heart (♥) button on the daily widget and each quote card. |
| **Favourites filter** | Search bar checkbox to show only philosophers with favourited quotes. |
| **Comparison dialog** | Select any two philosophers in the sidebar → click Compare. |
| **"Show in Graph"** | Button in the detail view switches to the graph tab and centres the node. |
| **Menu bar** | File → Export CSV / JSON, View → Fullscreen / tabs, Help → Shortcuts / About. |
| **Export** | CSV and JSON export via File menu (`Ctrl+E`). |
| **Keyboard shortcuts** | Full reference in Help → Keyboard Shortcuts. |

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + N` | Add philosopher |
| `Ctrl + F` | Focus search bar |
| `Ctrl + E` | Export to CSV |
| `Ctrl + 1 – 5` | Switch tab (Timeline / Country / Graph / Map / Stats) |
| `Ctrl + Scroll` | Zoom timeline |
| `F11` | Toggle fullscreen |
| `Delete` | Delete selected philosopher |
| `Double-click` | Open detail view |

---

## Project Structure

```
chronosophy/
├── main.py                      # Entry point
├── database.py                  # SQLite layer + data classes
├── styles.py                    # Colour tokens + QSS stylesheet
├── requirements.txt
├── README.md
├── philosophers.db              # Created / migrated on first run
├── ui/
│   ├── main_window.py           # Root window — orchestrates everything
│   ├── quote_widget.py          # Daily wisdom panel (fade animation + favouriting)
│   ├── timeline_widget.py       # Chronological canvas (zoom / pan / tooltips)
│   ├── country_widget.py        # Country card grid
│   ├── influence_graph.py       # Force-directed teacher → student graph
│   ├── world_map.py             # Custom-painted world map (no browser dependency)
│   ├── statistics_view.py       # Aggregate insights tab
│   ├── search_bar.py            # Filter / sort / favourites toolbar
│   ├── philosopher_form.py      # Add / Edit dialog
│   ├── detail_dialog.py         # Read-only detail view (with Show in Graph)
│   ├── comparison_dialog.py     # Side-by-side comparison modal
│   ├── about_dialog.py          # About modal
│   └── shortcuts_dialog.py      # Keyboard shortcuts reference
└── services/
    └── export.py                # CSV and JSON export logic
```

---

## Database Schema

```sql
philosophers  (id, name, birth_year, death_year, birth_city, birth_country,
               teachers, contributions)

quotes        (id, philosopher_id FK, text, is_favourite)  -- v5: is_favourite added

daily_quote   (id=1, quote_id, selected_on)                -- singleton row

teacher_links (id, student_id FK, teacher_id FK)           -- v5: parsed from teachers field
```

---

## Dependencies

- **PyQt6** — GUI framework (LGPL)
- **sqlite3** — standard library
- Python 3.10+ required (`int | None` union type syntax)

No external mapping libraries, no browser widget — the world map is rendered
entirely with `QPainter`.

---

## Extending

- **New philosopher fields** — add a column to `philosophers`, update the `Philosopher`
  dataclass, and add an input in `philosopher_form.py`
- **More teaching links** — populate the `teachers` field with comma-separated names
  that match existing philosopher names; `_rebuild_teacher_links()` runs on startup
- **New views** — add a widget in `ui/`, import in `main_window.py`, and add a tab
- **Map countries** — add entries to `COUNTRY_COORDS` in `world_map.py` as
  `"Country Name": (lat, lng)`
