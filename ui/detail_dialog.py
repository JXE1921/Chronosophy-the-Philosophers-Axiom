"""
ui/detail_dialog.py — Full philosopher detail view (read-only modal).

v10 changes:
- Sized to fit a 14" laptop: caps at 85 % of the current screen height
- Tighter banner / spacing so the whole dialog is more compact
- Favourite buttons fire on pressed (light tap) not clicked (full press+release)
- No philosopher-level favouriting — only individual quotes can be favourited
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QSizePolicy, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QDesktopServices
import os
import database as db
from database import Philosopher, Quote, Work
import library
from ui import image_utils
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

        # ── Compact header banner (portrait + identity) ───────────────────
        era_color = ERA_COLORS.get(self.p.era, "#4A5E7E")
        banner = QWidget()
        banner.setFixedHeight(104)
        banner.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {era_color}, stop:1 #0C0C0E
            );
        """)
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(22, 12, 22, 12)
        bl.setSpacing(16)

        # Framed portrait (or monogram fallback) on the left
        portrait = QLabel()
        portrait.setFixedSize(78, 78)
        portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        portrait.setStyleSheet("background: transparent; border: none;")
        portrait.setPixmap(self._portrait_pixmap(78, radius=12))
        self._portrait_label = portrait
        bl.addWidget(portrait, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Identity text on the right
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addStretch()

        era_lbl = QLabel(self.p.era.upper())
        era_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.5);font-size:9px;letter-spacing:3px;background:transparent;"
        )
        text_col.addWidget(era_lbl)

        name_lbl = QLabel(self.p.name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            "color:white;font-family:'Georgia',serif;font-size:20px;background:transparent;"
        )
        text_col.addWidget(name_lbl)

        lifespan_lbl = QLabel(self.p.lifespan_label)
        lifespan_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.65);font-size:12px;font-style:italic;background:transparent;"
        )
        text_col.addWidget(lifespan_lbl)
        text_col.addStretch()

        bl.addLayout(text_col, stretch=1)
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

        # Works & bibliography
        if self.p.works:
            b.addWidget(self._section_header(f"WORKS & BIBLIOGRAPHY  ({len(self.p.works)})"))
            for work in self.p.works:
                b.addWidget(self._work_card(work))

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

    def showEvent(self, event):
        super().showEvent(event)
        # Re-render the portrait at the real display dpr now we are on screen.
        if hasattr(self, "_portrait_label"):
            self._portrait_label.setPixmap(self._portrait_pixmap(78, radius=12))

    # ── Portrait ─────────────────────────────────────────────────────────────

    def _portrait_pixmap(self, size: int, radius: int = 12):
        dpr = self.devicePixelRatioF() or 1.0
        abs_path = library.abs_path(self.p.portrait_path)
        if abs_path:
            pm = image_utils.framed_pixmap(
                abs_path, size, size, dpr,
                radius=radius, border_color="rgba(255,255,255,0.35)", border_width=1.5,
            )
            if pm is not None:
                return pm
        # Fallback: a translucent framed monogram that reads on the banner gradient
        return image_utils.monogram_pixmap(
            self.p.name, size, size, dpr, radius=radius,
            bg="rgba(0,0,0,0.28)", fg="white",
            border_color="rgba(255,255,255,0.35)", border_width=1.5,
        )

    # ── Works ────────────────────────────────────────────────────────────────

    def _work_card(self, work: Work) -> QWidget:
        card = QWidget()
        card.setObjectName("workcard")
        card.setStyleSheet(f"""
            QWidget#workcard {{
                background: {BG_SURFACE};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(10)

        icon = QLabel("📖" if not work.has_file else "📎")
        icon.setStyleSheet("background: transparent; font-size: 14px;")
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        title = QLabel(work.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"""
            color: {TEXT_PRI}; font-size: 13px; background: transparent;
            font-family: 'Georgia', serif;
        """)
        text_col.addWidget(title)
        if work.has_file:
            sub = QLabel(work.original_filename or "Attached file")
            sub.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; background: transparent;")
            text_col.addWidget(sub)
        layout.addLayout(text_col, stretch=1)

        if work.has_file:
            btn_open = QPushButton("Open")
            btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setMinimumWidth(72)
            btn_open.setToolTip(f"Open “{work.original_filename or work.title}” in its default app")
            btn_open.clicked.connect(lambda _, w=work: self._open_work(w))
            layout.addWidget(btn_open, alignment=Qt.AlignmentFlag.AlignVCenter)

        return card

    def _open_work(self, work: Work):
        abs_path = library.abs_path(work.file_path)
        if not abs_path or not os.path.isfile(abs_path):
            QMessageBox.warning(
                self, "File not found",
                f"The attached file for “{work.title}” could not be found.\n\n"
                "It may have been moved or deleted from the library folder. "
                "Edit this philosopher to re-attach it.",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

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
