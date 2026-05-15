Chronosophy — The Philosopher's Axiom is a richly featured desktop application for anyone passionate about the history of ideas. Built with PyQt6 and SQLite, it lets you explore, organise, and visualise philosophers across time, geography, and intellectual lineage — all within a polished, dark-themed interface designed to feel as considered as the subject matter itself.
The name Chronosophy blends chronos (time) and sophia (wisdom) — a fitting frame for an app that maps the arc of human thought from antiquity to the modern era.

**Features:**
Interactive Timeline — A custom-painted, zoomable chronological canvas with era colour bands, proportional year scaling, hover tooltips, and smooth pan/zoom via mouse or keyboard.
Influence Graph — A force-directed node graph visualising teacher → student relationships. Drag nodes, zoom, and re-layout to explore philosophical lineages.
World Map — A fully custom-rendered world map (no browser dependency) with country dots you can click to filter philosophers by origin.
Country View — Philosopher cards grouped and colour-differentiated by country of birth.
Statistics Tab — At-a-glance insights including era and country breakdowns, top-quoted philosophers, and aggregate counts.
Daily Wisdom Widget — An elegant quote panel that automatically selects a new quote each day, with smooth fade transitions and a favouriting system.
Search & Filtering — Filter by name, country, era, and favourited quotes. Sort by lifespan or alphabetically.
Philosopher Management — A clean form to add, edit, and delete philosophers, with support for multiple quotes and teacher/influence links.
Comparison Dialog — Side-by-side comparison of any two philosophers.
Export — Export your full database to CSV or JSON via the File menu.
Keyboard Shortcuts — Full keyboard navigation (Ctrl+1–5 for tabs, Ctrl+N, Ctrl+F, F11, and more).
Session Persistence — Window geometry, zoom level, and UI scale are all restored between sessions.

**Tech Stack**
Layer            Technology
GUI Framework    PyQt6
Database         SQLite (via sqlite3)
Rendering        Custom QPainter (map, timeline, graph)
Persistence      QSettings + SQLite
Language         Python 3.10+
