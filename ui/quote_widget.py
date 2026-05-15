"""
ui/quote_widget.py — Daily Wisdom Widget.
An elegant, prominent display of the day's chosen philosopher quote.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QBrush
import database as db
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, GOLD_MUTED, BG_SURFACE, BG_RAISED,
    TEXT_PRI, TEXT_SEC, BORDER, FAVOURITE
)


class QuoteWidget(QWidget):
    """A self-contained daily quote panel with smooth fade transitions."""

    # Emitted when the favourite button is toggled, with the new state
    favourite_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.quote_text = ""
        self.author_name = ""
        self._current_quote_id: int | None = None
        self._current_is_fav = False

        # Opacity effect powers the fade animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)

        self._fade_out: QPropertyAnimation | None = None
        self._fade_in: QPropertyAnimation | None = None

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

        # ── Inner content widget so we can apply the opacity effect to just
        # the contents (not the painted border/background)
        self._content = QWidget(self)
        self._content.setStyleSheet("background: transparent;")
        self._content.setGraphicsEffect(self._opacity_effect)

        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        layout.addWidget(self._content)

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

        # Favourite button
        self.btn_fav = QPushButton("♡")
        self.btn_fav.setFixedSize(28, 28)
        self.btn_fav.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_fav.setToolTip("Add this quote to favourites")
        # pressed fires on initial touch — light trackpad tap is enough
        self.btn_fav.pressed.connect(self._on_toggle_favourite)
        self._style_fav_button(False)
        header.addWidget(self.btn_fav)

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
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setToolTip("Show a different random quote (doesn't change today's daily quote)")
        self.btn_refresh.clicked.connect(self._force_refresh)
        header.addWidget(self.btn_refresh)

        content_layout.addLayout(header)

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
        content_layout.addWidget(self.lbl_quote, stretch=1)

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
        content_layout.addWidget(self.lbl_author)

    def _style_fav_button(self, is_fav: bool):
        """Restyle the favourite button to reflect current state."""
        self.btn_fav.setText("♥" if is_fav else "♡")
        if is_fav:
            self.btn_fav.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {FAVOURITE};
                    border-radius: 14px;
                    color: {FAVOURITE};
                    font-size: 14px;
                }}
                QPushButton:hover {{ background: rgba(224, 160, 80, 0.15); }}
            """)
            self.btn_fav.setToolTip("Remove from favourites")
        else:
            self.btn_fav.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {GOLD_DIM};
                    border-radius: 14px;
                    color: {GOLD_DIM};
                    font-size: 14px;
                }}
                QPushButton:hover {{ border-color: {GOLD}; color: {GOLD}; }}
            """)
            self.btn_fav.setToolTip("Add this quote to favourites")

    # ── Data loading ─────────────────────────────────────────────────────────

    def refresh(self):
        """Reload the daily quote (used on startup and after CRUD changes)."""
        result = db.get_daily_quote()
        if result:
            self.quote_text, self.author_name = result
        else:
            self.quote_text = "Add philosophers and quotes to receive daily wisdom."
            self.author_name = ""
        self._sync_current_quote_meta()
        self._update_labels(animated=False)

    def _force_refresh(self):
        """Show a different random quote with a fade transition.
        Does NOT update the daily-quote cache.
        """
        result = db.get_random_quote()
        if not result:
            return
        self.quote_text, self.author_name = result
        self._sync_current_quote_meta()
        self._update_labels(animated=True)

    def _sync_current_quote_meta(self):
        """Look up the quote ID and favourite state for the currently shown quote.
        Needed so the heart button can toggle the right row.
        """
        import sqlite3
        if not self.quote_text or not self.author_name:
            self._current_quote_id = None
            self._current_is_fav = False
            self.btn_fav.setEnabled(False)
            self._style_fav_button(False)
            return
        try:
            conn = sqlite3.connect(db.DB_PATH)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT q.id, q.is_favourite FROM quotes q
                    JOIN philosophers p ON p.id = q.philosopher_id
                    WHERE q.text=? AND p.name=? LIMIT 1""",
                (self.quote_text, self.author_name)
            ).fetchone()
            conn.close()
            if row:
                self._current_quote_id = row["id"]
                self._current_is_fav = bool(row["is_favourite"])
                self.btn_fav.setEnabled(True)
            else:
                self._current_quote_id = None
                self._current_is_fav = False
                self.btn_fav.setEnabled(False)
        except Exception:
            self._current_quote_id = None
            self._current_is_fav = False
            self.btn_fav.setEnabled(False)
        self._style_fav_button(self._current_is_fav)

    def _on_toggle_favourite(self):
        if self._current_quote_id is None:
            return
        new_state = db.toggle_quote_favourite(self._current_quote_id)
        self._current_is_fav = new_state
        self._style_fav_button(new_state)
        self.favourite_toggled.emit(new_state)

    # ── Label rendering with optional fade ───────────────────────────────────

    def _update_labels(self, animated: bool = False):
        if animated:
            self._fade_swap()
        else:
            self._write_labels()

    def _write_labels(self):
        q = self.quote_text
        if q and not q.startswith("\u201c"):
            q = f"\u201c{q}\u201d"
        self.lbl_quote.setText(q)
        self.lbl_author.setText(f"— {self.author_name}" if self.author_name else "")

    def _fade_swap(self):
        """Fade content out, swap text, fade back in."""
        # Stop any running animations to avoid stacking
        if self._fade_out and self._fade_out.state() == QPropertyAnimation.State.Running:
            self._fade_out.stop()
        if self._fade_in and self._fade_in.state() == QPropertyAnimation.State.Running:
            self._fade_in.stop()

        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(180)
        self._fade_out.setStartValue(self._opacity_effect.opacity())
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def _on_faded_out():
            self._write_labels()
            self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._fade_in.setDuration(280)
            self._fade_in.setStartValue(0.0)
            self._fade_in.setEndValue(1.0)
            self._fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._fade_in.start()

        self._fade_out.finished.connect(_on_faded_out)
        self._fade_out.start()

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

        # Left accent bar
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
