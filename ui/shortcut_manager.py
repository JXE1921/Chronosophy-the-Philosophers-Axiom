"""
ui/shortcut_manager.py — Central registry and runtime manager for the app's
customisable keyboard shortcuts.

Why this exists
---------------
Previously every shortcut was hand-wired with a one-off ``QShortcut`` inside
``MainWindow._build_shortcuts`` and *also* described, separately, in a static
reference dialog.  The two drifted apart: half the shortcuts the dialog
advertised (Ctrl+1–5, Ctrl+E, F11, Ctrl+Q) were never actually registered, so
they silently did nothing — and none of them could be changed by the user.

This module makes the registry the single source of truth:

  · ``SHORTCUT_DEFS`` lists every rebindable action once — id, category,
    human label and default key sequence.
  · ``ShortcutManager`` owns the live ``QShortcut`` objects, loads any user
    overrides from ``QSettings``, rebuilds a shortcut when its sequence
    changes, and reports conflicts so two actions can't fight over one combo.

Both the menu hints and the customiser dialog read their bindings from here, so
what the user sees always matches what the keyboard actually does.
"""

from dataclasses import dataclass

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QKeySequence, QShortcut


@dataclass(frozen=True)
class ShortcutDef:
    """One rebindable action.

    ``default`` is stored as a portable key-sequence string (e.g. ``"Ctrl+N"``).
    An empty string means the action ships unbound but can still be assigned a
    key by the user.
    """
    id: str
    category: str
    label: str
    default: str


# ── Single source of truth — display order is preserved in the dialog ─────────
SHORTCUT_DEFS: list[ShortcutDef] = [
    # Navigation
    ShortcutDef("tab_timeline", "Navigation", "Switch to Timeline tab",        "Ctrl+1"),
    ShortcutDef("tab_country",  "Navigation", "Switch to By Country tab",       "Ctrl+2"),
    ShortcutDef("tab_graph",    "Navigation", "Switch to Influence Graph tab",  "Ctrl+3"),
    ShortcutDef("tab_map",      "Navigation", "Switch to World Map tab",        "Ctrl+4"),
    ShortcutDef("tab_stats",    "Navigation", "Switch to Statistics tab",       "Ctrl+5"),

    # Philosophers
    ShortcutDef("add",     "Philosophers", "Add new philosopher",            "Ctrl+N"),
    ShortcutDef("search",  "Philosophers", "Focus search bar",               "Ctrl+F"),
    ShortcutDef("view",    "Philosophers", "Open detail view (selected)",    "Return"),
    ShortcutDef("edit",    "Philosophers", "Edit selected philosopher",      "F2"),
    ShortcutDef("delete",  "Philosophers", "Delete selected philosopher",    "Delete"),
    ShortcutDef("compare", "Philosophers", "Compare two selected",           "Ctrl+R"),

    # General
    ShortcutDef("zoom_in",    "General", "Zoom UI in",               "Ctrl+="),
    ShortcutDef("zoom_out",   "General", "Zoom UI out",              "Ctrl+-"),
    ShortcutDef("zoom_reset", "General", "Reset UI zoom",            "Ctrl+0"),
    ShortcutDef("export_csv", "General", "Export to CSV",            "Ctrl+E"),
    ShortcutDef("export_json","General", "Export to JSON",           "Ctrl+Shift+E"),
    ShortcutDef("fullscreen", "General", "Toggle fullscreen",        "F11"),
    ShortcutDef("shortcuts",  "General", "Show keyboard shortcuts",  "F1"),
    ShortcutDef("quit",       "General", "Quit",                     "Ctrl+Q"),
]

# Fast lookup by id
_DEF_BY_ID: dict[str, ShortcutDef] = {d.id: d for d in SHORTCUT_DEFS}

# Ordered list of categories as they first appear above
CATEGORIES: list[str] = list(dict.fromkeys(d.category for d in SHORTCUT_DEFS))


def normalise(seq: str) -> str:
    """Return a canonical portable form of a key-sequence string.

    Lets us compare ``"Ctrl+N"`` and ``"ctrl+n"`` (or whatever Qt round-trips
    to) as equal when checking for conflicts.
    """
    if not seq:
        return ""
    return QKeySequence(seq).toString(QKeySequence.SequenceFormat.PortableText)


class ShortcutManager:
    """Owns the live ``QShortcut`` objects for one window.

    Usage:
        mgr = ShortcutManager(window, settings)
        mgr.register("add", callback)      # for every action id
        mgr.build()                        # create the QShortcuts
        ...
        mgr.set_sequence("add", "Ctrl+Shift+N")   # rebind live + persist
    """

    SETTINGS_GROUP = "shortcuts"

    def __init__(self, parent_widget, settings: QSettings | None = None):
        self._parent = parent_widget
        self._settings = settings
        self._callbacks: dict[str, callable] = {}
        self._shortcuts: dict[str, QShortcut] = {}
        self._sequences: dict[str, str] = {}
        self._load_sequences()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _settings_key(self, action_id: str) -> str:
        return f"{self.SETTINGS_GROUP}/{action_id}"

    def _load_sequences(self):
        """Seed current sequences from defaults, overridden by any saved values.

        Note: ``QSettings.value(key, None, type=str)`` returns ``""`` — not
        ``None`` — for a missing key, so we must test ``contains()`` to tell an
        absent override from a deliberately-empty (user-unbound) one.
        """
        for d in SHORTCUT_DEFS:
            seq = d.default
            key = self._settings_key(d.id)
            if self._settings is not None and self._settings.contains(key):
                seq = self._settings.value(key, d.default, type=str)
            self._sequences[d.id] = seq

    def _persist(self, action_id: str, seq: str):
        if self._settings is not None:
            self._settings.setValue(self._settings_key(action_id), seq)

    # ── Registration / build ─────────────────────────────────────────────────

    def register(self, action_id: str, callback) -> None:
        """Associate an action id with the callable it should trigger."""
        if action_id not in _DEF_BY_ID:
            raise KeyError(f"Unknown shortcut id: {action_id!r}")
        self._callbacks[action_id] = callback

    def build(self) -> None:
        """Create a live ``QShortcut`` for every registered action."""
        for d in SHORTCUT_DEFS:
            self._rebuild_one(d.id)

    def _rebuild_one(self, action_id: str) -> None:
        """(Re)create the QShortcut for a single action from its current sequence."""
        # Tear down the previous shortcut, if any
        old = self._shortcuts.pop(action_id, None)
        if old is not None:
            old.setEnabled(False)
            old.setParent(None)
            old.deleteLater()

        callback = self._callbacks.get(action_id)
        seq = self._sequences.get(action_id, "")
        if not callback or not seq:
            return                      # unbound or no handler → nothing to install

        sc = QShortcut(QKeySequence(seq), self._parent)
        sc.activated.connect(callback)
        self._shortcuts[action_id] = sc

    # ── Queries ──────────────────────────────────────────────────────────────

    def sequence(self, action_id: str) -> str:
        """Current portable key-sequence string for an action ("" if unbound)."""
        return self._sequences.get(action_id, "")

    def default(self, action_id: str) -> str:
        return _DEF_BY_ID[action_id].default

    def label(self, action_id: str) -> str:
        return _DEF_BY_ID[action_id].label

    def display(self, action_id: str) -> str:
        """Native, human-friendly text for the current binding (e.g. 'Ctrl+1')."""
        return display_text(self.sequence(action_id))

    def conflict(self, action_id: str, seq: str) -> str | None:
        """Return the id of any *other* action already using ``seq``, else None."""
        target = normalise(seq)
        if not target:
            return None
        for other_id, other_seq in self._sequences.items():
            if other_id == action_id:
                continue
            if normalise(other_seq) == target:
                return other_id
        return None

    # ── Mutations ────────────────────────────────────────────────────────────

    def set_sequence(self, action_id: str, seq: str) -> None:
        """Rebind an action live and persist the change."""
        if action_id not in _DEF_BY_ID:
            raise KeyError(f"Unknown shortcut id: {action_id!r}")
        seq = normalise(seq)
        self._sequences[action_id] = seq
        self._persist(action_id, seq)
        self._rebuild_one(action_id)

    def reset(self, action_id: str) -> None:
        """Restore one action to its default binding."""
        self.set_sequence(action_id, self.default(action_id))

    def reset_all(self) -> None:
        """Restore every action to its default binding."""
        for d in SHORTCUT_DEFS:
            self.set_sequence(d.id, d.default)


def display_text(seq: str) -> str:
    """Human-readable native label for a portable sequence string."""
    if not seq:
        return "Unbound"
    return QKeySequence(seq).toString(QKeySequence.SequenceFormat.NativeText)
