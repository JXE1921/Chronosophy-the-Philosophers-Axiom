"""
ui/shortcuts_dialog.py — Interactive keyboard-shortcut customiser.

This used to be a read-only reference list.  It is now a live editor: click any
binding, press a new key combination, and it applies immediately and is saved
for next time.  Conflicts are detected so two actions can't share one combo, and
every action — or the whole set — can be reset to its default.

Mouse / scroll interactions (timeline & graph navigation) are not rebindable, so
they are shown at the bottom as a plain reference.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QScrollArea, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QKeyCombination
from PyQt6.QtGui import QKeySequence

from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, BG_BASE, BG_SURFACE, BG_RAISED,
    BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM, RED
)
from ui.shortcut_manager import SHORTCUT_DEFS, CATEGORIES, display_text


# Non-rebindable reference — mouse / scroll gestures, shown verbatim
_GESTURE_REFERENCE = [
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
]


class KeyCaptureButton(QPushButton):
    """A button that records the next key combination the user presses.

    Click it to enter recording mode; the next non-modifier key press becomes
    the new binding.  Esc cancels, Backspace clears the binding.
    """

    captured = pyqtSignal(str)   # emits the new portable sequence ("" when cleared)

    # Lone modifier keys never form a binding on their own
    _MODIFIER_KEYS = {
        Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
        Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
    }

    def __init__(self, sequence: str, parent=None):
        super().__init__(parent)
        self._sequence = sequence
        self._recording = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(170)
        self.clicked.connect(self._start_recording)
        self._refresh_style()

    # ── Public ───────────────────────────────────────────────────────────────

    def set_sequence(self, sequence: str):
        """Set the displayed binding without emitting (used for external updates)."""
        self._sequence = sequence
        self._recording = False
        self._refresh_style()

    # ── Recording lifecycle ──────────────────────────────────────────────────

    def _start_recording(self):
        self._recording = True
        self.setText("Press keys…")
        self._refresh_style()

    def _stop_recording(self):
        self._recording = False
        self._refresh_style()

    def keyPressEvent(self, event):
        if not self._recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in self._MODIFIER_KEYS:
            return                          # wait for the real key
        if key == Qt.Key.Key_Escape:
            self._stop_recording()          # cancel, keep current binding
            return
        if key == Qt.Key.Key_Backspace:
            self._sequence = ""             # clear the binding
            self._stop_recording()
            self.captured.emit("")
            return

        combo = QKeyCombination(event.modifiers(), Qt.Key(key))
        seq = QKeySequence(combo.toCombined()).toString(
            QKeySequence.SequenceFormat.PortableText
        )
        self._recording = False
        # Don't commit to self._sequence yet — the dialog may reject a conflict
        self._refresh_style()
        self.captured.emit(seq)

    def focusOutEvent(self, event):
        if self._recording:
            self._stop_recording()          # clicking away cancels
        super().focusOutEvent(event)

    # ── Appearance ───────────────────────────────────────────────────────────

    def _refresh_style(self):
        if self._recording:
            self.setText("Press keys…")
            border, colour, bg = GOLD, GOLD_LIGHT, BG_RAISED
        else:
            unbound = not self._sequence
            self.setText(display_text(self._sequence))
            border = BORDER_LT
            colour = TEXT_DIM if unbound else GOLD_LIGHT
            bg = BG_RAISED
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 5px;
                color: {colour};
                font-family: 'Courier New', monospace;
                font-size: 12px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{ border-color: {GOLD}; color: {GOLD_LIGHT}; }}
        """)


class ShortcutsDialog(QDialog):
    """Editable shortcut customiser bound to a :class:`ShortcutManager`."""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._buttons: dict[str, KeyCaptureButton] = {}

        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(560, 640)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {BG_BASE}; }}")
        if parent and not parent.windowIcon().isNull():
            self.setWindowIcon(parent.windowIcon())
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet(f"background: {BG_BASE};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 18, 28, 20)
        layout.setSpacing(16)

        hint = QLabel("Click a shortcut, then press a new key combination.  "
                      "Backspace clears it · Esc cancels.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 12px; "
                           f"font-style: italic; background: transparent;")
        layout.addWidget(hint)

        # Editable, rebindable shortcuts grouped by category
        defs_by_cat: dict[str, list] = {c: [] for c in CATEGORIES}
        for d in SHORTCUT_DEFS:
            defs_by_cat[d.category].append(d)

        for category in CATEGORIES:
            layout.addWidget(self._section_label(category))
            for d in defs_by_cat[category]:
                layout.addLayout(self._editable_row(d))

        # Non-rebindable mouse / scroll reference
        for section_name, bindings in _GESTURE_REFERENCE:
            layout.addWidget(self._section_label(f"{section_name}  (mouse)"))
            for key, desc in bindings:
                layout.addLayout(self._reference_row(key, desc))

        layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
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
        return header

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(52)
        footer.setStyleSheet(f"background: {BG_SURFACE}; border-top: 1px solid {BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)

        btn_reset_all = QPushButton("↺  Restore Defaults")
        btn_reset_all.setMinimumWidth(150)
        btn_reset_all.clicked.connect(self._reset_all)
        fl.addWidget(btn_reset_all)

        fl.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setObjectName("btn_primary")
        btn_close.setMinimumWidth(90)
        btn_close.clicked.connect(self.accept)
        fl.addWidget(btn_close)
        return footer

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(f"""
            color: {GOLD};
            font-size: 9px;
            letter-spacing: 2.5px;
            background: transparent;
            border-bottom: 1px solid {BORDER};
            padding-bottom: 5px;
        """)
        return lbl

    def _editable_row(self, d) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        desc = QLabel(d.label)
        desc.setStyleSheet(f"color: {TEXT_PRI}; font-size: 13px; background: transparent;")
        row.addWidget(desc, stretch=1)

        btn = KeyCaptureButton(self._manager.sequence(d.id))
        btn.captured.connect(lambda seq, aid=d.id: self._on_captured(aid, seq))
        self._buttons[d.id] = btn
        row.addWidget(btn)

        reset = QPushButton("↺")
        reset.setFixedWidth(32)
        reset.setToolTip("Reset to default")
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.clicked.connect(lambda _=False, aid=d.id: self._reset_one(aid))
        row.addWidget(reset)
        return row

    def _reference_row(self, key: str, desc: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)
        key_lbl = QLabel(key)
        key_lbl.setFixedWidth(180)
        key_lbl.setStyleSheet(f"""
            background: {BG_RAISED};
            border: 1px solid {BORDER};
            border-radius: 5px;
            color: {TEXT_SEC};
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 4px 10px;
        """)
        row.addWidget(key_lbl)
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 13px; background: transparent;")
        row.addWidget(desc_lbl, stretch=1)
        return row

    # ── Editing logic ────────────────────────────────────────────────────────

    def _on_captured(self, action_id: str, seq: str):
        if not self._apply(action_id, seq):
            # Rejected — restore the button to the still-current binding
            self._buttons[action_id].set_sequence(self._manager.sequence(action_id))

    def _apply(self, action_id: str, seq: str) -> bool:
        """Assign ``seq`` to ``action_id``, resolving any conflict first.

        Returns True if applied, False if the user declined to reassign.
        """
        if seq:
            conflict_id = self._manager.conflict(action_id, seq)
            if conflict_id is not None:
                if not self._confirm_reassign(seq, conflict_id, action_id):
                    return False
                self._manager.set_sequence(conflict_id, "")
                if conflict_id in self._buttons:
                    self._buttons[conflict_id].set_sequence("")

        self._manager.set_sequence(action_id, seq)
        self._buttons[action_id].set_sequence(self._manager.sequence(action_id))
        return True

    def _confirm_reassign(self, seq: str, conflict_id: str, action_id: str) -> bool:
        reply = QMessageBox.question(
            self, "Shortcut In Use",
            f"“{display_text(seq)}” is already assigned to "
            f"“{self._manager.label(conflict_id)}”.\n\n"
            f"Reassign it to “{self._manager.label(action_id)}” and leave "
            f"“{self._manager.label(conflict_id)}” unbound?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _reset_one(self, action_id: str):
        self._apply(action_id, self._manager.default(action_id))

    def _reset_all(self):
        reply = QMessageBox.question(
            self, "Restore Defaults",
            "Reset every keyboard shortcut to its default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._manager.reset_all()
        for aid, btn in self._buttons.items():
            btn.set_sequence(self._manager.sequence(aid))
