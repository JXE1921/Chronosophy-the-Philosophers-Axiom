"""
ui/detail_dialog.py — Full philosopher detail view (read-only modal).
Shows all data beautifully formatted with their quotes.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from database import Philosopher
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, GOLD_MUTED, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, ERA_COLORS
)


class DetailDialog(QDialog):
    """Read-only detailed profile of a philosopher."""

    def __init__(self, philosopher: Philosopher, parent=None):
        super().__init__(parent)
        self.p = philosopher
        self.setWindowTitle(philosopher.name)
        self.setMinimumWidth(580)
        self.setMinimumHeight(700)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {BG_BASE}; }}")
        # Inherit the app-wide icon so every dialog shows it in the title bar
        if parent and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header banner
        era_color = ERA_COLORS.get(self.p.era, "#4A5E7E")
        banner = QWidget()
        banner.setFixedHeight(110)
        banner.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {era_color},
                stop:1 #0C0C0E
            );
        """)
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(28, 18, 28, 14)
        b_layout.setSpacing(4)

        era_lbl = QLabel(self.p.era.upper())
        era_lbl.setStyleSheet(f"""
            color: rgba(255,255,255,0.5);
            font-size: 10px;
            letter-spacing: 3px;
            background: transparent;
        """)
        b_layout.addWidget(era_lbl)

        name_lbl = QLabel(self.p.name)
        name_lbl.setStyleSheet(f"""
            color: white;
            font-family: 'Georgia', serif;
            font-size: 26px;
            background: transparent;
        """)
        b_layout.addWidget(name_lbl)

        lifespan_lbl = QLabel(self.p.lifespan_label)
        lifespan_lbl.setStyleSheet(f"""
            color: rgba(255,255,255,0.65);
            font-size: 13px;
            font-style: italic;
            background: transparent;
        """)
        b_layout.addWidget(lifespan_lbl)

        root.addWidget(banner)

        # ── Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        b = QVBoxLayout(body)
        b.setContentsMargins(28, 22, 28, 28)
        b.setSpacing(18)

        # Info row
        info_row = QHBoxLayout()
        info_row.setSpacing(24)
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
                font-size: 14px;
                line-height: 1.7;
                background: transparent;
                font-family: 'Georgia', serif;
            """)
            b.addWidget(contrib)

        # Quotes
        if self.p.quotes:
            b.addWidget(self._section_header(f"QUOTES  ({len(self.p.quotes)})"))
            for quote in self.p.quotes:
                b.addWidget(self._quote_card(quote.text))

        b.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # ── Close button bar
        btn_bar = QWidget()
        btn_bar.setFixedHeight(56)
        btn_bar.setStyleSheet(f"background: {BG_SURFACE}; border-top: 1px solid {BORDER};")
        bb = QHBoxLayout(btn_bar)
        bb.setContentsMargins(24, 0, 24, 0)
        bb.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_primary")
        btn_close.setMinimumWidth(100)
        btn_close.clicked.connect(self.accept)
        bb.addWidget(btn_close)
        root.addWidget(btn_bar)

    def _info_chip(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background: {BG_RAISED};
            border: 1px solid {BORDER};
            border-radius: 16px;
            color: {TEXT_SEC};
            font-size: 12px;
            padding: 4px 12px;
            font-family: 'Georgia', serif;
        """)
        return lbl

    def _section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {GOLD};
            font-size: 10px;
            letter-spacing: 2.5px;
            font-family: 'Georgia', serif;
            padding-top: 4px;
            background: transparent;
            border-bottom: 1px solid {BORDER};
            padding-bottom: 6px;
        """)
        return lbl

    def _quote_card(self, text: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: {BG_SURFACE};
                border-left: 3px solid {GOLD_DIM};
                border-radius: 4px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        lbl = QLabel(f"\u201c{text}\u201d")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            color: {TEXT_PRI};
            font-size: 13px;
            font-style: italic;
            line-height: 1.6;
            background: transparent;
            font-family: 'Georgia', serif;
        """)
        layout.addWidget(lbl)
        return card
