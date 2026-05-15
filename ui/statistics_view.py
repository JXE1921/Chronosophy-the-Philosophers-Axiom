"""
ui/statistics_view.py — Aggregate insights tab.

Renders:
· Four summary tiles (total philosophers, quotes, favourites, teaching links)
· Era distribution bar chart (custom QPainter)
· Country distribution bar chart
· Top-5 most-quoted philosophers
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
import database as db
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED, BG_HOVER,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, ERA_COLORS, FAVOURITE
)


# ─── Tile widget ─────────────────────────────────────────────────────────────

class StatTile(QWidget):
    """A small summary tile: big number on top, label underneath."""

    def __init__(self, label: str, accent: str = GOLD, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = "—"
        self._accent = accent
        self.setFixedHeight(96)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value: int | str):
        self._value = str(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        painter.setBrush(QBrush(QColor(BG_SURFACE)))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(r, 8, 8)

        # Left accent bar
        accent = QColor(self._accent)
        accent.setAlpha(220)
        painter.setBrush(QBrush(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(1, 1, 4, r.height(), 3, 3)

        # Big number
        painter.setPen(QColor(self._accent))
        painter.setFont(QFont("Georgia", 28, QFont.Weight.Bold))
        painter.drawText(20, 14, r.width() - 40, 44,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        self._value)

        # Label
        painter.setPen(QColor(TEXT_DIM))
        painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal))
        # Letter-spacing emulation: draw uppercase
        painter.drawText(20, r.height() - 30, r.width() - 40, 22,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                        self._label.upper())

        painter.end()


# ─── Bar chart ───────────────────────────────────────────────────────────────

class BarChart(QWidget):
    """A horizontal bar chart. Each row: label (left), bar (centre), count (right)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple[str, int, str]] = []  # (label, value, colour_hex)
        self._title = ""
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_data(self, title: str, items: list[tuple[str, int, str]]):
        self._title = title
        self._items = items
        # Resize height to fit rows
        row_h = 26
        self.setMinimumHeight(48 + len(items) * row_h + 8)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        r = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(QColor(BG_SURFACE)))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(r, 8, 8)

        if not self._items:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "No data.")
            painter.end()
            return

        # Title
        painter.setPen(QColor(GOLD))
        painter.setFont(QFont("Georgia", 9, QFont.Weight.Normal))
        painter.drawText(20, 18, self._title.upper())

        # Layout
        max_val = max(v for _, v, _ in self._items) or 1
        label_col_w = 180
        count_col_w = 36
        bar_left = 20 + label_col_w + 12
        bar_right = r.width() - count_col_w - 16
        bar_max_w = max(20, bar_right - bar_left)

        row_h = 26
        y = 36
        for label, value, colour_hex in self._items:
            # Label
            painter.setPen(QColor(TEXT_PRI))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal))
            fm = QFontMetrics(painter.font())
            elided = fm.elidedText(label, Qt.TextElideMode.ElideRight, label_col_w)
            painter.drawText(20, y, label_col_w, row_h,
                            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                            elided)

            # Bar background
            painter.setBrush(QBrush(QColor(BG_RAISED)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_left, y + 6, bar_max_w, row_h - 12, 4, 4)

            # Bar fill
            fill_w = int(bar_max_w * (value / max_val))
            colour = QColor(colour_hex)
            colour.setAlpha(200)
            painter.setBrush(QBrush(colour))
            painter.drawRoundedRect(bar_left, y + 6, fill_w, row_h - 12, 4, 4)

            # Count
            painter.setPen(QColor(GOLD_LIGHT))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Bold))
            painter.drawText(bar_right + 4, y, count_col_w, row_h,
                            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                            str(value))
            y += row_h

        painter.end()


# ─── Top-quoted list ─────────────────────────────────────────────────────────

class TopQuotedList(QWidget):
    """Stylish list of philosophers ranked by quote count."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple[str, int]] = []
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_data(self, items: list[tuple[str, int]]):
        self._items = items
        self.setMinimumHeight(48 + len(items) * 32 + 8)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        r = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(QColor(BG_SURFACE)))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(r, 8, 8)

        painter.setPen(QColor(GOLD))
        painter.setFont(QFont("Georgia", 9, QFont.Weight.Normal))
        painter.drawText(20, 18, "MOST QUOTED")

        if not self._items:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "No data.")
            painter.end()
            return

        y = 38
        for rank, (name, count) in enumerate(self._items, start=1):
            # Rank circle
            painter.setBrush(QBrush(QColor(GOLD_DIM if rank == 1 else BG_RAISED)))
            painter.setPen(QPen(QColor(GOLD if rank == 1 else BORDER_LT), 1))
            painter.drawEllipse(20, y + 4, 22, 22)
            painter.setPen(QColor(GOLD_LIGHT if rank == 1 else TEXT_SEC))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Bold))
            painter.drawText(20, y + 4, 22, 22, Qt.AlignmentFlag.AlignCenter, str(rank))

            # Name
            painter.setPen(QColor(TEXT_PRI))
            painter.setFont(QFont("Georgia", 12, QFont.Weight.Normal))
            painter.drawText(54, y, r.width() - 130, 30,
                            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                            name)

            # Count
            painter.setPen(QColor(GOLD))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(r.width() - 90, y, 70, 30,
                            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                            f"{count} quote{'s' if count != 1 else ''}")
            y += 32

        painter.end()


# ─── Statistics view ─────────────────────────────────────────────────────────

class StatisticsView(QWidget):
    """The full statistics tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("STATISTICS")
        title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; letter-spacing: 2px; background: transparent;")
        hl.addWidget(title)
        sub = QLabel("Aggregate insights across the archive")
        sub.setStyleSheet(f"color: {GOLD_DIM}; font-size: 11px; background: transparent; font-style: italic;")
        hl.addWidget(sub)
        hl.addStretch()
        outer.addWidget(header)

        # Scroll body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {BG_BASE}; border: none; }}")

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Tile row
        tile_row = QHBoxLayout()
        tile_row.setSpacing(14)
        self.tile_p = StatTile("Philosophers", GOLD)
        self.tile_q = StatTile("Quotes", "#5CBB8A")
        self.tile_f = StatTile("Favourites", FAVOURITE)
        self.tile_l = StatTile("Teaching Links", "#4AAFB4")
        for tile in (self.tile_p, self.tile_q, self.tile_f, self.tile_l):
            tile_row.addWidget(tile)
        layout.addLayout(tile_row)

        # Charts row
        charts_row = QHBoxLayout()
        charts_row.setSpacing(14)

        self.era_chart = BarChart()
        charts_row.addWidget(self.era_chart, stretch=1)

        self.country_chart = BarChart()
        charts_row.addWidget(self.country_chart, stretch=1)

        layout.addLayout(charts_row)

        # Top-quoted list
        self.top_list = TopQuotedList()
        layout.addWidget(self.top_list)

        layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

    def refresh(self):
        """Pull fresh stats from the DB and update all sub-widgets."""
        stats = db.get_statistics()
        self.tile_p.set_value(stats["total_philosophers"])
        self.tile_q.set_value(stats["total_quotes"])
        self.tile_f.set_value(stats["total_favourites"])
        self.tile_l.set_value(stats["total_teacher_links"])

        # Era chart — use the canonical era ordering so chronology reads top→bottom
        era_order = [
            "Pre-Socratic", "Classical", "Hellenistic / Roman", "Medieval",
            "Renaissance", "Early Modern", "Modern", "Contemporary",
        ]
        era_items = [
            (era, stats["by_era"].get(era, 0), ERA_COLORS.get(era, "#4A5E7E"))
            for era in era_order
            if stats["by_era"].get(era, 0) > 0
        ]
        self.era_chart.set_data("By era", era_items)

        # Country chart
        country_items = [(c, n, GOLD_DIM) for c, n in stats["by_country"]]
        self.country_chart.set_data("By country", country_items)

        # Top-quoted
        self.top_list.set_data(stats["top_quoted"])
