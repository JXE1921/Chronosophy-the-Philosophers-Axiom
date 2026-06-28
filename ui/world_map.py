"""
ui/world_map.py — Accurate world map view (offline, pure QPainter).

Country outlines come from a bundled, simplified Natural Earth 50m dataset
(assets/world_countries.json — public domain), so coastlines are geographically
accurate (the UK, small states and islands all exist) without any web / tile
dependency. Geometry is projected with an equirectangular projection and drawn
through a single zoom/pan transform, so the whole map moves together.

Level of detail:
  · Zoomed out  → one aggregate dot per birth-country showing the total count.
  · Zoomed in   → the aggregate dots cross-fade into per-city markers placed at
                  the philosopher's actual birth city. A city with one
                  philosopher shows their initials (as in the Graph view); a city
                  with several shows a count badge that "spiders" open on click to
                  reveal each philosopher's initials. Clicking a philosopher
                  marker opens their detail view.
"""

import os
import sys
import json
import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QToolTip, QPushButton
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QPoint, QEvent, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QFontMetrics,
    QCursor, QRadialGradient, QLinearGradient
)
from database import Philosopher
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM,
    MAP_LAND, MAP_LAND_BORDER, MAP_OCEAN, MAP_DOT, MAP_DOT_HOVER, ERA_COLORS
)


# Aggregate (zoomed-out) dot positions, keyed by the app's birth_country values.
# Kept curated because the app uses names Natural Earth has no polygon for
# (England, Scotland, Persia, …); the dot just needs a sensible anchor.
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "Greece":      (39.0, 22.0),
    "China":       (35.0, 104.0),
    "Germany":     (51.0, 10.5),
    "France":      (46.5, 2.5),
    "England":     (52.5, -1.5),
    "Spain":       (40.0, -3.5),
    "Netherlands": (52.3, 5.5),
    "Scotland":    (56.8, -4.2),
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


# Birth-city coordinates (lat, lng) for the seed philosophers. Historical places
# are mapped to their real site (Königsberg→Kaliningrad, La Haye en Touraine→
# Descartes, Ku County→Luyi County, Henan). User-added cities fall back to the
# country anchor with a small deterministic offset (see _city_coord).
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Athens":              (37.9715, 23.7257),
    "Stagira":             (40.5917, 23.7946),
    "Qufu":                (35.5974, 117.0226),
    "Königsberg":          (54.7104, 20.5101),
    "La Haye en Touraine": (46.9744, 0.6986),
    "Röcken":              (51.2408, 12.1161),
    "Wrington":            (51.3610, -2.7630),
    "Paris":               (48.8566, 2.3522),
    "Córdoba":             (37.8882, -4.7794),
    "Amsterdam":           (52.3683, 4.9032),
    "London":              (51.5189, -0.0824),
    "Ku County":           (33.8600, 115.4900),
    "Edinburgh":           (55.9533, -3.1883),
}


# ── Bundled geometry loading (cached process-wide) ───────────────────────────

_GEOMETRY: list[dict] | None = None


def _asset_path(rel: str) -> str:
    """Resolve a bundled asset both from source and inside a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, rel)


def _load_geometry() -> list[dict]:
    """Load simplified country polygons once; tolerate a missing asset."""
    global _GEOMETRY
    if _GEOMETRY is None:
        try:
            with open(_asset_path("assets/world_countries.json"), encoding="utf-8") as fh:
                _GEOMETRY = json.load(fh).get("countries", [])
        except Exception:
            _GEOMETRY = []
    return _GEOMETRY


def _initials(name: str) -> str:
    """Two-letter initials — identical convention to the Graph view."""
    return "".join(part[0].upper() for part in name.split() if part)[:2] or "?"


class WorldMapCanvas(QWidget):
    country_clicked = pyqtSignal(str)
    philosopher_clicked = pyqtSignal(int)

    _DRAG_THRESHOLD = 6      # px — distinguishes tap from drag-to-pan
    LAT_LIMIT = 83           # projection clamps latitude to ±this
    FADE_START = 1.9         # zoom at which city markers begin to appear
    FADE_END = 2.7           # zoom at which only city markers show
    MAX_ZOOM = 16.0
    MIN_ZOOM = 0.5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._philosophers: list[Philosopher] = []
        self._country_counts: dict[str, int] = {}
        self._city_entries: list[dict] = []
        self._city_by_key: dict[tuple, dict] = {}

        # Cached base-projected land path (rebuilt only when the widget resizes)
        self._base_path: QPainterPath | None = None
        self._base_path_size: tuple[int, int] = (0, 0)

        # Hit zones, rebuilt every paint
        self._country_hits: list[tuple[QPointF, float, str]] = []
        self._cluster_hits: list[tuple[QPointF, float, tuple]] = []
        self._philosopher_hits: list[tuple[QPointF, float, Philosopher]] = []

        # Hover / interaction state
        self._hover_country: str | None = None
        self._hover_cluster: tuple | None = None
        self._hover_phil_id: int | None = None
        self._expanded_city: tuple | None = None     # spidered-open cluster

        # Pan / zoom state
        self._zoom_factor: float = 1.0
        self._pan_offset: QPointF = QPointF(0.0, 0.0)
        self._pan_anchor: QPoint | None = None
        self._press_action: tuple | None = None      # ('country'|'phil'|'cluster', payload)
        self._press_pos: QPoint | None = None

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(700, 380)

    # ── Public API ───────────────────────────────────────────────────────────

    def reset_view(self):
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0.0, 0.0)
        self._expanded_city = None
        self.update()

    def set_philosophers(self, philosophers: list[Philosopher]):
        self._philosophers = philosophers
        counts: dict[str, int] = {}
        for p in philosophers:
            if p.birth_country:
                counts[p.birth_country] = counts.get(p.birth_country, 0) + 1
        self._country_counts = counts
        self._build_city_entries()
        self._expanded_city = None
        self.update()

    def _build_city_entries(self):
        groups: dict[tuple, list[Philosopher]] = {}
        for p in self._philosophers:
            if not (p.birth_city or p.birth_country):
                continue
            key = (p.birth_country, p.birth_city)
            groups.setdefault(key, []).append(p)
        entries, by_key = [], {}
        for (country, city), phils in groups.items():
            entry = {
                "key": (country, city), "country": country, "city": city,
                "phils": phils, "coord": self._city_coord(country, city),
            }
            entries.append(entry)
            by_key[(country, city)] = entry
        # Draw busier clusters first so single-initial markers sit on top
        entries.sort(key=lambda e: -len(e["phils"]))
        self._city_entries = entries
        self._city_by_key = by_key

    def _city_coord(self, country: str, city: str) -> tuple[float, float] | None:
        coord = CITY_COORDS.get(city)
        if coord:
            return coord
        base = COUNTRY_COORDS.get(country)
        if base:
            # Deterministic offset so distinct unknown cities don't stack.
            seed = sum(ord(ch) for ch in (city or country))
            dlat = ((seed % 100) / 100 - 0.5) * 1.6
            dlng = (((seed // 100) % 100) / 100 - 0.5) * 1.6
            return (base[0] + dlat, base[1] + dlng)
        return None

    # ── Projection ───────────────────────────────────────────────────────────

    def _base_project(self, lng: float, lat: float) -> QPointF:
        """Equirectangular projection into base (unzoomed) canvas coordinates."""
        margin = 30
        w = self.width() - 2 * margin
        h = self.height() - 2 * margin
        lat = max(-self.LAT_LIMIT, min(self.LAT_LIMIT, lat))
        bx = margin + ((lng + 180) / 360) * w
        by = margin + ((self.LAT_LIMIT - lat) / (2 * self.LAT_LIMIT)) * h
        return QPointF(bx, by)

    def _project(self, lng: float, lat: float) -> QPointF:
        """Base projection + current zoom (about centre) + pan."""
        b = self._base_project(lng, lat)
        cx, cy = self.width() / 2, self.height() / 2
        x = cx + (b.x() - cx) * self._zoom_factor + self._pan_offset.x()
        y = cy + (b.y() - cy) * self._zoom_factor + self._pan_offset.y()
        return QPointF(x, y)

    def _lod_t(self) -> float:
        """0.0 = country dots only, 1.0 = city markers only (cross-fade between)."""
        z = self._zoom_factor
        span = self.FADE_END - self.FADE_START
        return max(0.0, min(1.0, (z - self.FADE_START) / span))

    def _city_mode(self) -> bool:
        return self._lod_t() >= 0.5

    def _zoom_to(self, factor: float, anchor: QPointF):
        """Zoom by `factor`, keeping the screen point `anchor` stationary."""
        old_z = self._zoom_factor
        new_z = max(self.MIN_ZOOM, min(self.MAX_ZOOM, old_z * factor))
        cx, cy = self.width() / 2, self.height() / 2
        base_x = (anchor.x() - cx - self._pan_offset.x()) / old_z + cx
        base_y = (anchor.y() - cy - self._pan_offset.y()) / old_z + cy
        self._pan_offset = QPointF(
            anchor.x() - cx - (base_x - cx) * new_z,
            anchor.y() - cy - (base_y - cy) * new_z,
        )
        self._zoom_factor = new_z
        if not self._city_mode():
            self._expanded_city = None
        self.update()

    # ── Painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), QColor(MAP_OCEAN))

        self._country_hits.clear()
        self._cluster_hits.clear()
        self._philosopher_hits.clear()

        self._paint_grid(painter)
        self._paint_land(painter)

        if not self._country_counts:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Georgia", 11, QFont.Weight.Normal, True))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No philosophers loaded.")
            painter.end()
            return

        t = self._lod_t()
        if t < 1.0:
            self._paint_country_dots(painter, 1.0 - t)
        if t > 0.0:
            self._paint_city_markers(painter, t)
        painter.setOpacity(1.0)

        self._paint_legend(painter)
        painter.end()

    def _paint_grid(self, painter: QPainter):
        pen = QPen(QColor(BORDER), 0.5, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        for lng in range(-180, 181, 30):
            painter.drawLine(self._project(lng, -self.LAT_LIMIT),
                             self._project(lng, self.LAT_LIMIT))
        for lat in range(-60, 61, 30):
            painter.drawLine(self._project(-180, lat), self._project(180, lat))

    def _build_base_path(self):
        path = QPainterPath()
        for country in _load_geometry():
            for ring in country["polys"]:
                for i, (lng, lat) in enumerate(ring):
                    pt = self._base_project(lng, lat)
                    if i == 0:
                        path.moveTo(pt)
                    else:
                        path.lineTo(pt)
                path.closeSubpath()
        self._base_path = path
        self._base_path_size = (self.width(), self.height())

    def _paint_land(self, painter: QPainter):
        if self._base_path is None or self._base_path_size != (self.width(), self.height()):
            self._build_base_path()
        painter.save()
        cx, cy = self.width() / 2, self.height() / 2
        z = self._zoom_factor
        painter.translate(cx * (1 - z) + self._pan_offset.x(),
                          cy * (1 - z) + self._pan_offset.y())
        painter.scale(z, z)
        pen = QPen(QColor(MAP_LAND_BORDER), 1.0)
        pen.setCosmetic(True)              # 1px borders regardless of zoom
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(MAP_LAND)))
        painter.drawPath(self._base_path)
        painter.restore()

    def _on_canvas(self, pt: QPointF) -> bool:
        m = 80
        return (-m <= pt.x() <= self.width() + m) and (-m <= pt.y() <= self.height() + m)

    def _paint_country_dots(self, painter: QPainter, alpha: float):
        painter.setOpacity(alpha)
        max_count = max(self._country_counts.values())
        label_font = QFont("Georgia", 9, QFont.Weight.Normal)
        fm = QFontMetrics(label_font)

        for country, count in sorted(self._country_counts.items(), key=lambda kv: -kv[1]):
            coords = COUNTRY_COORDS.get(country)
            if not coords:
                continue
            lat, lng = coords
            pt = self._project(lng, lat)
            r = 8 + 10 * (count / max_count)
            is_hover = (country == self._hover_country) and self._city_mode() is False

            glow_radius = r * 2.4
            grad = QRadialGradient(pt, glow_radius)
            base = QColor(MAP_DOT_HOVER if is_hover else MAP_DOT)
            base.setAlpha(140 if is_hover else 90)
            grad.setColorAt(0.0, base)
            transparent = QColor(base); transparent.setAlpha(0)
            grad.setColorAt(1.0, transparent)
            painter.setBrush(QBrush(grad)); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pt, glow_radius, glow_radius)

            painter.setBrush(QBrush(QColor(MAP_DOT_HOVER if is_hover else MAP_DOT)))
            painter.setPen(QPen(QColor(GOLD_LIGHT), 1.2))
            painter.drawEllipse(pt, r, r)

            painter.setPen(QColor("#0C0C0E"))
            painter.setFont(QFont("Georgia", max(8, int(r * 0.7)), QFont.Weight.Bold))
            painter.drawText(QRectF(pt.x() - r, pt.y() - r, r * 2, r * 2),
                             Qt.AlignmentFlag.AlignCenter, str(count))

            painter.setFont(label_font)
            painter.setPen(QColor(TEXT_PRI if is_hover else TEXT_SEC))
            lw = fm.horizontalAdvance(country)
            painter.drawText(int(pt.x() - lw / 2), int(pt.y() + r + 14), country)

            self._country_hits.append((pt, r, country))

    def _paint_city_markers(self, painter: QPainter, alpha: float):
        painter.setOpacity(alpha)
        for entry in self._city_entries:
            coord = entry["coord"]
            if not coord:
                continue
            pt = self._project(coord[1], coord[0])
            if not self._on_canvas(pt):
                continue
            phils = entry["phils"]
            if self._expanded_city == entry["key"] and len(phils) > 1:
                self._paint_spider(painter, pt, phils)
            elif len(phils) == 1:
                self._paint_phil_marker(painter, pt, phils[0], phils[0].name)
            else:
                self._paint_cluster(painter, pt, entry)

    def _paint_phil_marker(self, painter: QPainter, pt: QPointF, p: Philosopher,
                           label: str, r: float = 15.0):
        era = QColor(ERA_COLORS.get(p.era, "#4A5E7E"))
        is_hover = (p.id == self._hover_phil_id)

        if is_hover:
            ring = QColor(GOLD_LIGHT); ring.setAlpha(180)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ring, 3))
            painter.drawEllipse(pt, r + 5, r + 5)

        grad = QLinearGradient(pt.x() - r, pt.y() - r, pt.x() + r, pt.y() + r)
        grad.setColorAt(0.0, era.lighter(140))
        grad.setColorAt(1.0, era.darker(140))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(GOLD if is_hover else BORDER_LT), 1.4))
        painter.drawEllipse(pt, r, r)

        painter.setPen(QColor("white"))
        painter.setFont(QFont("Georgia", max(9, int(r * 0.72)), QFont.Weight.Bold))
        painter.drawText(QRectF(pt.x() - r, pt.y() - r, r * 2, r * 2),
                         Qt.AlignmentFlag.AlignCenter, _initials(p.name))

        painter.setPen(QColor(TEXT_PRI if is_hover else TEXT_SEC))
        painter.setFont(QFont("Georgia", 8, QFont.Weight.Normal))
        painter.drawText(QRectF(pt.x() - 90, pt.y() + r + 2, 180, 16),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)

        self._philosopher_hits.append((pt, r, p))

    def _paint_cluster(self, painter: QPainter, pt: QPointF, entry: dict):
        n = len(entry["phils"])
        r = 13 + 2 * min(n, 6)
        is_hover = (entry["key"] == self._hover_cluster)

        glow_radius = r * 2.2
        grad = QRadialGradient(pt, glow_radius)
        base = QColor(MAP_DOT_HOVER if is_hover else MAP_DOT)
        base.setAlpha(150 if is_hover else 95)
        grad.setColorAt(0.0, base)
        transparent = QColor(base); transparent.setAlpha(0)
        grad.setColorAt(1.0, transparent)
        painter.setBrush(QBrush(grad)); painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(pt, glow_radius, glow_radius)

        painter.setBrush(QBrush(QColor(MAP_DOT_HOVER if is_hover else MAP_DOT)))
        painter.setPen(QPen(QColor(GOLD_LIGHT), 1.4))
        painter.drawEllipse(pt, r, r)

        painter.setPen(QColor("#0C0C0E"))
        painter.setFont(QFont("Georgia", max(9, int(r * 0.75)), QFont.Weight.Bold))
        painter.drawText(QRectF(pt.x() - r, pt.y() - r, r * 2, r * 2),
                         Qt.AlignmentFlag.AlignCenter, str(n))

        painter.setPen(QColor(TEXT_PRI if is_hover else TEXT_SEC))
        painter.setFont(QFont("Georgia", 8, QFont.Weight.Normal))
        painter.drawText(QRectF(pt.x() - 90, pt.y() + r + 2, 180, 16),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                         f"{entry['city']} · {n}")

        self._cluster_hits.append((pt, r, entry["key"]))

    def _paint_spider(self, painter: QPainter, pt: QPointF, phils: list[Philosopher]):
        n = len(phils)
        radius = 30 + 7 * n
        # connector lines first, so markers sit on top
        painter.setPen(QPen(QColor(BORDER_LT), 1.0, Qt.PenStyle.SolidLine))
        spokes = []
        for i, p in enumerate(phils):
            ang = math.radians(-90 + i * 360.0 / n)
            mp = QPointF(pt.x() + radius * math.cos(ang), pt.y() + radius * math.sin(ang))
            spokes.append((mp, p))
            painter.drawLine(pt, mp)
        # small anchor at the city centre
        painter.setBrush(QBrush(QColor(GOLD_DIM)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(pt, 3, 3)
        for mp, p in spokes:
            self._paint_phil_marker(painter, mp, p, p.name, r=14.0)

    def _paint_legend(self, painter: QPainter):
        painter.setOpacity(1.0)
        total_p = sum(self._country_counts.values())
        total_c = len(self._country_counts)
        if self._city_mode():
            hint = "Showing cities · click a cluster to expand · click a marker for details"
        else:
            hint = "Ctrl+scroll to zoom in and reveal cities · click a dot to filter"
        text = f"{total_p} philosophers · {total_c} countries · {hint}"
        painter.setFont(QFont("Georgia", 9, QFont.Weight.Normal, True))
        fm = QFontMetrics(painter.font())
        painter.setPen(QColor(TEXT_DIM))
        painter.drawText(self.width() - fm.horizontalAdvance(text) - 14,
                         self.height() - 12, text)

    # ── Hit testing ──────────────────────────────────────────────────────────

    @staticmethod
    def _hit(pos: QPointF, hits) -> object | None:
        for pt, r, payload in hits:
            dx, dy = pos.x() - pt.x(), pos.y() - pt.y()
            if dx * dx + dy * dy <= r * r:
                return payload
        return None

    def _action_at(self, pos: QPointF) -> tuple | None:
        """The interactive thing under `pos`, respecting the current LOD mode."""
        if self._city_mode():
            p = self._hit(pos, self._philosopher_hits)
            if p is not None:
                return ("phil", p)
            key = self._hit(pos, self._cluster_hits)
            if key is not None:
                return ("cluster", key)
        else:
            country = self._hit(pos, self._country_hits)
            if country is not None:
                return ("country", country)
        return None

    # ── Mouse events ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        action = self._action_at(event.position())
        if action is not None:
            self._press_action = action
            self._press_pos = event.pos()
            return
        self._pan_anchor = event.pos()
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        if self._pan_anchor is not None:
            delta = event.pos() - self._pan_anchor
            self._pan_offset += QPointF(delta.x(), delta.y())
            self._pan_anchor = event.pos()
            self._clear_hover()
            QToolTip.hideText()
            self.update()
            return

        if self._press_action is not None and self._press_pos is not None:
            if (event.pos() - self._press_pos).manhattanLength() > self._DRAG_THRESHOLD:
                self._pan_anchor = event.pos()
                self._press_action = None
                self._press_pos = None
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        self._update_hover(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._pan_anchor is not None:
            self._pan_anchor = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return
        action = self._press_action
        self._press_action = None
        self._press_pos = None
        if action is not None:
            kind, payload = action
            if kind == "country":
                self.country_clicked.emit(payload)
            elif kind == "phil":
                self.philosopher_clicked.emit(payload.id)
            elif kind == "cluster":
                self._expanded_city = None if self._expanded_city == payload else payload
                self.update()
            return
        # Click on empty space collapses an open cluster
        if self._expanded_city is not None:
            self._expanded_city = None
            self.update()

    def _clear_hover(self):
        self._hover_country = None
        self._hover_cluster = None
        self._hover_phil_id = None

    def _update_hover(self, event):
        pos = event.position()
        hp = hc = hcountry = None
        if self._city_mode():
            hp = self._hit(pos, self._philosopher_hits)
            if hp is None:
                hc = self._hit(pos, self._cluster_hits)
        else:
            hcountry = self._hit(pos, self._country_hits)

        new_pid = hp.id if hp else None
        changed = (new_pid != self._hover_phil_id or hc != self._hover_cluster
                   or hcountry != self._hover_country)
        self._hover_phil_id = new_pid
        self._hover_cluster = hc
        self._hover_country = hcountry

        if changed:
            self.update()
            self._show_tooltip(event, hp, hc, hcountry)

        over = hp is not None or hc is not None or hcountry is not None
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor if over
                               else Qt.CursorShape.ArrowCursor))

    def _show_tooltip(self, event, hp, hc, hcountry):
        gpos = self.mapToGlobal(event.pos())
        if hp is not None:
            tip = (f"<b>{hp.name}</b><br>{hp.lifespan_label}"
                   f"<br><i>{hp.birth_city or '—'}, {hp.birth_country}</i>")
            QToolTip.showText(gpos, tip, self)
        elif hc is not None:
            entry = self._city_by_key.get(hc)
            if entry:
                names = ", ".join(p.name for p in entry["phils"][:6])
                if len(entry["phils"]) > 6:
                    names += f" + {len(entry['phils']) - 6} more"
                QToolTip.showText(
                    gpos,
                    f"<b>{entry['city']}</b> · {entry['country']}"
                    f"<br>{len(entry['phils'])} philosophers<br><i>{names}</i><br>"
                    f"<span style='color:#888'>click to expand</span>", self)
        elif hcountry is not None:
            count = self._country_counts.get(hcountry, 0)
            names = [p.name for p in self._philosophers if p.birth_country == hcountry]
            preview = ", ".join(names[:6])
            if len(names) > 6:
                preview += f" + {len(names) - 6} more"
            tip = f"<b>{hcountry}</b><br>{count} philosopher{'s' if count != 1 else ''}"
            if preview:
                tip += f"<br><i>{preview}</i>"
            QToolTip.showText(gpos, tip, self)
        else:
            QToolTip.hideText()

    def wheelEvent(self, event):
        """Ctrl + scroll = zoom (anchored on cursor); plain scroll pans."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 1 / 1.12
            self._zoom_to(factor, event.position())
            event.accept()
        else:
            dx = event.angleDelta().x()
            dy = event.angleDelta().y()
            self._pan_offset += QPointF(dx * 0.5, dy * 0.5)
            self.update()
            event.accept()

    def event(self, ev):
        """Native trackpad pinch-to-zoom."""
        if ev.type() == QEvent.Type.NativeGesture:
            try:
                from PyQt6.QtGui import QNativeGestureEvent
                if isinstance(ev, QNativeGestureEvent):
                    if ev.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                        self._zoom_to(1.0 + ev.value(), ev.position())
                        ev.accept()
                        return True
            except Exception:
                pass
        return super().event(ev)

    def leaveEvent(self, event):
        if self._hover_country or self._hover_cluster or self._hover_phil_id is not None:
            self._clear_hover()
            self.update()
            QToolTip.hideText()


# ─── View wrapper ────────────────────────────────────────────────────────────

class WorldMapView(QWidget):
    """Wraps the canvas with a thin header bar."""
    country_clicked = pyqtSignal(str)
    philosopher_clicked = pyqtSignal(int)

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

        sub = QLabel("Birth places · zoom in to reveal cities")
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
        self.canvas.philosopher_clicked.connect(self.philosopher_clicked)
        layout.addWidget(self.canvas, stretch=1)

    def set_philosophers(self, philosophers: list[Philosopher]):
        self.canvas.set_philosophers(philosophers)
