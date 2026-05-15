"""
ui/country_widget.py — Country view.
Displays philosophers grouped by country of origin in a card-based layout
with muted colour differentiation per country.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QFrame, QSizePolicy, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QObject
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QBrush, QPen, QPainterPath
from database import Philosopher
from styles import (
    GOLD, GOLD_DIM, GOLD_MUTED, BG_BASE, BG_SURFACE, BG_RAISED, BG_HOVER,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, COUNTRY_COLORS, ERA_COLORS
)
import hashlib


def _country_color(country: str) -> str:
    """Deterministically assign a muted colour to each country."""
    idx = int(hashlib.md5(country.encode()).hexdigest(), 16) % len(COUNTRY_COLORS)
    return COUNTRY_COLORS[idx]


class PhilosopherCard(QWidget):
    """A compact clickable card for a single philosopher."""
    clicked = pyqtSignal(int)

    def __init__(self, philosopher: Philosopher, accent: str, parent=None):
        super().__init__(parent)
        self.p = philosopher
        self.accent = accent
        self._hovered = False
        self.setFixedSize(200, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self.rect().adjusted(1, 1, -1, -1)
        accent = QColor(self.accent)

        # Background
        bg = QColor(BG_SURFACE) if not self._hovered else QColor(BG_HOVER)
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r, 8, 8)

        # Left accent strip
        strip_color = QColor(self.accent)
        strip_color.setAlpha(200)
        painter.setBrush(QBrush(strip_color))
        path = QPainterPath()
        path.addRoundedRect(1, 1, 5, r.height(), 4, 4)
        painter.drawPath(path)

        # Border
        border_col = accent.lighter(130) if self._hovered else QColor(BORDER)
        border_col.setAlpha(180)
        painter.setPen(QPen(border_col, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r, 8, 8)

        # Era chip
        era_col = QColor(ERA_COLORS.get(self.p.era, "#4A5E7E"))
        era_col.setAlpha(120)
        painter.setBrush(QBrush(era_col))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(14, 8, 80, 14, 3, 3)

        painter.setPen(QColor("white"))
        painter.setFont(self.font())
        from PyQt6.QtGui import QFont
        f = QFont("Georgia", 7)
        painter.setFont(f)
        painter.drawText(14, 8, 80, 14, Qt.AlignmentFlag.AlignCenter, self.p.era)

        # Name
        from PyQt6.QtGui import QFont, QFontMetrics
        name_font = QFont("Georgia", 11, QFont.Weight.Bold)
        painter.setFont(name_font)
        painter.setPen(QColor("white") if self._hovered else QColor(TEXT_PRI))
        painter.drawText(14, 26, 178, 30,
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        self.p.name)

        # Lifespan
        lf = QFont("Georgia", 9, QFont.Weight.Normal, True)
        painter.setFont(lf)
        painter.setPen(QColor(TEXT_SEC))
        painter.drawText(14, 56, 178, 18,
                        Qt.AlignmentFlag.AlignLeft,
                        self.p.lifespan_label)

        # Quote teaser
        if self.p.quotes:
            qf = QFont("Georgia", 8, QFont.Weight.Normal, True)
            painter.setFont(qf)
            painter.setPen(QColor(TEXT_DIM))
            q = self.p.quotes[0].text
            if len(q) > 48:
                q = q[:46] + "…"
            painter.drawText(14, 76, 178, 26,
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                            f"\u201c{q}\u201d")

        painter.end()

    def enterEvent(self, e):
        self._hovered = True
        self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.p.id)


class CountrySection(QWidget):
    """A section header + grid of cards for one country."""
    philosopher_clicked = pyqtSignal(int)

    def __init__(self, country: str, philosophers: list[Philosopher], parent=None):
        super().__init__(parent)
        self.country = country
        self.color = _country_color(country)
        self._build(philosophers)

    def _build(self, philosophers: list[Philosopher]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Country header
        header = QWidget()
        header.setFixedHeight(44)
        accent = QColor(self.color)
        accent_dim = QColor(self.color)
        accent_dim.setAlpha(40)
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {accent_dim.name(QColor.NameFormat.HexArgb)},
                    stop:1 transparent
                );
                border-left: 4px solid {self.color};
                border-radius: 4px;
            }}
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)

        name_lbl = QLabel(self.country)
        name_lbl.setStyleSheet(f"""
            color: {self.color};
            font-family: 'Georgia', serif;
            font-size: 15px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        h_layout.addWidget(name_lbl)

        count_lbl = QLabel(f"{len(philosophers)} philosopher{'s' if len(philosophers) != 1 else ''}")
        count_lbl.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 11px;
            background: transparent;
            border: none;
        """)
        h_layout.addWidget(count_lbl)
        h_layout.addStretch()

        layout.addWidget(header)

        # Card grid
        cards_widget = QWidget()
        cards_widget.setStyleSheet("background: transparent;")
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        for p in sorted(philosophers, key=lambda x: x.birth_year):
            card = PhilosopherCard(p, self.color)
            card.clicked.connect(self.philosopher_clicked)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        layout.addWidget(cards_widget)


class CountryView(QWidget):
    """Main country view — scroll area containing grouped country sections."""
    philosopher_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_BASE}; border: none; }}
        """)
        # Enable horizontal scroll so two-finger left/right swipe works
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.scroll)

        self.container = QWidget()
        self.container.setStyleSheet(f"background: {BG_BASE};")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(20, 20, 20, 20)
        self.container_layout.setSpacing(28)

        self.scroll.setWidget(self.container)
        # Install event filter on viewport to catch native gestures
        self.scroll.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        """Catch pinch-to-zoom and two-finger pan on the scroll viewport."""
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.NativeGesture:
            try:
                from PyQt6.QtGui import QNativeGestureEvent
                from PyQt6.QtCore import Qt as _Qt
                if isinstance(ev, QNativeGestureEvent):
                    if ev.gestureType() == _Qt.NativeGestureType.ZoomNativeGesture:
                        # Scale card sizes by adjusting the container margin as a proxy
                        # (simple: just scroll vertically proportionally)
                        factor = 1.0 + ev.value()
                        bar = self.scroll.verticalScrollBar()
                        bar.setValue(int(bar.value() / factor))
                        ev.accept()
                        return True
            except Exception:
                pass
        return super().eventFilter(obj, ev)

    def set_philosophers(self, philosophers: list[Philosopher]):
        # Clear old content
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not philosophers:
            empty = QLabel("No philosophers match your filters.")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-size: 14px; font-style: italic;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.container_layout.addWidget(empty)
            return

        # Group by country
        groups: dict[str, list[Philosopher]] = {}
        for p in philosophers:
            country = p.birth_country or "Unknown"
            groups.setdefault(country, []).append(p)

        for country in sorted(groups.keys()):
            section = CountrySection(country, groups[country])
            section.philosopher_clicked.connect(self.philosopher_clicked)
            self.container_layout.addWidget(section)
            # Thin divider
            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet(f"border: none; border-top: 1px solid {BORDER}; margin: 0;")
            self.container_layout.addWidget(div)

        self.container_layout.addStretch()
