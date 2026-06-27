"""
ui/quote_dialog.py — Focused single-quote viewer.

Opened when a favourited quote card in the sidebar is double-clicked. Unlike the
full philosopher DetailDialog, this shows nothing but the quote itself and the
philosopher's name — large, centred and uncluttered.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QScrollArea, QFrame, QApplication
)
from PyQt6.QtCore import Qt
from styles import (
    GOLD, BG_BASE, BG_SURFACE, BORDER, TEXT_PRI
)


class QuoteDialog(QDialog):
    """A small, elegant modal showing a single quote and its author."""

    def __init__(self, quote_text: str, author: str, parent=None):
        super().__init__(parent)
        self._quote = " ".join((quote_text or "").split())   # collapse whitespace
        self._author = (author or "").strip()
        # Follow the app-wide UI zoom so this reading-focused window matches the
        # rest of the interface (the favourite cards that launch it scale too).
        self._scale = max(0.6, min(2.0, float(getattr(parent, "_ui_scale", 1.0) or 1.0)))

        self.setWindowTitle(f"Quote — {self._author}" if self._author else "Quote")
        self.setModal(True)
        if parent is not None and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())
        self.setStyleSheet(f"QDialog {{ background: {BG_BASE}; }}")

        # Fixed width keeps the wrapping predictable; height fits the content,
        # capped to the screen (a scroll area handles anything longer).
        screen = QApplication.primaryScreen().availableGeometry()
        width = max(360, min(560, int(screen.width() * 0.5)))
        self.setFixedWidth(width)
        self._max_h = int(screen.height() * 0.85)
        self.setMaximumHeight(self._max_h)

        self._build_ui()
        self._fit_height(width)

    # ─────────────────────────────────────────────────────────────────────────

    def _px(self, base: float) -> int:
        return max(7, round(base * self._scale))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scrollable content (long quotes scroll instead of clipping) ──────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._panel = QWidget()
        self._panel.setObjectName("quotepanel")
        self._panel.setStyleSheet(f"QWidget#quotepanel {{ background: {BG_SURFACE}; }}")
        pl = QVBoxLayout(self._panel)
        pl.setContentsMargins(44, 28, 44, 26)
        pl.setSpacing(12)

        # Decorative opening quotation mark
        glyph = QLabel("“")
        glyph.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        glyph.setStyleSheet(
            f"color: {GOLD}; font-family: 'Georgia', serif; font-size: {self._px(54)}px;"
            " background: transparent; border: none;"
        )
        pl.addWidget(glyph)

        # The quote body — large, centred, selectable
        body = QLabel(self._quote)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet(
            f"color: {TEXT_PRI}; font-family: 'Georgia', serif; font-size: {self._px(21)}px;"
            " font-style: italic; background: transparent; border: none;"
        )
        pl.addWidget(body)

        # Author
        if self._author:
            pl.addSpacing(4)
            author_lbl = QLabel(f"— {self._author}")
            author_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            author_lbl.setStyleSheet(
                f"color: {GOLD}; font-family: 'Georgia', serif; font-size: {self._px(15)}px;"
                " letter-spacing: 0.5px; background: transparent; border: none;"
            )
            pl.addWidget(author_lbl)

        scroll.setWidget(self._panel)
        root.addWidget(scroll, stretch=1)

        # ── Button bar ───────────────────────────────────────────────────────
        bar = QWidget()
        bar.setObjectName("quotebar")
        bar.setFixedHeight(54)
        bar.setStyleSheet(
            f"QWidget#quotebar {{ background: {BG_SURFACE}; border-top: 1px solid {BORDER}; }}"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(20, 0, 20, 0)
        bl.addStretch()

        btn = QPushButton("Close")
        btn.setObjectName("btn_primary")
        btn.setMinimumWidth(96)
        btn.clicked.connect(self.accept)
        bl.addWidget(btn)

        root.addWidget(bar)

    def _fit_height(self, width: int):
        """Size the window to its content, capped at 85% of the screen height.
        Anything taller scrolls rather than being clipped."""
        self._panel.setFixedWidth(width)
        self._panel.adjustSize()
        content_h = self._panel.sizeHint().height()
        self._panel.setMinimumWidth(0)
        self._panel.setMaximumWidth(16777215)
        total = content_h + 54 + 2          # + button bar + slack
        self.resize(width, min(total, self._max_h))
