"""
ui/search_bar.py — Search, filter, and sort controls.
Emits a signal whenever the user changes any filter so the parent can reload data.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QComboBox, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from styles import (
    GOLD, GOLD_DIM, BG_SURFACE, BG_RAISED, BORDER, BORDER_LT,
    TEXT_PRI, TEXT_SEC, TEXT_DIM
)


class SearchBar(QWidget):
    """
    Compact filter bar. Emits `filters_changed(query, country, era, sort)`.
    Uses a short debounce on text input so rapid typing doesn't hammer the DB.
    """
    filters_changed = pyqtSignal(str, str, str, str)

    ERAS = [
        "All", "Pre-Socratic", "Classical", "Hellenistic / Roman",
        "Medieval", "Renaissance", "Early Modern", "Modern", "Contemporary",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            QWidget {{
                background: {BG_SURFACE};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        self._debounce = QTimer(singleShot=True, interval=280)
        self._debounce.timeout.connect(self._emit)
        self._build_ui()
        self._country_list: list[str] = []

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Search input
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍  Search philosophers…")
        self.inp_search.setFixedWidth(240)
        self.inp_search.textChanged.connect(lambda: self._debounce.start())
        self.inp_search.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_RAISED};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                color: {TEXT_PRI};
                font-size: 13px;
                font-family: 'Georgia', serif;
            }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)
        layout.addWidget(self.inp_search)

        sep = QLabel("|")
        sep.setStyleSheet(f"color: {BORDER}; background: transparent; border: none;")
        layout.addWidget(sep)

        # Country filter
        lbl_c = QLabel("Country")
        lbl_c.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(lbl_c)

        self.cmb_country = QComboBox()
        self.cmb_country.addItem("All")
        self.cmb_country.setFixedWidth(150)
        self.cmb_country.currentTextChanged.connect(self._emit)
        layout.addWidget(self.cmb_country)

        # Era filter
        lbl_e = QLabel("Era")
        lbl_e.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(lbl_e)

        self.cmb_era = QComboBox()
        for era in self.ERAS:
            self.cmb_era.addItem(era)
        self.cmb_era.setFixedWidth(170)
        self.cmb_era.currentTextChanged.connect(self._emit)
        layout.addWidget(self.cmb_era)

        # Sort
        lbl_s = QLabel("Sort")
        lbl_s.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(lbl_s)

        self.cmb_sort = QComboBox()
        self.cmb_sort.addItems(["By Lifespan", "By Name"])
        self.cmb_sort.setFixedWidth(120)
        self.cmb_sort.currentTextChanged.connect(self._emit)
        layout.addWidget(self.cmb_sort)

        layout.addStretch()

        # Clear button
        btn_clear = QPushButton("✕  Clear")
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {TEXT_DIM};
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {GOLD_DIM}; }}
        """)
        btn_clear.clicked.connect(self._clear_filters)
        layout.addWidget(btn_clear)

    def update_countries(self, countries: list[str]):
        """Repopulate country dropdown (call after DB changes)."""
        current = self.cmb_country.currentText()
        self.cmb_country.blockSignals(True)
        self.cmb_country.clear()
        self.cmb_country.addItem("All")
        for c in countries:
            self.cmb_country.addItem(c)
        idx = self.cmb_country.findText(current)
        self.cmb_country.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_country.blockSignals(False)

    def _sort_key(self) -> str:
        return "name" if "Name" in self.cmb_sort.currentText() else "birth_year"

    def _emit(self):
        self.filters_changed.emit(
            self.inp_search.text().strip(),
            self.cmb_country.currentText(),
            self.cmb_era.currentText(),
            self._sort_key(),
        )

    def _clear_filters(self):
        self.inp_search.clear()
        self.cmb_country.setCurrentIndex(0)
        self.cmb_era.setCurrentIndex(0)
        self.cmb_sort.setCurrentIndex(0)
        self._emit()
