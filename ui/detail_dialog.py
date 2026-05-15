"""
ui/detail_dialog.py — Full philosopher detail view (read-only modal).

v7 changes:
- Sized to fit a 14" laptop: caps at 85 % of the current screen height
- Tighter banner / spacing so the whole dialog is more compact
- Favourite buttons fire on pressed (light tap) not clicked (full press+release)
- No philosopher-level favouriting — only individual quotes can be favourited
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import database as db
from database import Philosopher, Quote
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, GOLD_MUTED, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, ERA_COLORS, FAVOURITE
)


class DetailDialog(QDialog):
    """Read-only detailed profile of a philosopher."""

    show_in_graph   = pyqtSignal(int)   # philosopher_id
    favourite_toggled = pyqtSignal()    # parent refreshes stats / list

    def __init__(self, philosopher: Philosopher, parent=None):
        super().__init__(parent)
        self.p = philosopher
        self.setWindowTitle(philosopher.name)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {BG_BASE}; }}")
        if parent and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())

        # ── Fit to screen: cap height at 85 % of the available screen area
        screen = QApplication.primaryScreen().availableGeometry()
        max_h  = int(screen.height() * 0.85)
        max_w  = min(620, int(screen.width() * 0.55))
        self.setMinimumWidth(480)
        self.setMinimumHeight(420)
        self.resize(max_w, min(max_h, 640))
        self.setMaximumHeight(max_h)

        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Compact header banner ─────────────────────────────────────────
        era_color = ERA_COLORS.get(self.p.era, "#4A5E7E")
        banner = QWidget()
        banner.setFixedHeight(86)
        banner.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {era_color}, stop:1 #0C0C0E
            );
        """)
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(22, 12, 22, 10)
        bl.setSpacing(2)

        era_lbl = QLabel(self.p.era.upper())
        era_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.5);font-size:9px;letter-spacing:3px;background:transparent;"
        )
        bl.addWidget(era_lbl)

        name_lbl = QLabel(self.p.name)
        name_lbl.setStyleSheet(
            "color:white;font-family:'Georgia',serif;font-size:20px;background:transparent;"
        )
        bl.addWidget(name_lbl)

        lifespan_lbl = QLabel(self.p.lifespan_label)
        lifespan_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.65);font-size:12px;font-style:italic;background:transparent;"
        )
        bl.addWidget(lifespan_lbl)

        root.addWidget(banner)

        # ── Scrollable body ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        b = QVBoxLayout(body)
        b.setContentsMargins(22, 14, 22, 18)
        b.setSpacing(12)

        # Info chips
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        if self.p.birth_city or self.p.birth_country:
            place = ", ".join(filter(None, [self.p.birth_city, self.p.birth_country]))
            info_row.addWidget(self._info_chip("📍  " + place))
        if self.p.teachers:
            info_row.addWidget(self._info_chip("📚  " + self.p.teachers))
        info_row.addStretch()
        b.addLayout(info_row)

        # Contributions
        if self.p.contributions:
            b.addWidget(self._section_header("CONTRIBUTIONS & SIGNIFICANCE"))
            contrib = QLabel(self.p.contributions)
            contrib.setWordWrap(True)
            contrib.setStyleSheet(f"""
                color: {TEXT_PRI};
                font-size: 13px;
                line-height: 1.6;
                background: transparent;
                font-family: 'Georgia', serif;
            """)
            b.addWidget(contrib)

        # Quotes
        if self.p.quotes:
            b.addWidget(self._section_header(f"QUOTES  ({len(self.p.quotes)})"))
            for quote in self.p.quotes:
                b.addWidget(self._quote_card(quote))

        b.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # ── Button bar ────────────────────────────────────────────────────
        btn_bar = QWidget()
        btn_bar.setFixedHeight(50)
        btn_bar.setStyleSheet(f"background: {BG_SURFACE}; border-top: 1px solid {BORDER};")
        bb = QHBoxLayout(btn_bar)
        bb.setContentsMargins(20, 0, 20, 0)
        bb.setSpacing(8)

        btn_graph = QPushButton("🕸  Show in Graph")
        btn_graph.setToolTip("Open the influence graph centred on this philosopher")
        btn_graph.clicked.connect(self._on_show_in_graph)
        bb.addWidget(btn_graph)

        bb.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_primary")
        btn_close.setMinimumWidth(90)
        btn_close.clicked.connect(self.accept)
        bb.addWidget(btn_close)
        root.addWidget(btn_bar)

    # ─────────────────────────────────────────────────────────────────────────

    def _on_show_in_graph(self):
        self.show_in_graph.emit(self.p.id)
        self.accept()

    def _info_chip(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background: {BG_RAISED};
            border: 1px solid {BORDER};
            border-radius: 14px;
            color: {TEXT_SEC};
            font-size: 11px;
            padding: 3px 10px;
            font-family: 'Georgia', serif;
        """)
        return lbl

    def _section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {GOLD};
            font-size: 9px;
            letter-spacing: 2.5px;
            font-family: 'Georgia', serif;
            padding-top: 2px;
            background: transparent;
            border-bottom: 1px solid {BORDER};
            padding-bottom: 5px;
        """)
        return lbl

    def _quote_card(self, quote: Quote) -> QWidget:
        card = QWidget()
        card.setObjectName("quotecard")
        card.setStyleSheet(f"""
            QWidget#quotecard {{
                background: {BG_SURFACE};
                border-left: 3px solid {GOLD_DIM};
                border-radius: 4px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(8)

        lbl = QLabel(f"\u201c{quote.text}\u201d")
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl.setStyleSheet(f"""
            color: {TEXT_PRI};
            font-size: 12px;
            font-style: italic;
            line-height: 1.6;
            background: transparent;
            font-family: 'Georgia', serif;
        """)
        layout.addWidget(lbl, stretch=1)

        # ── Favourite button — fires on pressed so a light trackpad tap registers
        fav_btn = QPushButton()
        fav_btn.setFixedSize(30, 30)
        fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Disable the default focus rect so the button stays clean
        fav_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def _style(is_fav: bool):
            fav_btn.setText("♥" if is_fav else "♡")
            if is_fav:
                fav_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: 1px solid {FAVOURITE};
                        border-radius: 15px;
                        color: {FAVOURITE};
                        font-size: 15px;
                    }}
                    QPushButton:hover {{ background: rgba(224,160,80,0.15); }}
                """)
                fav_btn.setToolTip("Remove from favourites")
            else:
                fav_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: 1px solid {BORDER_LT};
                        border-radius: 15px;
                        color: {TEXT_DIM};
                        font-size: 15px;
                    }}
                    QPushButton:hover {{ border-color: {FAVOURITE}; color: {FAVOURITE}; }}
                """)
                fav_btn.setToolTip("Add to favourites")

        _style(quote.is_favourite)

        def _on_press():
            """Fire on the initial press/tap — no need to release first."""
            new = db.toggle_quote_favourite(quote.id)
            quote.is_favourite = new
            _style(new)
            self.favourite_toggled.emit()

        # Use pressed (not clicked) so a soft trackpad tap immediately toggles
        fav_btn.pressed.connect(_on_press)
        layout.addWidget(fav_btn, alignment=Qt.AlignmentFlag.AlignTop)

        return card
