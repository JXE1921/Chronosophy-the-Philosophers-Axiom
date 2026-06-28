"""
ui/philosopher_form.py — Add / Edit philosopher dialog.
Clean form with field validation and dynamic quote entry.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QTextEdit, QSpinBox, QPushButton, QScrollArea,
    QWidget, QFrame, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
import database as db
from database import Philosopher, Work, add_philosopher, update_philosopher
import library
from ui import image_utils
from styles import (
    GOLD, GOLD_DIM, GOLD_LIGHT, GOLD_MUTED, BG_BASE, BG_SURFACE, BG_RAISED,
    BG_HOVER, BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, RED, RED_DIM
)

# Size of the square portrait frame shown in the form preview (logical px).
_PREVIEW_SIZE = 132


class _WorkRow(QWidget):
    """One editable row in the Works & Bibliography section.

    Holds a title plus an optional file attachment, tracking exactly what the
    user did to the file (kept, replaced, removed, or freshly attached) so the
    save step can reconcile it without ever re-copying an untouched file.
    """

    remove_requested = pyqtSignal(object)   # emits self

    def __init__(self, dialog: QDialog, work: Work = None):
        super().__init__()
        self._dialog = dialog
        self.work_id = work.id if work else None
        self._existing_path = work.file_path if work else ""
        self._existing_name = work.original_filename if work else ""
        self._new_source = None           # path of a freshly chosen file
        self._file_removed = False        # user cleared an existing file

        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Work title  ·  e.g. Critique of Pure Reason")
        if work:
            self.title_edit.setText(work.title)
        row.addWidget(self.title_edit, stretch=1)

        self.btn_file = QPushButton()
        self.btn_file.setMinimumWidth(150)
        self.btn_file.setMaximumWidth(180)
        self.btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_file.setToolTip("Attach a file for this work (PDF, ePub, text, …)")
        self.btn_file.clicked.connect(self._on_attach)
        row.addWidget(self.btn_file)

        self.btn_clear_file = QPushButton("✕")
        self.btn_clear_file.setFixedSize(28, 28)
        self.btn_clear_file.setToolTip("Detach this file")
        self.btn_clear_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_file.setStyleSheet(f"""
            QPushButton {{
                background: {BG_RAISED}; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 4px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {RED_DIM}; color: {RED}; border-color: {RED}; }}
        """)
        self.btn_clear_file.clicked.connect(self._on_detach)
        row.addWidget(self.btn_clear_file)

        btn_remove = QPushButton("✕")
        btn_remove.setFixedSize(32, 28)
        btn_remove.setToolTip("Remove this work")
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet(f"""
            QPushButton {{
                background: {RED_DIM}; color: {RED};
                border: none; border-radius: 4px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {RED}; color: white; }}
        """)
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        row.addWidget(btn_remove)

        self._refresh_file_button()

    # ── current file state ───────────────────────────────────────────────────
    @property
    def _current_filename(self) -> str:
        if self._new_source:
            return os.path.basename(self._new_source)
        if self._existing_path and not self._file_removed:
            return self._existing_name or os.path.basename(self._existing_path)
        return ""

    def _has_file(self) -> bool:
        return bool(self._current_filename)

    def _refresh_file_button(self):
        name = self._current_filename
        if name:
            display = name if len(name) <= 22 else name[:20] + "…"
            self.btn_file.setText("📎  " + display)
            self.btn_file.setToolTip(f"Attached: {name}\nClick to replace.")
            self.btn_file.setStyleSheet(f"""
                QPushButton {{
                    background: {GOLD_MUTED}; color: {GOLD_LIGHT};
                    border: 1px solid {GOLD_DIM}; border-radius: 6px;
                    padding: 6px 10px; font-size: 12px; text-align: left;
                }}
                QPushButton:hover {{ border-color: {GOLD}; }}
            """)
            self.btn_clear_file.setVisible(True)
        else:
            self.btn_file.setText("📎  Attach file…")
            self.btn_file.setToolTip("Attach a file for this work (PDF, ePub, text, …)")
            self.btn_file.setStyleSheet("")   # inherit the app's default button look
            self.btn_clear_file.setVisible(False)

    def _on_attach(self):
        start_dir = os.path.dirname(self._new_source) if self._new_source else ""
        path, _ = QFileDialog.getOpenFileName(
            self._dialog, "Attach a file for this work", start_dir,
            "Documents (*.pdf *.epub *.txt *.doc *.docx *.rtf *.md *.djvu *.mobi);;All files (*)"
        )
        if not path:
            return
        self._new_source = path
        self._file_removed = False
        self._refresh_file_button()

    def _on_detach(self):
        # Forget a freshly chosen file; or mark an existing attachment for removal.
        self._new_source = None
        if self._existing_path:
            self._file_removed = True
        self._refresh_file_button()

    def spec(self) -> dict:
        """Return a save-spec describing this row's title + file intent."""
        title = self.title_edit.text().strip()
        if self._new_source:
            action = "new"
        elif self._existing_path and not self._file_removed:
            action = "keep"
        elif self._existing_path and self._file_removed:
            action = "remove"
        else:
            action = "none"
        return {"id": self.work_id, "title": title,
                "file": action, "source": self._new_source}


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
        self.work_rows: list[_WorkRow] = []

        # ── Portrait edit state ───────────────────────────────────────────────
        # _portrait_action: 'keep' (use existing) | 'new' (use _portrait_bytes)
        #                   | 'remove' (clear existing) | 'none' (never had one)
        self._existing_portrait = philosopher.portrait_path if self.is_edit else ""
        self._had_portrait = bool(self._existing_portrait)
        self._portrait_action = "keep" if self._had_portrait else "none"
        self._portrait_bytes: bytes | None = None
        self._portrait_ext = "png"

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

        # ── Section: Portrait
        self._build_portrait_section(form_layout)

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
        # Keep the monogram placeholder in sync with the name while no picture is set
        self.inp_name.textChanged.connect(self._on_name_changed)
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
        form_layout.addSpacing(8)

        # ── Section: Works & Bibliography
        self._add_section_header(form_layout, "WORKS & BIBLIOGRAPHY")
        hint = QLabel("List works written by — or inspired by — this philosopher. "
                      "Attach a file to any entry if you have one.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent;")
        form_layout.addWidget(hint)

        self.works_container = QVBoxLayout()
        self.works_container.setSpacing(8)
        self.works_container.setContentsMargins(0, 4, 0, 0)
        form_layout.addLayout(self.works_container)

        btn_add_work = QPushButton("＋  Add Another Work")
        btn_add_work.setStyleSheet(f"""
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
        btn_add_work.clicked.connect(lambda: self._add_work_row())
        form_layout.addWidget(btn_add_work)
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

    # ── Portrait ──────────────────────────────────────────────────────────────

    def _build_portrait_section(self, layout):
        self._add_section_header(layout, "PORTRAIT")

        wrap = QHBoxLayout()
        wrap.setSpacing(16)
        wrap.addStretch()

        # The framed preview — a fixed square that always shows exactly how the
        # portrait will be cropped and framed elsewhere in the app.
        self.portrait_preview = QLabel()
        self.portrait_preview.setFixedSize(_PREVIEW_SIZE, _PREVIEW_SIZE)
        self.portrait_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.portrait_preview.setStyleSheet("background: transparent; border: none;")
        wrap.addWidget(self.portrait_preview)

        # Buttons + hint, stacked beside the preview
        side = QVBoxLayout()
        side.setSpacing(8)
        side.addStretch()

        self.btn_upload_portrait = QPushButton("Upload Picture…")
        self.btn_upload_portrait.setObjectName("btn_primary")
        self.btn_upload_portrait.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_upload_portrait.clicked.connect(self._on_upload_portrait)
        side.addWidget(self.btn_upload_portrait)

        self.btn_remove_portrait = QPushButton("Remove")
        self.btn_remove_portrait.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_portrait.clicked.connect(self._on_remove_portrait)
        side.addWidget(self.btn_remove_portrait)

        tip = QLabel("PNG · JPG · WEBP\nCentred & framed automatically")
        tip.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; background: transparent;")
        side.addWidget(tip)
        side.addStretch()

        wrap.addLayout(side)
        wrap.addStretch()
        layout.addLayout(wrap)
        layout.addSpacing(8)

        self._update_portrait_preview()

    def _portrait_source(self):
        """Return the image source to preview: bytes, an abs path, or None."""
        if self._portrait_action == "new" and self._portrait_bytes:
            return self._portrait_bytes
        if self._portrait_action == "keep" and self._existing_portrait:
            return library.abs_path(self._existing_portrait)
        return None

    def _update_portrait_preview(self):
        dpr = self.devicePixelRatioF() or 1.0
        src = self._portrait_source()
        pm = None
        if src is not None:
            pm = image_utils.framed_pixmap(
                src, _PREVIEW_SIZE, _PREVIEW_SIZE, dpr,
                radius=14, border_color=GOLD_DIM, border_width=1.5,
            )
        if pm is None:
            name = self.inp_name.text() if hasattr(self, "inp_name") else ""
            if not name and self.is_edit:
                name = self.philosopher.name
            pm = image_utils.monogram_pixmap(
                name or "?", _PREVIEW_SIZE, _PREVIEW_SIZE, dpr,
                radius=14, bg=BG_RAISED, fg=GOLD, border_color=BORDER_LT, border_width=1.5,
            )
        self.portrait_preview.setPixmap(pm)
        has_pic = self._portrait_source() is not None
        if hasattr(self, "btn_remove_portrait"):
            self.btn_remove_portrait.setEnabled(has_pic)
            self.btn_upload_portrait.setText("Change Picture…" if has_pic else "Upload Picture…")

    def _on_name_changed(self, _text=None):
        # Only the monogram fallback depends on the name; skip when a picture is set.
        if self._portrait_source() is None:
            self._update_portrait_preview()

    def _on_upload_portrait(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a portrait picture", "", image_utils.IMAGE_FILTER
        )
        if not path:
            return

        dims = image_utils.image_dimensions(path)
        if dims is None:
            self._flash_error("That file could not be read as an image.\n"
                              "Please choose a PNG, JPG, WEBP, or similar picture.")
            return

        # Guard the user's stated quality concern: warn (but allow) low-res input.
        if min(dims) < image_utils.LOW_RES_EDGE:
            proceed = QMessageBox.question(
                self, "Low-resolution image",
                f"This picture is only {dims[0]}×{dims[1]} pixels and may look soft "
                f"when shown as a framed portrait.\n\nUse it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return

        try:
            data, ext = image_utils.normalise_portrait(path)
        except ValueError as exc:
            self._flash_error(str(exc))
            return

        self._portrait_bytes = data
        self._portrait_ext = ext
        self._portrait_action = "new"
        self._update_portrait_preview()

    def _on_remove_portrait(self):
        self._portrait_bytes = None
        self._portrait_action = "remove" if self._had_portrait else "none"
        self._update_portrait_preview()

    def showEvent(self, event):
        super().showEvent(event)
        # Re-render at the real display dpr now the dialog is on screen, so the
        # preview is always crisp (the pre-show ratio can be wrong on HiDPI).
        self._update_portrait_preview()

    # ── Works ─────────────────────────────────────────────────────────────────

    def _add_work_row(self, work: Work = None) -> _WorkRow:
        row = _WorkRow(self, work)
        row.remove_requested.connect(self._remove_work_row)
        self.work_rows.append(row)
        self.works_container.addWidget(row)
        return row

    def _remove_work_row(self, row: _WorkRow):
        if row in self.work_rows:
            self.work_rows.remove(row)
        self.works_container.removeWidget(row)
        row.deleteLater()

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

        # Populate works (each row carries its own attachment state)
        for work in p.works:
            self._add_work_row(work)

        # Refresh the preview now the name is set (matters for the monogram case)
        self._update_portrait_preview()

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
        work_specs = [s for s in (r.spec() for r in self.work_rows) if s["title"]]

        # Pre-flight: a newly-attached file must still exist on disk, so we never
        # half-save the philosopher and then fail copying its attachments.
        for s in work_specs:
            if s["file"] == "new" and (not s["source"] or not os.path.isfile(s["source"])):
                self._flash_error(
                    f"The file attached to “{s['title']}” could not be found.\n"
                    "Please re-attach it or detach it before saving."
                )
                return

        # Write the philosopher row first (so we have an id for its attachments).
        try:
            if self.is_edit:
                update_philosopher(p, quote_texts)
                pid = p.id
            else:
                pid = add_philosopher(p, quote_texts)
        except Exception as exc:
            self._flash_error(f"Could not save philosopher:\n{exc}")
            return

        # Then the portrait + works. If anything here fails, undo a brand-new
        # philosopher so a retry can't create a duplicate.
        try:
            if self._portrait_action == "new" and self._portrait_bytes:
                db.set_portrait(pid, self._portrait_bytes, self._portrait_ext)
            elif self._portrait_action == "remove":
                db.clear_portrait(pid)
            db.save_works(pid, work_specs)
        except Exception as exc:
            if not self.is_edit:
                try:
                    db.delete_philosopher(pid)
                except Exception:
                    pass
            self._flash_error(f"Could not save attachments:\n{exc}")
            return

        self.accept()

    def _flash_error(self, msg: str):
        QMessageBox.warning(self, "Validation Error", msg)
