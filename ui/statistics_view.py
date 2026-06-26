"""
ui/statistics_view.py — Aggregate insights tab.

Renders an interactive dashboard:
· Four summary tiles (philosophers, quotes, favourites, teaching links) — each
  clickable, linking to a filtered view or the graph.
· An "Archive Overview" panel of derived detail metrics.
· Era + country distribution bar charts — every row is clickable and filters.
· Top-5 most-quoted philosophers — each row opens that philosopher's detail.

Every value is clickable: hovering highlights it and shows a pointing-hand
cursor; clicking emits a signal the main window turns into a filtered view,
a graph jump, or a detail dialog.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QRect, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
import database as db
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED, BG_HOVER,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, ERA_COLORS, FAVOURITE,
)


def _fmt_year(year) -> str:
    """Render a signed year the way the rest of the app does (negative → ' BC')."""
    if year is None:
        return "—"
    return f"{abs(year)} BC" if year < 0 else str(year)


# ─── Tile widget ─────────────────────────────────────────────────────────────

class StatTile(QWidget):
    """A clickable summary tile: big number, label, and a small detail caption."""

    clicked = pyqtSignal()

    def __init__(self, label: str, accent: str = GOLD, action_hint: str = "",
                 parent=None):
        super().__init__(parent)
        self._label = label
        self._value = "—"
        self._caption = ""
        self._accent = accent
        self._action_hint = action_hint     # e.g. "View all" — shown on hover
        self._hover = False
        self.setFixedHeight(108)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        if action_hint:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_value(self, value, caption: str = ""):
        self._value = str(value)
        self._caption = caption
        self.update()

    # ── Interaction ──────────────────────────────────────────────────────────
    def enterEvent(self, event):
        if self._action_hint:
            self._hover = True
            self.update()

    def leaveEvent(self, event):
        if self._hover:
            self._hover = False
            self.update()

    def mouseReleaseEvent(self, event):
        if self._action_hint and event.button() == Qt.MouseButton.LeftButton \
                and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    # ── Painting ─────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        border_col = QColor(self._accent) if self._hover else QColor(BORDER)
        painter.setBrush(QBrush(QColor(BG_HOVER if self._hover else BG_SURFACE)))
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(r, 8, 8)

        # Left accent bar
        accent = QColor(self._accent)
        accent.setAlpha(255 if self._hover else 220)
        painter.setBrush(QBrush(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(1, 1, 4, r.height(), 3, 3)

        # Big number
        painter.setPen(QColor(self._accent))
        painter.setFont(QFont("Georgia", 26, QFont.Weight.Bold))
        painter.drawText(20, 12, r.width() - 40, 40,
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self._value)

        # Label (uppercase)
        painter.setPen(QColor(TEXT_SEC if self._hover else TEXT_DIM))
        painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal))
        painter.drawText(20, 56, r.width() - 40, 20,
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self._label.upper())

        # Caption (extra detail)
        if self._caption:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
            painter.drawText(20, 78, r.width() - 40, 18,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             self._caption)

        # Action hint + chevron on hover
        if self._action_hint and self._hover:
            painter.setPen(QColor(self._accent))
            painter.setFont(QFont("Georgia", 9, QFont.Weight.Bold))
            fm = QFontMetrics(painter.font())
            txt = f"{self._action_hint}  ›"
            tw = fm.horizontalAdvance(txt)
            painter.drawText(r.width() - tw - 16, 12, tw, 20,
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             txt)

        painter.end()


# ─── Detail / overview panel ─────────────────────────────────────────────────

class DetailPanel(QWidget):
    """A card showing a two-column grid of derived 'at a glance' metrics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = "ARCHIVE OVERVIEW"
        self._metrics: list[tuple[str, str]] = []   # (label, value)
        self._content_height = 86
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._recompute_height()

    # The layout needs an honest height for this content-driven card, otherwise
    # the enclosing QScrollArea can mis-size it (see StatisticsView._sync_scroll_body).
    def sizeHint(self) -> QSize:
        return QSize(360, self._content_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self._content_height)

    def set_metrics(self, metrics: list[tuple[str, str]]):
        self._metrics = metrics
        self._recompute_height()
        self.update()

    def _recompute_height(self):
        rows = (len(self._metrics) + 1) // 2     # two columns
        self._content_height = 46 + max(1, rows) * 30 + 10
        self.setMinimumHeight(self._content_height)
        self.updateGeometry()

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
        painter.drawText(20, 18, self._title)

        if not self._metrics:
            painter.end()
            return

        col_gap = 24
        col_w = (r.width() - 40 - col_gap) // 2
        row_h = 30
        top = 40
        for i, (label, value) in enumerate(self._metrics):
            col = i % 2
            row = i // 2
            x = 20 + col * (col_w + col_gap)
            y = top + row * row_h

            # Label
            painter.setPen(QColor(TEXT_SEC))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal))
            fm = QFontMetrics(painter.font())
            label_w = col_w - 8
            elided = fm.elidedText(label, Qt.TextElideMode.ElideRight, label_w - 70)
            painter.drawText(x, y, label_w, row_h - 6,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             elided)

            # Value (right-aligned in the column)
            painter.setPen(QColor(GOLD_LIGHT))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Bold))
            painter.drawText(x, y, col_w, row_h - 6,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             value)

            # Hair divider under each row (except the last visual rows)
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawLine(x, y + row_h - 4, x + col_w, y + row_h - 4)

        painter.end()


# ─── Bar chart ───────────────────────────────────────────────────────────────

class BarChart(QWidget):
    """Horizontal bar chart. Each row is clickable and emits its label."""

    row_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple[str, int, str]] = []   # (label, value, colour_hex)
        self._title = ""
        self._total = 0
        self._hover_index = -1
        self._row_rects: list[QRect] = []
        self._content_height = 120
        self.setMinimumHeight(self._content_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMouseTracking(True)

    # Report the exact content height so the parent layout / QScrollArea never
    # squeezes this card (see StatisticsView._sync_scroll_body).
    def sizeHint(self) -> QSize:
        return QSize(320, self._content_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(220, self._content_height)

    def set_data(self, title: str, items: list[tuple[str, int, str]], total: int = 0):
        self._title = title
        self._items = items
        self._total = total or sum(v for _, v, _ in items)
        self._hover_index = -1
        row_h = 28
        self._content_height = 48 + len(items) * row_h + 10
        self.setMinimumHeight(self._content_height)
        self.updateGeometry()
        self.update()

    # ── Interaction ──────────────────────────────────────────────────────────
    def _index_at(self, pos) -> int:
        for i, rect in enumerate(self._row_rects):
            if rect.contains(pos):
                return i
        return -1

    def mouseMoveEvent(self, event):
        idx = self._index_at(event.position().toPoint())
        if idx != self._hover_index:
            self._hover_index = idx
            self.setCursor(Qt.CursorShape.PointingHandCursor if idx >= 0
                           else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        if self._hover_index != -1:
            self._hover_index = -1
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        idx = self._index_at(event.position().toPoint())
        if 0 <= idx < len(self._items):
            self.row_clicked.emit(self._items[idx][0])

    # ── Painting ─────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        r = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(QColor(BG_SURFACE)))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(r, 8, 8)

        self._row_rects = []

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
        label_col_w = 168
        count_col_w = 34
        pct_col_w = 44
        bar_left = 20 + label_col_w + 12
        bar_right = r.width() - count_col_w - pct_col_w - 16
        bar_max_w = max(20, bar_right - bar_left)

        row_h = 28
        y = 34
        for i, (label, value, colour_hex) in enumerate(self._items):
            hovered = (i == self._hover_index)
            row_rect = QRect(8, y, r.width() - 14, row_h)
            self._row_rects.append(row_rect)

            # Hover highlight behind the whole row
            if hovered:
                painter.setBrush(QBrush(QColor(BG_HOVER)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(row_rect, 5, 5)

            # Label
            painter.setPen(QColor(GOLD_LIGHT if hovered else TEXT_PRI))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal))
            fm = QFontMetrics(painter.font())
            elided = fm.elidedText(label, Qt.TextElideMode.ElideRight, label_col_w)
            painter.drawText(20, y, label_col_w, row_h,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             elided)

            # Bar background
            painter.setBrush(QBrush(QColor(BG_RAISED)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_left, y + 7, bar_max_w, row_h - 14, 4, 4)

            # Bar fill
            fill_w = int(bar_max_w * (value / max_val))
            colour = QColor(colour_hex)
            colour.setAlpha(255 if hovered else 200)
            painter.setBrush(QBrush(colour))
            painter.drawRoundedRect(bar_left, y + 7, fill_w, row_h - 14, 4, 4)

            # Count
            painter.setPen(QColor(GOLD_LIGHT))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Bold))
            painter.drawText(bar_right + 6, y, count_col_w, row_h,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             str(value))

            # Percentage of total
            pct = (value / self._total * 100) if self._total else 0
            painter.setPen(QColor(TEXT_SEC if hovered else TEXT_DIM))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
            painter.drawText(bar_right + 6 + count_col_w, y, pct_col_w, row_h,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             f"{pct:.0f}%")
            y += row_h

        painter.end()


# ─── Top-quoted list ─────────────────────────────────────────────────────────

class TopQuotedList(QWidget):
    """Philosophers ranked by quote count; each row opens that philosopher."""

    philosopher_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple[int, str, int]] = []   # (pid, name, count)
        self._hover_index = -1
        self._row_rects: list[QRect] = []
        self._content_height = 120
        self.setMinimumHeight(self._content_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMouseTracking(True)

    # Report the exact content height so the parent layout / QScrollArea never
    # squeezes this card (see StatisticsView._sync_scroll_body).
    def sizeHint(self) -> QSize:
        return QSize(360, self._content_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self._content_height)

    def set_data(self, items: list[tuple[int, str, int]]):
        self._items = items
        self._hover_index = -1
        self._content_height = 48 + len(items) * 34 + 8
        self.setMinimumHeight(self._content_height)
        self.updateGeometry()
        self.update()

    # ── Interaction ──────────────────────────────────────────────────────────
    def _index_at(self, pos) -> int:
        for i, rect in enumerate(self._row_rects):
            if rect.contains(pos):
                return i
        return -1

    def mouseMoveEvent(self, event):
        idx = self._index_at(event.position().toPoint())
        if idx != self._hover_index:
            self._hover_index = idx
            self.setCursor(Qt.CursorShape.PointingHandCursor if idx >= 0
                           else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        if self._hover_index != -1:
            self._hover_index = -1
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        idx = self._index_at(event.position().toPoint())
        if 0 <= idx < len(self._items):
            self.philosopher_clicked.emit(self._items[idx][0])

    # ── Painting ─────────────────────────────────────────────────────────────
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

        self._row_rects = []

        if not self._items:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Normal, True))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "No data.")
            painter.end()
            return

        y = 36
        row_h = 34
        for rank, (pid, name, count) in enumerate(self._items, start=1):
            hovered = (rank - 1 == self._hover_index)
            row_rect = QRect(8, y, r.width() - 14, row_h - 2)
            self._row_rects.append(row_rect)

            if hovered:
                painter.setBrush(QBrush(QColor(BG_HOVER)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(row_rect, 5, 5)

            # Rank circle
            painter.setBrush(QBrush(QColor(GOLD_DIM if rank == 1 else BG_RAISED)))
            painter.setPen(QPen(QColor(GOLD if rank == 1 else BORDER_LT), 1))
            painter.drawEllipse(20, y + 5, 22, 22)
            painter.setPen(QColor(GOLD_LIGHT if rank == 1 else TEXT_SEC))
            painter.setFont(QFont("Georgia", 10, QFont.Weight.Bold))
            painter.drawText(20, y + 5, 22, 22, Qt.AlignmentFlag.AlignCenter, str(rank))

            # Name
            painter.setPen(QColor(GOLD_LIGHT if hovered else TEXT_PRI))
            painter.setFont(QFont("Georgia", 12, QFont.Weight.Normal))
            painter.drawText(54, y, r.width() - 130, row_h,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             name)

            # Count
            painter.setPen(QColor(GOLD))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(r.width() - 96, y, 76, row_h,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             f"{count} quote{'s' if count != 1 else ''}")
            y += row_h

        painter.end()


# ─── Statistics view ─────────────────────────────────────────────────────────

class StatisticsView(QWidget):
    """The full statistics tab.

    Emits high-level intents the main window turns into navigation:
      · era_selected(str)         → filter by era + show timeline
      · country_selected(str)     → filter by country + show By Country
      · philosopher_selected(int) → open that philosopher's detail dialog
      · favourites_requested()    → favourites-only filtered view
      · graph_requested()         → jump to the influence graph
      · show_all_requested()      → clear filters + show everything
    """

    era_selected = pyqtSignal(str)
    country_selected = pyqtSignal(str)
    philosopher_selected = pyqtSignal(int)
    favourites_requested = pyqtSignal()
    graph_requested = pyqtSignal()
    show_all_requested = pyqtSignal()

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
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"QScrollArea {{ background: {BG_BASE}; border: none; }}")

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Tile row — each tile links somewhere
        tile_row = QHBoxLayout()
        tile_row.setSpacing(14)
        self.tile_p = StatTile("Philosophers", GOLD, action_hint="View all")
        self.tile_q = StatTile("Quotes", "#5CBB8A", action_hint="See most quoted")
        self.tile_f = StatTile("Favourites", FAVOURITE, action_hint="Show favourites")
        self.tile_l = StatTile("Teaching Links", "#4AAFB4", action_hint="Open graph")
        for tile in (self.tile_p, self.tile_q, self.tile_f, self.tile_l):
            tile_row.addWidget(tile)
        layout.addLayout(tile_row)

        self.tile_p.clicked.connect(self.show_all_requested.emit)
        self.tile_q.clicked.connect(self._scroll_to_most_quoted)
        self.tile_f.clicked.connect(self.favourites_requested.emit)
        self.tile_l.clicked.connect(self.graph_requested.emit)

        # Archive overview detail panel
        self.detail_panel = DetailPanel()
        layout.addWidget(self.detail_panel)

        # Charts row
        charts_row = QHBoxLayout()
        charts_row.setSpacing(14)

        self.era_chart = BarChart()
        self.era_chart.row_clicked.connect(self.era_selected.emit)
        charts_row.addWidget(self.era_chart, stretch=1)

        self.country_chart = BarChart()
        self.country_chart.row_clicked.connect(self.country_selected.emit)
        charts_row.addWidget(self.country_chart, stretch=1)

        layout.addLayout(charts_row)

        # Top-quoted list
        self.top_list = TopQuotedList()
        self.top_list.philosopher_clicked.connect(self.philosopher_selected.emit)
        layout.addWidget(self.top_list)

        layout.addStretch()
        self._scroll.setWidget(body)
        outer.addWidget(self._scroll, stretch=1)

    def _scroll_to_most_quoted(self):
        """Quotes tile → reveal the Most Quoted section."""
        self._scroll.ensureWidgetVisible(self.top_list, 0, 40)

    # ── Layout correctness ───────────────────────────────────────────────────
    def showEvent(self, event):
        """Resync the scroll body the moment this tab becomes visible.

        refresh() is run once at startup *while this tab is hidden* (the window
        opens on the Timeline tab and populates stats lazily). A hidden
        QScrollArea only re-sizes its inner widget on a real resize event, so it
        can keep the body sized for the old/empty content — squeezing the cards
        until they overlap, which only clears when the user drags the splitter.
        A showEvent fires even when the size is unchanged, so it's the reliable
        place to force the body back to its true height.
        """
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_scroll_body)

    def _sync_scroll_body(self):
        """Force the scroll body to the height its content actually needs.

        With widgetResizable the QScrollArea normally does this on resize; here
        we do it explicitly so the cards lay out without overlapping even when
        no resize event has occurred since the content last changed.
        """
        body = self._scroll.widget()
        if body is None:
            return
        if body.layout() is not None:
            body.layout().invalidate()
        vp = self._scroll.viewport()
        body.resize(vp.width(), max(vp.height(), body.sizeHint().height()))

    def refresh(self):
        """Pull fresh stats from the DB and update all sub-widgets."""
        stats = db.get_statistics()
        total_p = stats["total_philosophers"]

        # ── Tiles (value + detail caption) ───────────────────────────────────
        self.tile_p.set_value(
            total_p,
            f"across {stats['distinct_countries']} countries",
        )
        self.tile_q.set_value(
            stats["total_quotes"],
            f"avg {stats['avg_quotes']:.1f} per philosopher",
        )
        self.tile_f.set_value(
            stats["total_favourites"],
            f"{stats['fav_pct']:.0f}% of all quotes",
        )
        self.tile_l.set_value(
            stats["total_teacher_links"],
            "mentor connections",
        )

        # ── Archive overview ─────────────────────────────────────────────────
        span = f"{_fmt_year(stats['earliest_birth'])} – {_fmt_year(stats['latest_death'])}"
        self.detail_panel.set_metrics([
            ("Time span",             span),
            ("Avg. lifespan",         f"{stats['avg_lifespan']:.0f} years"),
            ("Eras represented",      str(stats["distinct_eras"])),
            ("Countries represented", str(stats["distinct_countries"])),
            ("Most prolific era",     stats["most_era"]),
            ("Largest tradition",     stats["most_country"]),
            ("Quotes / philosopher",  f"{stats['avg_quotes']:.1f}"),
            ("Favourited quotes",     f"{stats['fav_pct']:.0f}%"),
        ])

        # ── Era chart — canonical ordering so chronology reads top→bottom ─────
        era_order = [
            "Pre-Socratic", "Classical", "Hellenistic / Roman", "Medieval",
            "Renaissance", "Early Modern", "Modern", "Contemporary",
        ]
        era_items = [
            (era, stats["by_era"].get(era, 0), ERA_COLORS.get(era, "#4A5E7E"))
            for era in era_order
            if stats["by_era"].get(era, 0) > 0
        ]
        self.era_chart.set_data("By era", era_items, total=total_p)

        # ── Country chart ────────────────────────────────────────────────────
        country_items = [(c, n, GOLD_DIM) for c, n in stats["by_country"]]
        self.country_chart.set_data("By country", country_items, total=total_p)

        # ── Top-quoted ───────────────────────────────────────────────────────
        self.top_list.set_data(stats["top_quoted"])

        # Cards just changed height — make sure the scroll body follows suit even
        # if this ran while the tab was hidden (e.g. the startup refresh).
        self._sync_scroll_body()
