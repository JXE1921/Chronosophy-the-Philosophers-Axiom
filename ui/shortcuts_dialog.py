"""
ui/shortcuts_dialog.py — Keyboard shortcuts reference modal.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM
)


_SHORTCUTS = [
    ("Navigation", [
        ("Ctrl + 1", "Switch to Timeline tab"),
        ("Ctrl + 2", "Switch to By Country tab"),
        ("Ctrl + 3", "Switch to Influence Graph tab"),
        ("Ctrl + 4", "Switch to World Map tab"),
        ("Ctrl + 5", "Switch to Statistics tab"),
    ]),
    ("Philosophers", [
        ("Ctrl + N", "Add new philosopher"),
        ("Ctrl + F", "Focus search bar"),
        ("Double-click (sidebar)", "Open detail view"),
        ("Enter (sidebar)", "Open detail view"),
        ("Delete (sidebar)", "Delete selected philosopher"),
    ]),
    ("Timeline", [
        ("Ctrl + Scroll", "Zoom in / out"),
        ("Scroll", "Pan left / right"),
        ("Middle-drag", "Pan horizontally and vertically"),
    ]),
    ("Influence Graph", [
        ("Scroll", "Zoom in / out"),
        ("Drag (empty space)", "Pan the canvas"),
        ("Drag (node)", "Reposition a philosopher node"),
        ("Click (node)", "Open detail view"),
    ]),
    ("General", [
        ("Ctrl + =  /  Ctrl + +", "Zoom UI in"),
        ("Ctrl + -", "Zoom UI out"),
        ("Ctrl + 0", "Reset UI zoom"),
        ("Ctrl + E", "Export to CSV"),
        ("F11", "Toggle fullscreen"),
        ("Ctrl + Q", "Quit"),
    ]),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(520, 580)
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
        header.setFixedHeight(52)
        header.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        icon = QLabel("⌨")
        icon.setStyleSheet(f"color: {GOLD}; font-size: 18px; background: transparent;")
        hl.addWidget(icon)
        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet(f"""
            color: {GOLD_LIGHT};
            font-family: 'Georgia', serif;
            font-size: 16px;
            background: transparent;
        """)
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(header)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(18)

        for section_name, bindings in _SHORTCUTS:
            # Section label
            section_lbl = QLabel(section_name.upper())
            section_lbl.setStyleSheet(f"""
                color: {GOLD};
                font-size: 9px;
                letter-spacing: 2.5px;
                background: transparent;
                border-bottom: 1px solid {BORDER};
                padding-bottom: 5px;
            """)
            layout.addWidget(section_lbl)

            for key, desc in bindings:
                row = QHBoxLayout()
                row.setSpacing(16)

                key_lbl = QLabel(key)
                key_lbl.setFixedWidth(180)
                key_lbl.setStyleSheet(f"""
                    background: {BG_RAISED};
                    border: 1px solid {BORDER_LT};
                    border-radius: 5px;
                    color: {GOLD_LIGHT};
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    padding: 4px 10px;
                """)
                row.addWidget(key_lbl)

                desc_lbl = QLabel(desc)
                desc_lbl.setStyleSheet(f"""
                    color: {TEXT_PRI};
                    font-size: 13px;
                    background: transparent;
                """)
                row.addWidget(desc_lbl, stretch=1)
                layout.addLayout(row)

        layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

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
