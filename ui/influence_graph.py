"""
ui/influence_graph.py — Teacher → student relationship graph.
Custom-painted force-directed layout, no extra dependencies.

Each philosopher is a node, each "X taught Y" link is a directed edge.
Layout uses a lightweight Fruchterman–Reingold-style force simulation
that runs for a bounded number of iterations on data load (no live ticker).
"""

import math
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QFontMetrics, QCursor,
    QLinearGradient
)
from database import Philosopher
import database as db
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED, BG_HOVER,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, ERA_COLORS,
    GRAPH_NODE_FILL, GRAPH_NODE_HOVER, GRAPH_EDGE, GRAPH_EDGE_HIGHLIGHT
)


NODE_RADIUS = 28


class _Node:
    __slots__ = ("p", "x", "y", "vx", "vy")

    def __init__(self, p: Philosopher, x: float, y: float):
        self.p = p
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0


class InfluenceGraphCanvas(QWidget):
    """The painted graph itself."""
    philosopher_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: dict[int, _Node] = {}
        self._edges: list[tuple[int, int]] = []
        self._hover_id = -1
        self._dragging_id = -1
        self._drag_offset = QPointF(0, 0)
        self._pan_offset = QPointF(0, 0)
        self._pan_anchor: QPoint | None = None
        self._zoom = 1.0
        self._highlight_id: int | None = None    # philosopher to centre on
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(600, 400)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_data(self, philosophers: list[Philosopher], edges: list[tuple[int, int]]):
        """Build the graph and run the layout simulation."""
        self._highlight_id = None
        if not philosophers:
            self._nodes = {}
            self._edges = []
            self.update()
            return

        # Initialise nodes in a circle so the simulation has a sensible start
        n = len(philosophers)
        cx, cy = self.width() / 2 or 400, self.height() / 2 or 300
        radius = min(cx, cy) * 0.7
        self._nodes = {}
        for i, p in enumerate(philosophers):
            angle = 2 * math.pi * i / max(n, 1)
            self._nodes[p.id] = _Node(
                p,
                cx + radius * math.cos(angle) + random.uniform(-10, 10),
                cy + radius * math.sin(angle) + random.uniform(-10, 10),
            )

        # Filter edges to only those between visible nodes
        self._edges = [(s, t) for s, t in edges if s in self._nodes and t in self._nodes]

        self._run_layout()
        self.update()

    def centre_on(self, philosopher_id: int):
        """Set highlight + pan so this philosopher is in view."""
        self._highlight_id = philosopher_id
        node = self._nodes.get(philosopher_id)
        if node:
            # Reset pan so the node lands near the centre of the viewport
            cx, cy = self.width() / 2, self.height() / 2
            self._pan_offset = QPointF(cx - node.x * self._zoom, cy - node.y * self._zoom)
        self.update()

    # ── Force-directed layout ────────────────────────────────────────────────

    def _run_layout(self, iterations: int = 200):
        """Lightweight Fruchterman–Reingold layout."""
        if not self._nodes:
            return

        nodes = list(self._nodes.values())
        n = len(nodes)
        W = max(self.width(), 800)
        H = max(self.height(), 600)
        area = W * H
        k = math.sqrt(area / n) * 0.75       # ideal edge length
        temp = W / 8                         # max displacement per step
        cooling = temp / iterations

        # Build adjacency for fast lookup
        edge_set = set()
        for s, t in self._edges:
            edge_set.add((s, t))
            edge_set.add((t, s))

        for it in range(iterations):
            # Repulsion (every pair)
            for u in nodes:
                u.vx = 0.0
                u.vy = 0.0
            for i, u in enumerate(nodes):
                for v in nodes[i + 1:]:
                    dx = u.x - v.x
                    dy = u.y - v.y
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01
                    force = (k * k) / dist
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force
                    u.vx += fx
                    u.vy += fy
                    v.vx -= fx
                    v.vy -= fy

            # Attraction (edges)
            for s, t in self._edges:
                u = self._nodes[s]
                v = self._nodes[t]
                dx = u.x - v.x
                dy = u.y - v.y
                dist = math.sqrt(dx * dx + dy * dy) or 0.01
                force = (dist * dist) / k
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                u.vx -= fx
                u.vy -= fy
                v.vx += fx
                v.vy += fy

            # Gentle pull toward chronological ordering on the X-axis so the
            # graph reads roughly left=ancient, right=modern
            min_year = min(n_.p.birth_year for n_ in nodes)
            max_year = max(n_.p.birth_year for n_ in nodes)
            year_span = max(max_year - min_year, 1)
            for u in nodes:
                target_x = ((u.p.birth_year - min_year) / year_span) * (W * 0.85) + W * 0.075
                u.vx += (target_x - u.x) * 0.04

            # Apply with temperature cap, keep within bounds
            for u in nodes:
                disp = math.sqrt(u.vx * u.vx + u.vy * u.vy) or 0.01
                cap = min(disp, temp)
                u.x += (u.vx / disp) * cap
                u.y += (u.vy / disp) * cap
                # Clamp into the viewport
                u.x = max(60, min(W - 60, u.x))
                u.y = max(80, min(H - 80, u.y))

            temp -= cooling

    # ── Coordinate transforms ────────────────────────────────────────────────

    def _to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(x * self._zoom + self._pan_offset.x(),
                       y * self._zoom + self._pan_offset.y())

    def _from_screen(self, sx: float, sy: float) -> QPointF:
        return QPointF((sx - self._pan_offset.x()) / self._zoom,
                        (sy - self._pan_offset.y()) / self._zoom)

    # ── Painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), QColor(BG_BASE))

        if not self._nodes:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Georgia", 14, QFont.Weight.Normal, True))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                                "No philosophers to graph.")
            painter.end()
            return

        self._paint_edges(painter)
        self._paint_nodes(painter)
        self._paint_legend(painter)
        painter.end()

    def _paint_edges(self, painter: QPainter):
        """Draw each teacher→student edge with a small arrowhead."""
        # Highlight set: edges touching the hovered node
        hover = self._hover_id
        for s, t in self._edges:
            u = self._nodes[s]
            v = self._nodes[t]
            p1 = self._to_screen(v.x, v.y)   # teacher (source visually)
            p2 = self._to_screen(u.x, u.y)   # student (arrow points here)

            highlighted = hover in (s, t) or self._highlight_id in (s, t)
            colour = QColor(GRAPH_EDGE_HIGHLIGHT) if highlighted else QColor(GRAPH_EDGE)
            colour.setAlpha(220 if highlighted else 130)
            pen = QPen(colour, 2.0 if highlighted else 1.2)
            painter.setPen(pen)

            # Stop the line short of the node circle so the arrow looks clean
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = math.sqrt(dx * dx + dy * dy) or 0.01
            r = NODE_RADIUS * self._zoom
            ux, uy = dx / length, dy / length
            start = QPointF(p1.x() + ux * r, p1.y() + uy * r)
            end = QPointF(p2.x() - ux * r, p2.y() - uy * r)
            painter.drawLine(start, end)

            # Arrowhead
            ah = 9
            angle = math.atan2(dy, dx)
            ax1 = end.x() - ah * math.cos(angle - math.pi / 7)
            ay1 = end.y() - ah * math.sin(angle - math.pi / 7)
            ax2 = end.x() - ah * math.cos(angle + math.pi / 7)
            ay2 = end.y() - ah * math.sin(angle + math.pi / 7)
            painter.setBrush(QBrush(colour))
            painter.setPen(Qt.PenStyle.NoPen)
            arrow = QPainterPath()
            arrow.moveTo(end)
            arrow.lineTo(QPointF(ax1, ay1))
            arrow.lineTo(QPointF(ax2, ay2))
            arrow.closeSubpath()
            painter.drawPath(arrow)

    def _paint_nodes(self, painter: QPainter):
        font = QFont("Georgia", max(8, int(9 * self._zoom)), QFont.Weight.Normal)
        for node in self._nodes.values():
            sx = self._to_screen(node.x, node.y)
            r = NODE_RADIUS * self._zoom
            era_colour = QColor(ERA_COLORS.get(node.p.era, "#4A5E7E"))

            is_hover = node.p.id == self._hover_id
            is_highlight = node.p.id == self._highlight_id

            # Drop ring for highlight/hover
            if is_highlight or is_hover:
                glow = QColor(GOLD_LIGHT if is_highlight else BORDER_LT)
                glow.setAlpha(180 if is_highlight else 140)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(glow, 3))
                painter.drawEllipse(sx, r + 5, r + 5)

            # Filled disk
            grad = QLinearGradient(sx.x() - r, sx.y() - r, sx.x() + r, sx.y() + r)
            grad.setColorAt(0.0, era_colour.lighter(140))
            grad.setColorAt(1.0, era_colour.darker(140))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(GOLD if is_hover else BORDER_LT), 1.4))
            painter.drawEllipse(sx, r, r)

            # Initials inside the node
            initials = "".join(part[0].upper() for part in node.p.name.split() if part)[:2]
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Georgia", max(9, int(11 * self._zoom)), QFont.Weight.Bold))
            text_rect = QRectF(sx.x() - r, sx.y() - r, r * 2, r * 2)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, initials)

            # Name label below
            painter.setPen(QColor(TEXT_PRI if (is_hover or is_highlight) else TEXT_SEC))
            painter.setFont(font)
            label_rect = QRectF(sx.x() - 80, sx.y() + r + 4, 160, 20)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                            node.p.name)

    def _paint_legend(self, painter: QPainter):
        """Bottom-left legend explaining edge direction."""
        painter.setFont(QFont("Georgia", 9, QFont.Weight.Normal, True))
        painter.setPen(QColor(TEXT_DIM))
        painter.drawText(14, self.height() - 12,
                        "Arrows point from teacher → student   ·   "
                        "Drag a node to reposition   ·   Wheel to zoom")

    # ── Mouse / wheel ────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pid = self._node_at(event.position())
            if pid >= 0:
                self._dragging_id = pid
                node = self._nodes[pid]
                screen = self._to_screen(node.x, node.y)
                self._drag_offset = event.position() - screen
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                return
            self._pan_anchor = event.pos()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        if self._dragging_id >= 0:
            node = self._nodes[self._dragging_id]
            new_screen = event.position() - self._drag_offset
            world = self._from_screen(new_screen.x(), new_screen.y())
            node.x = world.x()
            node.y = world.y()
            self.update()
            return
        if self._pan_anchor is not None:
            delta = event.pos() - self._pan_anchor
            self._pan_offset += QPointF(delta.x(), delta.y())
            self._pan_anchor = event.pos()
            self.update()
            return

        # Hover detection
        pid = self._node_at(event.position())
        if pid != self._hover_id:
            self._hover_id = pid
            self.update()
        self.setCursor(QCursor(
            Qt.CursorShape.PointingHandCursor if pid >= 0 else Qt.CursorShape.ArrowCursor
        ))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_drag = self._dragging_id >= 0 or self._pan_anchor is not None
            click_pid = self._node_at(event.position())
            # If we did NOT drag (i.e. press and release on same node), treat as click
            if not was_drag and click_pid >= 0:
                self.philosopher_clicked.emit(click_pid)
            elif self._dragging_id >= 0 and click_pid == self._dragging_id and \
                    (event.position() - (self._to_screen(self._nodes[click_pid].x,
                                                        self._nodes[click_pid].y) +
                                            self._drag_offset)).manhattanLength() < 4:
                self.philosopher_clicked.emit(click_pid)
            self._dragging_id = -1
            self._pan_anchor = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = max(0.4, min(3.0, self._zoom * factor))
        # Anchor zoom on cursor position
        cursor_world = self._from_screen(event.position().x(), event.position().y())
        self._zoom = new_zoom
        new_screen = QPointF(cursor_world.x() * self._zoom, cursor_world.y() * self._zoom)
        self._pan_offset = QPointF(event.position().x() - new_screen.x(),
                                    event.position().y() - new_screen.y())
        self.update()
        event.accept()

    def leaveEvent(self, event):
        if self._hover_id != -1:
            self._hover_id = -1
            self.update()

    def _node_at(self, pos: QPointF) -> int:
        for node in self._nodes.values():
            sx = self._to_screen(node.x, node.y)
            r = NODE_RADIUS * self._zoom
            dx = pos.x() - sx.x()
            dy = pos.y() - sx.y()
            if dx * dx + dy * dy <= r * r:
                return node.p.id
        return -1


# ─── View wrapper ────────────────────────────────────────────────────────────

class InfluenceGraphView(QWidget):
    philosopher_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(10)

        title = QLabel("INFLUENCE GRAPH")
        title.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; letter-spacing: 2px; background: transparent;")
        tl.addWidget(title)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(f"color: {GOLD_DIM}; font-size: 11px; background: transparent;")
        tl.addWidget(self.lbl_count)

        tl.addStretch()

        btn_relayout = QPushButton("⟳  Re-layout")
        btn_relayout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_relayout.setToolTip("Reshuffle and run the layout again")
        btn_relayout.clicked.connect(self._relayout)
        tl.addWidget(btn_relayout)

        btn_reset = QPushButton("⤺  Reset View")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setToolTip("Reset pan and zoom")
        btn_reset.clicked.connect(self._reset_view)
        tl.addWidget(btn_reset)

        layout.addWidget(toolbar)

        self.canvas = InfluenceGraphCanvas()
        self.canvas.philosopher_clicked.connect(self.philosopher_clicked)
        layout.addWidget(self.canvas, stretch=1)

    def set_philosophers(self, philosophers: list[Philosopher]):
        """Re-fetch edges from the DB and rebuild the graph."""
        edges = db.get_teacher_graph_edges()
        self.canvas.set_data(philosophers, edges)
        n_nodes = len(philosophers)
        n_edges = sum(1 for s, t in edges if any(p.id == s for p in philosophers)
                        and any(p.id == t for p in philosophers))
        self.lbl_count.setText(f"{n_nodes} philosophers · {n_edges} teaching links")

    def centre_on(self, philosopher_id: int):
        self.canvas.centre_on(philosopher_id)

    def _relayout(self):
        ps = [n.p for n in self.canvas._nodes.values()]
        edges = db.get_teacher_graph_edges()
        self.canvas.set_data(ps, edges)

    def _reset_view(self):
        self.canvas._zoom = 1.0
        self.canvas._pan_offset = QPointF(0, 0)
        self.canvas.update()
