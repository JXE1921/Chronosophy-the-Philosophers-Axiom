"""
ui/philosopher_form.py — Add / Edit philosopher dialog.
Clean form with field validation and dynamic quote entry.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QTextEdit, QSpinBox, QPushButton, QScrollArea,
    QWidget, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from database import Philosopher, add_philosopher, update_philosopher
from styles import (
    GOLD, GOLD_DIM, GOLD_LIGHT, GOLD_MUTED, BG_BASE, BG_SURFACE, BG_RAISED,
    BG_HOVER, BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, RED, RED_DIM
)


class PhilosopherFormDialog(QDialog):
    """
    Modal dialog for creating or editing a philosopher.
    Pass philosopher=None to create; pass an existing Philosopher to edit.
    """

    def __init__(self, parent=None, philosopher: Philosopher = None):
        super().__init__(parent)
        self.philosopher = philosopher
        self.is_edit = philosopher is not None
        self.quote_fields: list[QTextEdit] = []

        self.setWindowTitle("Edit Philosopher" if self.is_edit else "Add Philosopher")
        # Keep the dialog comfortably within smaller laptop screens (e.g. 14").
        # All the form content lives inside a scroll area, so a shorter window
        # simply scrolls rather than cutting anything off.
        self.setMinimumWidth(500)
        self.setMinimumHeight(440)
        screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        width = min(600, avail.width() - 60)
        height = min(680, avail.height() - 80)
        self.resize(width, height)   # opening size, capped to fit the current screen
        self.setModal(True)
        # Inherit the app-wide icon so every dialog shows it in the title bar
        if parent and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())
        self._style_dialog()
        self._build_ui()

        if self.is_edit:
            self._populate_fields()

    # ── Styling ──────────────────────────────────────────────────────────────

    def _style_dialog(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_BASE};
            }}
            QLabel#section_header {{
                color: {GOLD};
                font-size: 11px;
                letter-spacing: 2px;
                font-family: 'Georgia', serif;
                padding-top: 8px;
            }}
            QLabel#field_label {{
                color: {TEXT_SEC};
                font-size: 12px;
                font-family: 'Georgia', serif;
            }}
            QFrame#divider {{
                border: none;
                border-top: 1px solid {BORDER};
                margin: 4px 0;
            }}
        """)

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(60)
        title_bar.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER};")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(24, 0, 24, 0)

        icon = QLabel("✦")
        icon.setStyleSheet(f"color: {GOLD}; font-size: 16px; background: transparent;")
        tb_layout.addWidget(icon)

        title = QLabel("Edit Philosopher" if self.is_edit else "Add New Philosopher")
        title.setStyleSheet(f"""
            color: {GOLD_LIGHT};
            font-family: 'Georgia', serif;
            font-size: 17px;
            background: transparent;
        """)
        tb_layout.addWidget(title)
        tb_layout.addStretch()
        root.addWidget(title_bar)

        # ── Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet(f"background: {BG_BASE};")
        form_layout = QVBoxLayout(content)
        form_layout.setContentsMargins(28, 24, 28, 12)
        form_layout.setSpacing(6)

        # ── Section: Identity
        self._add_section_header(form_layout, "IDENTITY")

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Name
        grid.addWidget(self._field_label("Full Name"), 0, 0)
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("e.g. Immanuel Kant")
        grid.addWidget(self.inp_name, 1, 0)

        # Country
        grid.addWidget(self._field_label("Country of Birth"), 0, 1)
        self.inp_country = QLineEdit()
        self.inp_country.setPlaceholderText("e.g. Germany")
        grid.addWidget(self.inp_country, 1, 1)

        # City
        grid.addWidget(self._field_label("City of Birth"), 2, 0)
        self.inp_city = QLineEdit()
        self.inp_city.setPlaceholderText("e.g. Königsberg")
        grid.addWidget(self.inp_city, 3, 0)

        # Teachers
        grid.addWidget(self._field_label("Teachers / Inspirations"), 2, 1)
        self.inp_teachers = QLineEdit()
        self.inp_teachers.setPlaceholderText("Comma-separated names")
        grid.addWidget(self.inp_teachers, 3, 1)

        form_layout.addLayout(grid)
        form_layout.addSpacing(8)

        # ── Section: Lifespan
        self._add_section_header(form_layout, "LIFESPAN")
        lifespan_row = QHBoxLayout()
        lifespan_row.setSpacing(14)

        lifespan_row.addWidget(self._field_label("Birth Year"))
        self.spin_birth = QSpinBox()
        self.spin_birth.setRange(-3000, 2100)
        self.spin_birth.setValue(-400)
        self.spin_birth.setToolTip("Use negative numbers for BC years (e.g. -470 = 470 BC)")
        lifespan_row.addWidget(self.spin_birth)

        lifespan_row.addWidget(QLabel("—"))

        lifespan_row.addWidget(self._field_label("Death Year"))
        self.spin_death = QSpinBox()
        self.spin_death.setRange(-3000, 2100)
        self.spin_death.setValue(-300)
        self.spin_death.setToolTip("Leave as 0 if unknown / still living")
        lifespan_row.addWidget(self.spin_death)

        lifespan_row.addStretch()
        form_layout.addLayout(lifespan_row)
        form_layout.addSpacing(8)

        # ── Section: Contributions
        self._add_section_header(form_layout, "KEY CONTRIBUTIONS")
        self.inp_contributions = QTextEdit()
        self.inp_contributions.setPlaceholderText(
            "Describe what this philosopher is famous for, their major works, "
            "their impact on philosophy and culture..."
        )
        self.inp_contributions.setFixedHeight(100)
        form_layout.addWidget(self.inp_contributions)
        form_layout.addSpacing(8)

        # ── Section: Quotes
        self._add_section_header(form_layout, "QUOTES")

        self.quotes_container = QVBoxLayout()
        self.quotes_container.setSpacing(8)
        form_layout.addLayout(self.quotes_container)

        # Add first quote field
        self._add_quote_field()

        btn_add_quote = QPushButton("＋  Add Another Quote")
        btn_add_quote.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px dashed {BORDER_LT};
                border-radius: 6px;
                color: {TEXT_DIM};
                padding: 8px;
                font-size: 12px;
                font-family: 'Georgia', serif;
            }}
            QPushButton:hover {{
                border-color: {GOLD_DIM};
                color: {GOLD_DIM};
                background: {GOLD_MUTED};
            }}
        """)
        btn_add_quote.clicked.connect(self._add_quote_field)
        form_layout.addWidget(btn_add_quote)
        form_layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # ── Button bar
        btn_bar = QWidget()
        btn_bar.setFixedHeight(64)
        btn_bar.setStyleSheet(f"background: {BG_SURFACE}; border-top: 1px solid {BORDER};")
        bb_layout = QHBoxLayout(btn_bar)
        bb_layout.setContentsMargins(24, 0, 24, 0)
        bb_layout.setSpacing(12)
        bb_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bb_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save Philosopher" if not self.is_edit else "Save Changes")
        btn_save.setObjectName("btn_primary")
        btn_save.setMinimumWidth(160)
        btn_save.clicked.connect(self._on_save)
        bb_layout.addWidget(btn_save)

        root.addWidget(btn_bar)

    def _add_section_header(self, layout, text: str):
        lbl = QLabel(text)
        lbl.setObjectName("section_header")
        layout.addWidget(lbl)
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("field_label")
        return lbl

    def _add_quote_field(self):
        """Add a new quote text area with a remove button."""
        row = QHBoxLayout()
        row.setSpacing(6)

        field = QTextEdit()
        field.setFixedHeight(64)
        field.setPlaceholderText("Enter a quote…")
        self.quote_fields.append(field)
        row.addWidget(field, stretch=1)

        btn_remove = QPushButton("✕")
        btn_remove.setFixedSize(32, 32)
        btn_remove.setStyleSheet(f"""
            QPushButton {{
                background: {RED_DIM};
                color: {RED};
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: {RED}; color: white; }}
        """)
        btn_remove.clicked.connect(lambda _, f=field, r=row: self._remove_quote_field(f, r))
        row.addWidget(btn_remove, alignment=Qt.AlignmentFlag.AlignTop)

        self.quotes_container.addLayout(row)

    def _remove_quote_field(self, field: QTextEdit, row_layout):
        if field in self.quote_fields:
            self.quote_fields.remove(field)
        # Clear and remove widgets in row
        while row_layout.count():
            item = row_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.quotes_container.removeItem(row_layout)

    # ── Population ────────────────────────────────────────────────────────────

    def _populate_fields(self):
        p = self.philosopher
        self.inp_name.setText(p.name)
        self.inp_country.setText(p.birth_country)
        self.inp_city.setText(p.birth_city)
        self.inp_teachers.setText(p.teachers)
        self.inp_contributions.setPlainText(p.contributions)
        self.spin_birth.setValue(p.birth_year)
        self.spin_death.setValue(p.death_year or 0)

        # Populate quotes — first field already added
        quotes = [q.text for q in p.quotes]
        for i, qtext in enumerate(quotes):
            if i == 0:
                self.quote_fields[0].setPlainText(qtext)
            else:
                self._add_quote_field()
                self.quote_fields[-1].setPlainText(qtext)

    # ── Save logic ────────────────────────────────────────────────────────────

    def _on_save(self):
        name = self.inp_name.text().strip()
        if not name:
            self._flash_error("Name is required.")
            return

        country = self.inp_country.text().strip()
        city = self.inp_city.text().strip()
        birth = self.spin_birth.value()
        death = self.spin_death.value() or None

        p = Philosopher(
            id=self.philosopher.id if self.is_edit else 0,
            name=name,
            birth_year=birth,
            death_year=death,
            birth_city=city,
            birth_country=country,
            teachers=self.inp_teachers.text().strip(),
            contributions=self.inp_contributions.toPlainText().strip(),
        )
        quote_texts = [f.toPlainText().strip() for f in self.quote_fields]

        if self.is_edit:
            update_philosopher(p, quote_texts)
        else:
            add_philosopher(p, quote_texts)

        self.accept()

    def _flash_error(self, msg: str):
        QMessageBox.warning(self, "Validation Error", msg)
