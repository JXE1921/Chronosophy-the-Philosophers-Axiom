"""
ui/quote_widget.py — Daily Wisdom Widget.
An elegant, prominent display of the day's chosen philosopher quote.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QBrush
import database as db
from styles import GOLD, GOLD_LIGHT, GOLD_DIM, GOLD_MUTED, BG_SURFACE, BG_RAISED, TEXT_PRI, TEXT_SEC, BORDER


class QuoteWidget(QWidget):
    """
    A self-contained daily quote panel.
    Fetches the day's quote from the DB and renders it with refined typography.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.quote_text = ""
        self.author_name = ""
        self._opacity = 1.0
        self._build_ui()
        self.refresh()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.setFixedHeight(180)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        # Left margin 42px gives clear breathing room after the accent bar (drawn at x=12)
        layout.setContentsMargins(42, 20, 28, 20)
        layout.setSpacing(10)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)

        # Glowing dot indicator
        self.dot = QLabel("◆")
        self.dot.setStyleSheet(f"color: {GOLD}; font-size: 9px; background: transparent;")
        header.addWidget(self.dot)

        lbl_title = QLabel("DAILY WISDOM")
        lbl_title.setStyleSheet(f"""
            color: {GOLD};
            font-family: 'Georgia', serif;
            font-size: 10px;
            letter-spacing: 3px;
            background: transparent;
        """)
        header.addWidget(lbl_title)
        header.addStretch()

        self.btn_refresh = QPushButton("↻  New Quote")
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {GOLD_DIM};
                border-radius: 4px;
                color: {GOLD_DIM};
                font-size: 11px;
                padding: 3px 10px;
                font-family: 'Georgia', serif;
            }}
            QPushButton:hover {{
                border-color: {GOLD};
                color: {GOLD};
                background: {GOLD_MUTED};
            }}
        """)
        self.btn_refresh.clicked.connect(self._force_refresh)
        header.addWidget(self.btn_refresh)

        layout.addLayout(header)

        # Quote text label
        self.lbl_quote = QLabel()
        self.lbl_quote.setWordWrap(True)
        self.lbl_quote.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_quote.setStyleSheet(f"""
            color: {TEXT_PRI};
            font-family: 'Georgia', serif;
            font-size: 15px;
            font-style: italic;
            line-height: 1.6;
            background: transparent;
        """)
        layout.addWidget(self.lbl_quote, stretch=1)

        # Author label
        self.lbl_author = QLabel()
        self.lbl_author.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_author.setStyleSheet(f"""
            color: {GOLD};
            font-family: 'Georgia', serif;
            font-size: 13px;
            letter-spacing: 0.5px;
            background: transparent;
        """)
        layout.addWidget(self.lbl_author)

    # ── Data loading ─────────────────────────────────────────────────────────

    def refresh(self):
        result = db.get_daily_quote()
        if result:
            self.quote_text, self.author_name = result
        else:
            self.quote_text = "Add philosophers and quotes to receive daily wisdom."
            self.author_name = ""
        self._update_labels()

    def _force_refresh(self):
        """Temporarily override daily cache to show a new random quote."""
        import sqlite3, random, os
        try:
            conn = sqlite3.connect(db.DB_PATH)
            conn.row_factory = sqlite3.Row
            all_q = conn.execute(
                "SELECT q.text, p.name FROM quotes q JOIN philosophers p ON p.id=q.philosopher_id"
            ).fetchall()
            if all_q:
                chosen = random.choice(all_q)
                self.quote_text = chosen["text"]
                self.author_name = chosen["name"]
            conn.close()
        except Exception:
            pass
        self._update_labels()

    def _update_labels(self):
        q = self.quote_text
        # Add typographic quote marks
        if q and not q.startswith("\u201c"):
            q = f"\u201c{q}\u201d"
        self.lbl_quote.setText(q)
        self.lbl_author.setText(f"— {self.author_name}" if self.author_name else "")

    # ── Custom paint — gradient border glow ──────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self.rect().adjusted(1, 1, -1, -1)

        # Background with subtle gold tint
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#16141E"))
        grad.setColorAt(1.0, QColor("#120E18"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r, 10, 10)

        # Left accent bar — sits at x=12, well clear of the text (which starts at x=42)
        accent = QColor(GOLD)
        accent.setAlpha(200)
        painter.setBrush(QBrush(accent))
        painter.drawRoundedRect(12, 20, 3, self.height() - 40, 2, 2)

        # Outer border with gold tint
        border_grad = QLinearGradient(0, 0, self.width(), 0)
        border_grad.setColorAt(0.0, QColor(GOLD_DIM))
        border_grad.setColorAt(0.5, QColor(GOLD).lighter(110))
        border_grad.setColorAt(1.0, QColor(GOLD_DIM))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QBrush(border_grad), 1.2)
        painter.setPen(pen)
        painter.drawRoundedRect(r, 10, 10)

        super().paintEvent(event)
