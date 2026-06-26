"""
ui/comparison_dialog.py — Side-by-side comparison of two philosophers.

Useful for quickly contrasting eras, contributions, and signature quotes.
Two parallel column panels rendered with the existing detail-card aesthetic.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt
from database import Philosopher
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, ERA_COLORS
)


class ComparisonDialog(QDialog):
    """Two-column read-only comparison dialog."""

    def __init__(self, left: Philosopher, right: Philosopher, parent=None):
        super().__init__(parent)
        self.left = left
        self.right = right
        self.setWindowTitle(f"Compare: {left.name} vs {right.name}")
        self.setMinimumSize(960, 720)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {BG_BASE}; }}")
        if parent and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        icon = QLabel("⇆")
        icon.setStyleSheet(f"color: {GOLD}; font-size: 18px; background: transparent;")
        hl.addWidget(icon)
        title = QLabel("Side-by-side comparison")
        title.setStyleSheet(f"""
            color: {GOLD_LIGHT};
            font-family: 'Georgia', serif;
            font-size: 16px;
            background: transparent;
        """)
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(header)

        # Body — two columns side by side
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(20, 20, 20, 20)
        bl.setSpacing(16)

        bl.addWidget(self._build_column(self.left), stretch=1)

        # Vertical divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {BORDER}; background: {BORDER}; max-width: 1px;")
        sep.setFixedWidth(1)
        bl.addWidget(sep)

        bl.addWidget(self._build_column(self.right), stretch=1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # Footer — close button
        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet(f"background: {BG_SURFACE}; border-top: 1px solid {BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        fl.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_primary")
        btn_close.setMinimumWidth(100)
        btn_close.clicked.connect(self.accept)
        fl.addWidget(btn_close)
        root.addWidget(footer)

    def _build_column(self, p: Philosopher) -> QWidget:
        col = QWidget()
        col.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        era_color = ERA_COLORS.get(p.era, "#4A5E7E")

        # Banner
        banner = QWidget()
        banner.setFixedHeight(96)
        banner.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {era_color},
                stop:1 #0C0C0E
            );
            border-radius: 8px;
        """)
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(20, 14, 20, 14)
        bl.setSpacing(2)

        era_lbl = QLabel(p.era.upper())
        era_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 9px; letter-spacing: 2.5px; background: transparent;"
        )
        bl.addWidget(era_lbl)

        name_lbl = QLabel(p.name)
        name_lbl.setStyleSheet(
            "color: white; font-family: 'Georgia', serif; font-size: 20px; background: transparent;"
        )
        bl.addWidget(name_lbl)

        life_lbl = QLabel(p.lifespan_label)
        life_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.65); font-size: 12px; font-style: italic; background: transparent;"
        )
        bl.addWidget(life_lbl)
        layout.addWidget(banner)

        # Quick facts
        facts = [
            ("Country", p.birth_country or "—"),
            ("City", p.birth_city or "—"),
            ("Teachers", p.teachers or "—"),
            ("Quotes", str(len(p.quotes))),
        ]
        for label, value in facts:
            row = QHBoxLayout()
            row.setSpacing(10)
            lbl = QLabel(label.upper())
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"""
                color: {TEXT_DIM};
                font-size: 9px;
                letter-spacing: 1.5px;
                background: transparent;
            """)
            val = QLabel(value)
            val.setWordWrap(True)
            val.setStyleSheet(f"""
                color: {TEXT_PRI};
                font-size: 12px;
                background: transparent;
                font-family: 'Georgia', serif;
            """)
            row.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignTop)
            row.addWidget(val, stretch=1)
            layout.addLayout(row)

        # Section: contributions
        layout.addWidget(self._section_header("CONTRIBUTIONS"))
        contrib = QLabel(p.contributions or "—")
        contrib.setWordWrap(True)
        contrib.setStyleSheet(f"""
            color: {TEXT_PRI};
            font-size: 12.5px;
            line-height: 1.6;
            background: transparent;
            font-family: 'Georgia', serif;
        """)
        layout.addWidget(contrib)

        # Section: signature quote(s) — show up to 2
        layout.addWidget(self._section_header("SIGNATURE QUOTE"))
        if p.quotes:
            for q in p.quotes[:2]:
                card = QLabel(f"\u201c{q.text}\u201d")
                card.setWordWrap(True)
                card.setStyleSheet(f"""
                    background: {BG_SURFACE};
                    border-left: 3px solid {GOLD_DIM};
                    border-radius: 4px;
                    color: {TEXT_PRI};
                    font-size: 12.5px;
                    font-style: italic;
                    line-height: 1.6;
                    padding: 12px 14px;
                    font-family: 'Georgia', serif;
                """)
                layout.addWidget(card)
        else:
            empty = QLabel("No quotes recorded.")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-style: italic; background: transparent;")
            layout.addWidget(empty)

        layout.addStretch()
        return col

    def _section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {GOLD};
            font-size: 9px;
            letter-spacing: 2px;
            font-family: 'Georgia', serif;
            padding-top: 10px;
            background: transparent;
            border-bottom: 1px solid {BORDER};
            padding-bottom: 4px;
        """)
        return lbl
