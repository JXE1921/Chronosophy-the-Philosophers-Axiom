"""
main.py — Entry point for Chronosophy: The Philosopher's Axiom.

Run with:
    python main.py

Dependencies:
    pip install PyQt6
"""

import sys
import os

# ── Ensure project root is on path so all imports resolve ───────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Only import what is needed to show the window immediately ────────────────
# Heavy imports (database seeding, views) are deferred until after the window
# is visible, so the UI appears as fast as possible.
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt, QSettings, QTimer


def _resource_path(relative: str) -> str:
    """
    Return the absolute path to a bundled resource.

    When running from source:  resolves relative to this file.
    When running as a PyInstaller .exe: PyInstaller extracts all bundled files
    to a temporary folder stored in sys._MEIPASS at runtime.  Without checking
    that path first, icon.ico is never found inside the bundle and the window
    icon silently disappears even though the taskbar icon (set via --icon at
    build time) still shows correctly.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _set_windows_app_id() -> None:
    """
    Register a unique AppUserModelID with Windows.

    Windows uses this ID to decide which taskbar button a window belongs to.
    Without it, Windows groups the app under the generic python.exe / pythonw.exe
    entry, causing the taskbar icon and the window top-left icon to become
    de-synced after packaging (taskbar shows your icon; top-left reverts to the
    Python default or goes blank).

    Setting the ID here — before QApplication is created — fixes both.
    Silently ignored on macOS / Linux where ctypes.windll does not exist.
    """
    try:
        import ctypes
        app_id = "Chronosophy.ArchiveOfPhilosophy.1"   # unique per app
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


# ── Must be called before QApplication is instantiated ───────────────────────
_set_windows_app_id()

# Resolve icon — works from source AND inside a PyInstaller bundle
ICON_PATH = _resource_path("icon.ico")


def _restore_window(window, settings: QSettings) -> None:
    """Restore saved geometry and fullscreen state from previous session."""
    geometry = settings.value("windowGeometry")
    if geometry:
        window.restoreGeometry(geometry)
    else:
        window.resize(1300, 840)

    state = settings.value("windowState")
    if state:
        window.restoreState(state)

    was_maximised = settings.value("windowMaximised", False, type=bool)
    was_fullscreen = settings.value("windowFullscreen", False, type=bool)

    if was_fullscreen:
        window.showFullScreen()
    elif was_maximised:
        window.showMaximized()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Archive of Philosophy")
    app.setOrganizationName("Chronosophy")

    # Set icon at the QApplication level — propagates to every window/dialog
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    from styles import get_stylesheet
    app.setStyleSheet(get_stylesheet())
    app.setFont(QFont("Georgia", 12))

    import database as db
    db.initialise_db()

    from ui.main_window import MainWindow
    settings = QSettings("Chronosophy", "Archive of Philosophy")
    window = MainWindow(settings=settings, icon_path=ICON_PATH)

    _restore_window(window, settings)
    window.show()

    # Load data after UI is visible so the window appears instantly
    QTimer.singleShot(0, window.load_initial_data)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
