"""
ui/world_map.py — Stylised world map view.
Custom QPainter implementation (no QWebEngineView / folium dependency).

Continents are drawn as simplified painter paths (deliberately abstract — the
goal is atmosphere, not cartographic accuracy). Country dots are positioned
using approximate lat/lng for the eight seed countries plus a generous fallback
table for likely additions. Click a dot to filter to that country.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QToolTip, QPushButton
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QFontMetrics,
    QCursor, QRadialGradient
)
from database import Philosopher
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM,
    MAP_LAND, MAP_LAND_BORDER, MAP_OCEAN, MAP_DOT, MAP_DOT_HOVER, ERA_COLORS
)


# Approximate (lat, lng) coordinates for countries that appear in the seed data
# plus a broad fallback set for any additions users might make.
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    # Seed countries
    "Greece":      (39.0, 22.0),
    "China":       (35.0, 104.0),
    "Germany":     (51.0, 10.5),
    "France":      (46.5, 2.5),
    "England":     (52.5, -1.5),
    "Spain":       (40.0, -3.5),
    "Netherlands": (52.3, 5.5),
    "Scotland":    (56.8, -4.2),
    # Common additions
    "Italy":       (42.8, 12.5),
    "Ireland":     (53.4, -8.2),
    "Wales":       (52.4, -3.7),
    "United Kingdom":(54.0, -2.0),
    "USA":         (39.5, -98.5),
    "United States":(39.5, -98.5),
    "Russia":      (61.5, 100.0),
    "India":       (22.0, 79.0),
    "Japan":       (36.0, 138.0),
    "Korea":       (36.5, 127.7),
    "Egypt":       (26.8, 30.8),
    "Persia":      (32.5, 53.7),
    "Iran":        (32.5, 53.7),
    "Turkey":      (39.0, 35.2),
    "Austria":     (47.6, 14.5),
    "Switzerland": (46.8, 8.2),
    "Poland":      (52.0, 19.0),
    "Czech Republic":(49.8, 15.5),
    "Sweden":      (60.1, 15.6),
    "Norway":      (60.5, 9.0),
    "Denmark":     (56.0, 10.0),
    "Portugal":    (39.5, -8.0),
    "Belgium":     (50.5, 4.5),
    "Hungary":     (47.2, 19.5),
    "Romania":     (45.9, 24.9),
    "Argentina":   (-38.4, -63.6),
    "Brazil":      (-14.2, -51.9),
    "Mexico":      (23.6, -102.5),
    "Canada":      (56.1, -106.3),
    "Australia":   (-25.3, 133.8),
    "South Africa":(-30.6, 22.9),
    "Algeria":     (28.0, 1.7),
    "Morocco":     (31.8, -7.1),
}


# Simplified continent outlines (lng,lat polygons -> painted via projection).
# These are deliberately rough; the aim is a recognisable silhouette, not a real
# basemap. Coordinates from public-domain low-resolution outlines, reduced.
_CONTINENTS: list[list[tuple[float, float]]] = [
    # Eurasia (highly simplified)
    [(-10, 36), (-9, 43), (-1, 49), (2, 51), (8, 53), (13, 55), (18, 59),
    (24, 65), (30, 70), (40, 72), (60, 75), (80, 73), (105, 73), (140, 72),
    (160, 70), (170, 67), (175, 65), (170, 60), (160, 55), (145, 50),
    (140, 45), (135, 40), (125, 35), (120, 30), (110, 22), (108, 17),
    (105, 12), (100, 8), (95, 12), (88, 15), (82, 22), (78, 21), (72, 22),
    (65, 25), (58, 25), (52, 27), (48, 29), (44, 35), (40, 38), (35, 36),
    (28, 35), (22, 36), (18, 37), (12, 39), (5, 38), (-2, 36), (-9, 36)],

    # Africa
    [(-17, 21), (-15, 28), (-7, 32), (0, 33), (10, 31), (20, 30), (30, 31),
    (35, 24), (40, 16), (43, 11), (51, 11), (43, 0), (40, -10), (38, -16),
    (35, -22), (30, -25), (25, -33), (20, -34), (15, -29), (10, -22),
    (8, -10), (10, -3), (5, 4), (-2, 5), (-8, 5), (-13, 12), (-17, 14)],

    # North America
    [(-160, 65), (-140, 70), (-120, 70), (-100, 73), (-80, 73), (-65, 60),
    (-55, 50), (-65, 45), (-72, 40), (-78, 35), (-80, 28), (-82, 25),
    (-90, 20), (-100, 17), (-105, 22), (-115, 30), (-120, 35), (-125, 45),
    (-130, 55), (-145, 60), (-160, 60), (-165, 65)],

    # South America
    [(-80, 12), (-72, 11), (-62, 8), (-52, 5), (-42, -5), (-38, -15),
    (-40, -22), (-45, -30), (-58, -38), (-65, -50), (-70, -55), (-72, -50),
    (-75, -40), (-77, -28), (-78, -15), (-80, -5), (-82, 5), (-80, 12)],

    # Australia
    [(115, -22), (122, -20), (130, -13), (138, -12), (145, -15), (152, -25),
    (153, -32), (148, -38), (140, -38), (130, -32), (120, -34), (115, -30),
    (115, -22)],
]


class WorldMapCanvas(QWidget):
    country_clicked = pyqtSignal(str)

    _DRAG_THRESHOLD = 6    # px — distinguishes tap-on-dot from drag-to-pan

    def __init__(self, parent=None):
        super().__init__(parent)
        self._philosophers: list[Philosopher] = []
        self._country_counts: dict[str, int] = {}
        self._hover_country: str | None = None
        self._dot_hits: list[tuple[QPointF, float, str]] = []
        # ── Pan / zoom state ─────────────────────────────────────────────────
        self._zoom_factor: float = 1.0
        self._pan_offset: QPointF = QPointF(0.0, 0.0)
        self._pan_anchor: QPoint | None = None       # left-drag pan anchor
        self._press_dot_country: str | None = None   # dot the user tapped on
        self._press_dot_pos: QPoint | None = None    # where the tap happened
        # ─────────────────────────────────────────────────────────────────────
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(700, 380)

    def reset_view(self):
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0.0, 0.0)
        self.update()

    def set_philosophers(self, philosophers: list[Philosopher]):
        self._philosophers = philosophers
        counts: dict[str, int] = {}
        for p in philosophers:
            if p.birth_country:
                counts[p.birth_country] = counts.get(p.birth_country, 0) + 1
        self._country_counts = counts
        self.update()

    # ── Projection: lng/lat → canvas x/y ────────────────────────────────────

    def _project(self, lng: float, lat: float) -> QPointF:
        """Equirectangular projection, then apply current zoom + pan.

        All painted geometry goes through this function, so pan/zoom moves
        continents, grid lines, and country dots together perfectly.
        """
        margin_x = 30
        margin_y = 30
        w = self.width() - 2 * margin_x
        h = self.height() - 2 * margin_y
        lat = max(-75, min(75, lat))
        # Base (unzoomed) screen position
        bx = margin_x + ((lng + 180) / 360) * w
        by = margin_y + ((75 - lat) / 150) * h
        # Zoom is centred on the canvas centre, then pan is added
        cx = self.width() / 2
        cy = self.height() / 2
        x = cx + (bx - cx) * self._zoom_factor + self._pan_offset.x()
        y = cy + (by - cy) * self._zoom_factor + self._pan_offset.y()
        return QPointF(x, y)

    def _zoom_to(self, factor: float, anchor: QPointF):
        """Zoom by `factor` keeping the screen point `anchor` stationary."""
        old_z = self._zoom_factor
        new_z = max(0.5, min(8.0, old_z * factor))
        # Derive the "base canvas" position under the anchor before the zoom
        cx = self.width() / 2
        cy = self.height() / 2
        base_x = (anchor.x() - cx - self._pan_offset.x()) / old_z + cx
        base_y = (anchor.y() - cy - self._pan_offset.y()) / old_z + cy
        # After the zoom, the same base point must map back to the same screen pos
        self._pan_offset = QPointF(
            anchor.x() - cx - (base_x - cx) * new_z,
            anchor.y() - cy - (base_y - cy) * new_z,
        )
        self._zoom_factor = new_z
        self.update()

    # ── Painting ────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), QColor(MAP_OCEAN))

        self._paint_grid(painter)
        self._paint_continents(painter)
        self._paint_country_dots(painter)
        self._paint_legend(painter)
        painter.end()

    def _paint_grid(self, painter: QPainter):
        """Faint lat/lng grid for atmosphere."""
        pen = QPen(QColor(BORDER), 0.5, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        # Meridians every 30°
        for lng in range(-180, 181, 30):
            p1 = self._project(lng, -75)
            p2 = self._project(lng, 75)
            painter.drawLine(p1, p2)
        # Parallels every 30°
        for lat in range(-60, 61, 30):
            p1 = self._project(-180, lat)
            p2 = self._project(180, lat)
            painter.drawLine(p1, p2)
        # Equator highlight
        pen = QPen(QColor(BORDER_LT), 0.7, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = self._project(-180, 0)
        p2 = self._project(180, 0)
        painter.drawLine(p1, p2)

    def _paint_continents(self, painter: QPainter):
        """Draw the simplified continent silhouettes."""
        path = QPainterPath()
        for poly in _CONTINENTS:
            sub = QPainterPath()
            for i, (lng, lat) in enumerate(poly):
                pt = self._project(lng, lat)
                if i == 0:
                    sub.moveTo(pt)
                else:
                    sub.lineTo(pt)
            sub.closeSubpath()
            path.addPath(sub)

        painter.setBrush(QBrush(QColor(MAP_LAND)))
        painter.setPen(QPen(QColor(MAP_LAND_BORDER), 1.0))
        painter.drawPath(path)

    def _paint_country_dots(self, painter: QPainter):
        """Render a glowing dot for each country with at least one philosopher."""
        self._dot_hits.clear()
        if not self._country_counts:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                            "No philosophers loaded.")
            return

        max_count = max(self._country_counts.values())
        font = QFont("Georgia", 9, QFont.Weight.Normal)
        fm = QFontMetrics(font)
        painter.setFont(font)

        for country, count in sorted(self._country_counts.items(),
                                    key=lambda kv: -kv[1]):
            coords = COUNTRY_COORDS.get(country)
            if not coords:
                continue
            lat, lng = coords
            pt = self._project(lng, lat)
            # Dot radius scales with count (8..18 px)
            r = 8 + 10 * (count / max_count)

            is_hover = (country == self._hover_country)

            # Outer glow
            glow_radius = r * 2.4
            grad = QRadialGradient(pt, glow_radius)
            base = QColor(MAP_DOT_HOVER if is_hover else MAP_DOT)
            base.setAlpha(140 if is_hover else 90)
            grad.setColorAt(0.0, base)
            transparent = QColor(base)
            transparent.setAlpha(0)
            grad.setColorAt(1.0, transparent)
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pt, glow_radius, glow_radius)

            # Inner dot
            dot_colour = QColor(MAP_DOT_HOVER) if is_hover else QColor(MAP_DOT)
            painter.setBrush(QBrush(dot_colour))
            painter.setPen(QPen(QColor(GOLD_LIGHT), 1.2))
            painter.drawEllipse(pt, r, r)

            # Count number inside dot
            painter.setPen(QColor("#0C0C0E"))
            painter.setFont(QFont("Georgia", max(8, int(r * 0.7)), QFont.Weight.Bold))
            text_rect = QRectF(pt.x() - r, pt.y() - r, r * 2, r * 2)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(count))

            # Country label
            painter.setFont(font)
            painter.setPen(QColor(TEXT_PRI if is_hover else TEXT_SEC))
            label = country
            lw = fm.horizontalAdvance(label)
            label_y = pt.y() + r + 14
            painter.drawText(int(pt.x() - lw / 2), int(label_y), label)

            # Store hit zone
            self._dot_hits.append((pt, r, country))

    def _paint_legend(self, painter: QPainter):
        """Bottom-right legend with total countries / philosophers."""
        if not self._country_counts:
            return
        total_p = sum(self._country_counts.values())
        total_c = len(self._country_counts)
        text = f"{total_p} philosophers · {total_c} countries · Click a dot to filter"
        painter.setFont(QFont("Georgia", 9, QFont.Weight.Normal, True))
        fm = QFontMetrics(painter.font())
        tw = fm.horizontalAdvance(text)
        painter.setPen(QColor(TEXT_DIM))
        painter.drawText(self.width() - tw - 14, self.height() - 12, text)

    # ── Mouse events ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        # Check if pressing on a dot
        for pt, r, country in self._dot_hits:
            dx = pos.x() - pt.x()
            dy = pos.y() - pt.y()
            if dx * dx + dy * dy <= r * r:
                self._press_dot_country = country
                self._press_dot_pos = event.pos()
                return
        # Pressing on empty ocean/land → start pan
        self._pan_anchor = event.pos()
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        # ── Left-drag pan ────────────────────────────────────────────────────
        if self._pan_anchor is not None:
            delta = event.pos() - self._pan_anchor
            self._pan_offset += QPointF(delta.x(), delta.y())
            self._pan_anchor = event.pos()
            self._hover_country = None          # suppress hover while panning
            QToolTip.hideText()
            self.update()
            return

        # ── Pressed on dot but now dragging — promote to pan ─────────────────
        if self._press_dot_country is not None and self._press_dot_pos is not None:
            if (event.pos() - self._press_dot_pos).manhattanLength() > self._DRAG_THRESHOLD:
                self._pan_anchor = event.pos()
                self._press_dot_country = None
                self._press_dot_pos = None
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        # ── Hover detection ──────────────────────────────────────────────────
        pos = event.position()
        hovered = None
        for pt, r, country in self._dot_hits:
            dx = pos.x() - pt.x()
            dy = pos.y() - pt.y()
            if dx * dx + dy * dy <= r * r:
                hovered = country
                break

        if hovered != self._hover_country:
            self._hover_country = hovered
            self.update()
            if hovered:
                count = self._country_counts.get(hovered, 0)
                names = [p.name for p in self._philosophers
                        if p.birth_country == hovered]
                preview = ", ".join(names[:6])
                if len(names) > 6:
                    preview += f" + {len(names) - 6} more"
                tip = f"<b>{hovered}</b><br>{count} philosopher{'s' if count != 1 else ''}"
                if preview:
                    tip += f"<br><i>{preview}</i>"
                QToolTip.showText(self.mapToGlobal(event.pos()), tip, self)
            else:
                QToolTip.hideText()

        self.setCursor(QCursor(
            Qt.CursorShape.PointingHandCursor if hovered else Qt.CursorShape.ArrowCursor
        ))

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # End a pan
        if self._pan_anchor is not None:
            self._pan_anchor = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return
        # Clean tap on a dot → filter by country
        country = self._press_dot_country
        self._press_dot_country = None
        self._press_dot_pos = None
        if country:
            self.country_clicked.emit(country)

    def wheelEvent(self, event):
        """Ctrl + scroll = zoom (anchored on cursor). Plain scroll pans."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 1 / 1.12
            self._zoom_to(factor, event.position())
            event.accept()
        else:
            # Two-finger swipe pan (vertical → vertical, horizontal → horizontal)
            dx = event.angleDelta().x()
            dy = event.angleDelta().y()
            self._pan_offset += QPointF(dx * 0.5, dy * 0.5)
            self.update()
            event.accept()

    def event(self, ev):
        """Handle native trackpad pinch-to-zoom."""
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.NativeGesture:
            try:
                from PyQt6.QtGui import QNativeGestureEvent
                from PyQt6.QtCore import Qt as _Qt
                if isinstance(ev, QNativeGestureEvent):
                    if ev.gestureType() == _Qt.NativeGestureType.ZoomNativeGesture:
                        factor = 1.0 + ev.value()
                        self._zoom_to(factor, ev.position())
                        ev.accept()
                        return True
            except Exception:
                pass
        return super().event(ev)

    def leaveEvent(self, event):
        if self._hover_country is not None:
            self._hover_country = None
            self.update()
            QToolTip.hideText()


# ─── View wrapper ────────────────────────────────────────────────────────────

class WorldMapView(QWidget):
    """Wraps the canvas with a thin header bar."""
    country_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(10)

        title = QLabel("WORLD MAP")
        title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; letter-spacing: 2px; background: transparent;")
        hl.addWidget(title)

        sub = QLabel("Birth countries · click any dot to filter")
        sub.setStyleSheet(f"color: {GOLD_DIM}; font-size: 11px; background: transparent; font-style: italic;")
        hl.addWidget(sub)

        hl.addStretch()

        btn_reset = QPushButton("⤺  Reset View")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setToolTip("Reset pan and zoom to default")
        btn_reset.clicked.connect(lambda: self.canvas.reset_view())
        hl.addWidget(btn_reset)

        layout.addWidget(header)

        self.canvas = WorldMapCanvas()
        self.canvas.country_clicked.connect(self.country_clicked)
        layout.addWidget(self.canvas, stretch=1)

    def set_philosophers(self, philosophers: list[Philosopher]):
        self.canvas.set_philosophers(philosophers)
