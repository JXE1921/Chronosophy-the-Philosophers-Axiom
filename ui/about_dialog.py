"""
ui/about_dialog.py — "About Chronosophy" modal.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PyQt6.QtCore import Qt
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, TEXT_PRI, TEXT_SEC, TEXT_DIM
)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Chronosophy")
        self.setFixedSize(480, 360)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {BG_BASE}; }}")
        if parent and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Banner
        banner = QWidget()
        banner.setFixedHeight(120)
        banner.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #1A1228,
                stop:1 #0C0C0E
            );
        """)
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(32, 24, 32, 24)
        bl.setSpacing(4)

        logo_row = QHBoxLayout()
        logo = QLabel("⟁")
        logo.setStyleSheet(f"color: {GOLD}; font-size: 28px; background: transparent;")
        logo_row.addWidget(logo)

        title = QLabel("Chronosophy")
        title.setStyleSheet(f"""
            color: {GOLD_LIGHT};
            font-family: 'Georgia', serif;
            font-size: 24px;
            background: transparent;
        """)
        logo_row.addWidget(title)
        logo_row.addStretch()
        bl.addLayout(logo_row)

        subtitle = QLabel("The Philosopher's Axiom  ·  v3.0")
        subtitle.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-family: 'Georgia', serif;
            font-size: 12px;
            font-style: italic;
            background: transparent;
        """)
        bl.addWidget(subtitle)
        root.addWidget(banner)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 22, 32, 22)
        layout.setSpacing(14)

        desc = QLabel(
            "Chronosophy is a personal archive of human thought — "
            "mapping the lives, origins, and ideas of history's greatest minds across time and place. "
            "Built out of curiosity and a love for ideas, it's a quiet space to explore the philosophers who shaped how we think, "
            "organised by when they lived, where they came from, and the questions they refused to stop asking."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"""
            color: {TEXT_PRI};
            font-family: 'Georgia', serif;
            font-size: 13px;
            line-height: 1.6;
            background: transparent;
        """)
        layout.addWidget(desc)

        built_with = QLabel("Built with PyQt6 · SQLite · Pure Python")
        built_with.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 11px;
            background: transparent;
            font-style: italic;
        """)
        layout.addWidget(built_with)

        layout.addStretch()
        root.addWidget(body, stretch=1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(52)
        footer.setStyleSheet(f"background: {BG_SURFACE}; border-top: 1px solid {BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        fl.addStretch()
        btn = QPushButton("Close")
        btn.setObjectName("btn_primary")
        btn.setMinimumWidth(90)
        btn.clicked.connect(self.accept)
        fl.addWidget(btn)
        root.addWidget(footer)
