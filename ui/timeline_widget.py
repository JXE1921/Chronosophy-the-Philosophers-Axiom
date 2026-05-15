"""
ui/timeline_widget.py — Chronological philosopher timeline.
Custom-painted scrollable canvas with proportional year positioning,
era bands, and clickable philosopher cards.

v5 changes:
- Ctrl + scroll wheel zooms the timeline horizontally (anchored at the cursor)
- Plain scroll wheel pans horizontally (faster than dragging the scrollbar)
- Middle-mouse drag also pans horizontally
- Tooltips show contribution preview on hover
- Fixed shadowing of imported BORDER_LT by a walrus operator inside the painter
- Zoom slider in the legend bar for explicit control
"""

from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QToolTip
)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
    QFontMetrics, QCursor, QPainterPath
)
from database import Philosopher
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, GOLD_MUTED, BG_BASE, BG_SURFACE,
    BG_RAISED, BG_HOVER, BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, ERA_COLORS
)


# ─── Constants ───────────────────────────────────────────────────────────────
LANE_HEIGHT    = 68          # vertical space per philosopher lane
HEADER_HEIGHT  = 56          # top ruler area
YEAR_PADDING   = 80          # extra horizontal padding each side
TICK_INTERVAL  = 100         # years between major tick marks


class TimelineCanvas(QWidget):
    """The actual painted timeline. Sits inside a QScrollArea.

    Zoom is controlled by `_pixels_per_year` (0.5 .. 24.0).
    """
    philosopher_clicked = pyqtSignal(int)
    zoom_changed = pyqtSignal(float)        # emits pixels_per_year

    MIN_ZOOM = 0.5
    MAX_ZOOM = 24.0
    DEFAULT_ZOOM = 4.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.philosophers: list[Philosopher] = []
        self._hit_rects: list[tuple[QRect, int]] = []   # (rect, philosopher_id)
        self._hover_id: int = -1
        self._pixels_per_year: float = self.DEFAULT_ZOOM
        self._min_year = -500
        self._max_year = 2025
        self._canvas_w = 800
        # ── Pan tracking ──────────────────────────────────────────────────────
        self._pan_anchor: QPoint | None = None      # middle-mouse drag
        self._left_pan_anchor: QPoint | None = None  # left-button drag (empty space)
        self._press_bar_pid: int = -1               # bar the user pressed on
        self._press_bar_pos: QPoint | None = None   # where the press happened
        # ─────────────────────────────────────────────────────────────────────
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ── Public API ───────────────────────────────────────────────────────────

    def set_philosophers(self, philosophers: list[Philosopher]):
        self.philosophers = philosophers
        self._recalculate_geometry()
        self.update()

    def set_zoom(self, pixels_per_year: float, anchor_x: int | None = None):
        """Change the horizontal zoom level. Optionally keep `anchor_x` (in
        canvas coords) pointing at the same year before & after the zoom.
        """
        new = max(self.MIN_ZOOM, min(self.MAX_ZOOM, pixels_per_year))
        if abs(new - self._pixels_per_year) < 0.001:
            return
        # Remember the year currently under the anchor
        anchor_year = None
        if anchor_x is not None and self.philosophers:
            anchor_year = self._x_to_year(anchor_x)

        self._pixels_per_year = new
        self._recalculate_geometry()
        self.update()
        self.zoom_changed.emit(self._pixels_per_year)

        # Keep that year under the anchor by adjusting the parent scroll bar
        if anchor_year is not None:
            new_x = self._year_to_x(anchor_year)
            scroll = self._find_scroll_area()
            if scroll:
                bar = scroll.horizontalScrollBar()
                # We want new_x to appear at the same viewport position as before
                viewport_offset = anchor_x - bar.value()
                bar.setValue(int(new_x - viewport_offset))

    def zoom(self) -> float:
        return self._pixels_per_year

    # ── Geometry ─────────────────────────────────────────────────────────────

    def _recalculate_geometry(self):
        if not self.philosophers:
            self.setMinimumSize(800, 400)
            self._canvas_w = 800
            return

        min_y = min(p.birth_year for p in self.philosophers)
        max_y = max(
            (p.death_year or p.birth_year + 80) for p in self.philosophers
        )
        span = max(max_y - min_y, 100)

        canvas_w = max(1200, int(span * self._pixels_per_year) + YEAR_PADDING * 2)
        canvas_h = HEADER_HEIGHT + len(self.philosophers) * LANE_HEIGHT + 40

        self.setMinimumSize(canvas_w, canvas_h)
        self._min_year = min_y - 50
        self._max_year = max_y + 50
        self._canvas_w = canvas_w

    def _year_to_x(self, year: int) -> int:
        span = self._max_year - self._min_year
        ratio = (year - self._min_year) / span
        return int(YEAR_PADDING + ratio * (self._canvas_w - YEAR_PADDING * 2))

    def _x_to_year(self, x: int) -> float:
        span = self._max_year - self._min_year
        rel = (x - YEAR_PADDING) / max(1, (self._canvas_w - YEAR_PADDING * 2))
        return self._min_year + rel * span

    def _year_label(self, year: int) -> str:
        if year < 0:
            return f"{abs(year)} BC"
        return str(year)

    def _find_scroll_area(self) -> QScrollArea | None:
        """Walk up to find the wrapping QScrollArea (so we can manipulate scroll position)."""
        w = self.parent()
        while w is not None:
            if isinstance(w, QScrollArea):
                return w
            w = w.parent()
        return None

    # ── Painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        if not self.philosophers:
            self._paint_empty()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(BG_BASE))

        self._paint_era_bands(painter, h)
        self._paint_axis(painter, w)
        self._paint_tick_marks(painter)
        self._paint_philosophers(painter)

        painter.end()

    def _paint_empty(self):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BG_BASE))
        painter.setPen(QColor(TEXT_DIM))
        painter.setFont(QFont("Georgia", 14, QFont.Weight.Normal, True))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                        "No philosophers to display.\nAdd some using the + button.")
        painter.end()

    def _paint_era_bands(self, painter: QPainter, canvas_height: int):
        """Draw subtle alternating background bands for each era."""
        era_ranges = {
            "Pre-Socratic":         (-3000, -400),
            "Classical":            (-400,    0),
            "Hellenistic / Roman":  (0,      500),
            "Medieval":             (500,   1400),
            "Renaissance":          (1400,  1650),
            "Early Modern":         (1650,  1800),
            "Modern":               (1800,  1900),
            "Contemporary":         (1900,  2200),
        }
        for era, (y_start, y_end) in era_ranges.items():
            x1 = self._year_to_x(y_start)
            x2 = self._year_to_x(y_end)
            era_color = QColor(ERA_COLORS.get(era, "#333344"))
            era_color.setAlpha(22)
            painter.fillRect(x1, HEADER_HEIGHT, x2 - x1, canvas_height, era_color)

            # Era label at top (very faint), only if band is wide enough
            if x2 - x1 > 80:
                label_color = QColor(ERA_COLORS.get(era, "#555566"))
                label_color.setAlpha(100)
                painter.setPen(label_color)
                painter.setFont(QFont("Georgia", 9, QFont.Weight.Normal, True))
                mid_x = (x1 + x2) // 2
                painter.drawText(mid_x - 60, HEADER_HEIGHT + 16, 120, 20,
                                Qt.AlignmentFlag.AlignCenter, era)

    def _paint_axis(self, painter: QPainter, canvas_width: int):
        """Draw the central timeline axis line."""
        axis_y = HEADER_HEIGHT - 1
        grad = QLinearGradient(0, 0, canvas_width, 0)
        grad.setColorAt(0.0, QColor(BORDER))
        grad.setColorAt(0.3, QColor(GOLD_DIM))
        grad.setColorAt(0.7, QColor(GOLD_DIM))
        grad.setColorAt(1.0, QColor(BORDER))
        painter.setPen(QPen(QBrush(grad), 1.5))
        painter.drawLine(0, axis_y, canvas_width, axis_y)

        # Zero line (AD/BC boundary)
        if self._min_year < 0 < self._max_year:
            zero_x = self._year_to_x(0)
            pen = QPen(QColor(GOLD), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(zero_x, 0, zero_x, self.height())
            painter.setFont(QFont("Georgia", 8))
            painter.setPen(QColor(GOLD_DIM))
            painter.drawText(zero_x + 4, 14, "AD")
            painter.drawText(zero_x - 26, 14, "BC")

    def _paint_tick_marks(self, painter: QPainter):
        """Draw year tick marks and labels along the top ruler.
        Tick interval auto-adjusts based on zoom level so labels never overlap.
        """
        # Adaptive tick interval: aim for ~80px between major ticks
        approx_px_per_tick = TICK_INTERVAL * self._pixels_per_year
        if approx_px_per_tick < 40:
            interval = TICK_INTERVAL * 5
        elif approx_px_per_tick < 80:
            interval = TICK_INTERVAL * 2
        elif approx_px_per_tick > 400:
            interval = TICK_INTERVAL // 2 if TICK_INTERVAL >= 50 else TICK_INTERVAL
            interval = max(25, interval)
        else:
            interval = TICK_INTERVAL

        start = (self._min_year // interval) * interval
        end = self._max_year + interval

        painter.setFont(QFont("Georgia", 8))

        for year in range(start, end, interval):
            if year < self._min_year or year > self._max_year:
                continue
            x = self._year_to_x(year)

            # Tick — use the imported BORDER_LT (was previously shadowed by a
            # walrus assignment that silently overwrote the import).
            painter.setPen(QPen(QColor(BORDER_LT), 1))
            painter.drawLine(x, HEADER_HEIGHT - 12, x, HEADER_HEIGHT)

            painter.setPen(QColor(TEXT_DIM))
            label = self._year_label(year)
            fm = QFontMetrics(painter.font())
            lw = fm.horizontalAdvance(label)
            painter.drawText(x - lw // 2, HEADER_HEIGHT - 16, label)

    def _paint_philosophers(self, painter: QPainter):
        """Render each philosopher as a horizontal bar in their lane."""
        self._hit_rects.clear()
        BAR_H = 34
        BAR_RADIUS = 5

        for idx, p in enumerate(self.philosophers):
            lane_y = HEADER_HEIGHT + idx * LANE_HEIGHT + (LANE_HEIGHT - BAR_H) // 2

            x1 = self._year_to_x(p.birth_year)
            x2 = self._year_to_x(p.death_year or p.birth_year + 80)
            bar_w = max(x2 - x1, 120)

            era_hex = ERA_COLORS.get(p.era, "#4A5E7E")
            era_col = QColor(era_hex)

            is_hover = (p.id == self._hover_id)

            grad = QLinearGradient(x1, 0, x1 + bar_w, 0)
            if is_hover:
                base = era_col.lighter(150)
                base.setAlpha(230)
                grad.setColorAt(0.0, base)
                grad.setColorAt(1.0, QColor(BG_RAISED))
            else:
                base = QColor(era_hex)
                base.setAlpha(170)
                grad.setColorAt(0.0, base)
                dimmed = QColor(era_hex)
                dimmed.setAlpha(80)
                grad.setColorAt(1.0, dimmed)

            path = QPainterPath()
            path.addRoundedRect(x1, lane_y, bar_w, BAR_H, BAR_RADIUS, BAR_RADIUS)
            painter.fillPath(path, QBrush(grad))

            border_col = QColor(era_hex).lighter(160) if is_hover else QColor(era_hex).lighter(110)
            border_col.setAlpha(180 if is_hover else 120)
            painter.setPen(QPen(border_col, 1.2))
            painter.drawPath(path)

            # Name
            painter.setPen(QColor("white") if is_hover else QColor(TEXT_PRI))
            name_font = QFont("Georgia", 11, QFont.Weight.Bold if is_hover else QFont.Weight.Normal)
            painter.setFont(name_font)

            text_x = x1 + 10
            text_w = bar_w - 20
            painter.drawText(text_x, lane_y, text_w, BAR_H // 2 + 4,
                            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                            p.name)

            painter.setFont(QFont("Georgia", 8, QFont.Weight.Normal, True))
            painter.setPen(QColor(TEXT_SEC))
            painter.drawText(text_x, lane_y + BAR_H // 2 - 2, text_w, BAR_H // 2 + 2,
                            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                            p.lifespan_label)

            # Country chip
            if p.birth_country:
                painter.setFont(QFont("Georgia", 8))
                fm = QFontMetrics(painter.font())
                country_text = p.birth_country
                cw = fm.horizontalAdvance(country_text) + 10
                cx = x1 + bar_w - cw - 6
                if cx > x1 + bar_w // 2:
                    painter.setPen(QColor(TEXT_DIM))
                    painter.drawText(cx, lane_y + 4, cw, BAR_H - 8,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                    country_text)

            self._hit_rects.append((QRect(x1, lane_y, bar_w, BAR_H), p.id))

            painter.setPen(QPen(QColor(BORDER), 0.5))
            painter.drawLine(0, HEADER_HEIGHT + (idx + 1) * LANE_HEIGHT,
                             self.width(), HEADER_HEIGHT + (idx + 1) * LANE_HEIGHT)

    # ── Mouse / wheel events ─────────────────────────────────────────────────

    # ── Mouse / wheel events ─────────────────────────────────────────────────

    # Drag threshold in px — if the user moves more than this before releasing,
    # we treat the gesture as a pan rather than a click.
    _DRAG_THRESHOLD = 6

    def _pan_scroll(self, new_global: QPoint, anchor: QPoint):
        """Move both scroll bars by the delta between two GLOBAL screen positions.

        Using global coordinates is critical: when setValue() repositions the
        viewport the canvas-local mouse position changes, but the global screen
        position never does. This is what eliminates the jitter/shake.
        """
        scroll = self._find_scroll_area()
        if scroll:
            delta = new_global - anchor
            scroll.horizontalScrollBar().setValue(
                scroll.horizontalScrollBar().value() - delta.x()
            )
            scroll.verticalScrollBar().setValue(
                scroll.verticalScrollBar().value() - delta.y()
            )

    def mouseMoveEvent(self, event):
        g = event.globalPosition().toPoint()

        # ── Middle-button drag pan ───────────────────────────────────────────
        if self._pan_anchor is not None:
            self._pan_scroll(g, self._pan_anchor)
            self._pan_anchor = g
            return

        # ── Left-button drag pan (started on empty space) ────────────────────
        if self._left_pan_anchor is not None:
            self._pan_scroll(g, self._left_pan_anchor)
            self._left_pan_anchor = g
            return

        # ── Left pressed on a bar, but now dragging — promote to pan ─────────
        if self._press_bar_pid >= 0 and self._press_bar_pos is not None:
            # Compare using local pos for the drag threshold (stable while not yet panning)
            if (event.pos() - self._press_bar_pos).manhattanLength() > self._DRAG_THRESHOLD:
                self._left_pan_anchor = g
                self._press_bar_pid = -1
                self._press_bar_pos = None
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        # ── Hover detection ──────────────────────────────────────────────────
        pos = event.pos()
        hovered = -1
        hovered_p: Philosopher | None = None
        for rect, pid in self._hit_rects:
            if rect.contains(pos):
                hovered = pid
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                hovered_p = next((p for p in self.philosophers if p.id == pid), None)
                break
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        if hovered != self._hover_id:
            self._hover_id = hovered
            self.update()
            if hovered_p:
                preview = (hovered_p.contributions or "").strip().replace("\n", " ")
                if len(preview) > 180:
                    preview = preview[:177] + "…"
                tip = (f"<b>{hovered_p.name}</b><br>"
                        f"<i>{hovered_p.lifespan_label} · {hovered_p.birth_country}</i>")
                if preview:
                    tip += f"<br><br>{preview}"
                QToolTip.showText(self.mapToGlobal(pos), tip, self)
            else:
                QToolTip.hideText()

    def mousePressEvent(self, event):
        # Middle button → pan (any direction), anchor in global coords
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_anchor = event.globalPosition().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            # Check if pressing on a philosopher bar
            for rect, pid in self._hit_rects:
                if rect.contains(pos):
                    self._press_bar_pid = pid
                    self._press_bar_pos = pos   # local coords fine for threshold check
                    return
            # Pressing on empty canvas → pan, anchor in global coords
            self._left_pan_anchor = event.globalPosition().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_anchor = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # End a left-button pan
            if self._left_pan_anchor is not None:
                self._left_pan_anchor = None
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                return

            # Releasing after pressing on a bar (no significant drag) → click
            pid = self._press_bar_pid
            self._press_bar_pid = -1
            self._press_bar_pos = None
            if pid >= 0:
                pos = event.pos()
                for rect, rpid in self._hit_rects:
                    if rect.contains(pos) and rpid == pid:
                        self.philosopher_clicked.emit(pid)
                        break

    def wheelEvent(self, event):
        # Ctrl + wheel = zoom; plain wheel = horizontal pan (two-finger swipe)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            anchor_x = event.position().x()
            self.set_zoom(self._pixels_per_year * factor, anchor_x=int(anchor_x))
            event.accept()
            return

        # Forward to horizontal scroll bar for two-finger swipe panning
        scroll = self._find_scroll_area()
        if scroll:
            delta = event.angleDelta().y()
            bar = scroll.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            event.accept()
            return
        super().wheelEvent(event)

    def event(self, ev):
        """Handle native trackpad pinch-to-zoom gesture."""
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.NativeGesture:
            try:
                from PyQt6.QtGui import QNativeGestureEvent
                if isinstance(ev, QNativeGestureEvent):
                    from PyQt6.QtCore import Qt as _Qt
                    if ev.gestureType() == _Qt.NativeGestureType.ZoomNativeGesture:
                        factor = 1.0 + ev.value()
                        anchor_x = int(ev.position().x())
                        self.set_zoom(self._pixels_per_year * factor, anchor_x=anchor_x)
                        ev.accept()
                        return True
            except Exception:
                pass
        return super().event(ev)

    def leaveEvent(self, event):
        self._hover_id = -1
        self.update()
        QToolTip.hideText()


# ─── TimelineView: wraps canvas in scroll area + legend ──────────────────────

class TimelineView(QWidget):
    philosopher_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: transparent;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_legend())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_BASE}; border: none; }}
        """)

        self.canvas = TimelineCanvas()
        self.canvas.philosopher_clicked.connect(self.philosopher_clicked)
        self.scroll.setWidget(self.canvas)

        layout.addWidget(self.scroll, stretch=1)

    def _build_legend(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(36)
        w.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        title = QLabel("ERA KEY")
        title.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 9px; letter-spacing: 2px; background: transparent;"
        )
        layout.addWidget(title)

        for era, color in ERA_COLORS.items():
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
            lbl = QLabel(era)
            lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; background: transparent;")
            layout.addWidget(dot)
            layout.addWidget(lbl)

        layout.addStretch()
        return w

    def set_philosophers(self, philosophers: list[Philosopher]):
        self.canvas.set_philosophers(philosophers)
        self.canvas.setMinimumSize(self.canvas.minimumSize())
