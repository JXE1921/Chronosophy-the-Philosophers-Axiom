"""
ui/main_window.py — Root application window.
Coordinates: sidebar list, search/filter bar, quote widget, clock, tab views,
and all CRUD dialogs. Saves/restores window state between sessions.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QFrame, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, QTime, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QIcon

import database as db
from database import Philosopher, search_philosophers, delete_philosopher, get_all_countries
from styles import (
    GOLD, GOLD_LIGHT, GOLD_DIM, GOLD_MUTED, BG_DEEP, BG_BASE, BG_SURFACE,
    BG_RAISED, BG_HOVER, BORDER, BORDER_LT, TEXT_PRI, TEXT_SEC, TEXT_DIM,
    RED, RED_DIM, ERA_COLORS
)
from ui.quote_widget import QuoteWidget
from ui.timeline_widget import TimelineView
from ui.country_widget import CountryView
from ui.search_bar import SearchBar
from ui.philosopher_form import PhilosopherFormDialog
from ui.detail_dialog import DetailDialog


class MainWindow(QMainWindow):
    """Application root window."""

    def __init__(self, settings: QSettings = None, icon_path: str = ""):
        super().__init__()
        self._settings = settings
        self._icon_path = icon_path
        self._current_filters = ("", "All", "All", "birth_year")
        self._philosophers: list[Philosopher] = []

        # Set window title and icon
        self.setWindowTitle("Chronosophy — The Philosopher's Axiom")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self.setMinimumSize(900, 620)
        self._build_ui()

    # ── Called by main.py after window.show() for fast startup ───────────────

    def load_initial_data(self):
        self._load_data()

    # ── Window state persistence ──────────────────────────────────────────────

    def closeEvent(self, event):
        """Save window geometry and state before closing."""
        if self._settings:
            self._settings.setValue("windowGeometry", self.saveGeometry())
            self._settings.setValue("windowState", self.saveState())
            self._settings.setValue(
                "windowMaximised",
                self.windowState() == Qt.WindowState.WindowMaximized
            )
            self._settings.setValue(
                "windowFullscreen",
                self.isFullScreen()
            )
        super().closeEvent(event)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(f"background: {BG_BASE};")
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_header())
        self.quote_widget = QuoteWidget()
        main_layout.addWidget(self.quote_widget)

        self.search_bar = SearchBar()
        self.search_bar.filters_changed.connect(self._on_filters_changed)
        main_layout.addWidget(self.search_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_tabs())
        splitter.setSizes([260, 1040])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, stretch=1)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(58)
        header.setStyleSheet(f"""
            QWidget {{
                background: {BG_DEEP};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(10)

        # Logo glyph
        logo = QLabel("⟁")
        logo.setStyleSheet(f"color: {GOLD}; font-size: 22px; background: transparent; border: none;")
        layout.addWidget(logo)

        # "Chronosophy:" — gold
        title = QLabel("Chronosophy:")
        title.setStyleSheet(f"""
            color: {GOLD_LIGHT};
            font-family: 'Georgia', serif;
            font-size: 18px;
            letter-spacing: 0.5px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(title)

        # "The Philosopher's Axiom" — grey
        subtitle = QLabel("The Philosopher's Axiom")
        subtitle.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-family: 'Georgia', serif;
            font-size: 14px;
            font-style: italic;
            background: transparent;
            border: none;
        """)
        layout.addWidget(subtitle)

        layout.addStretch()

        # ── 24-hour London clock ──────────────────────────────────────────────
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"""
            color: {TEXT_SEC};
            font-family: 'Georgia', serif;
            font-size: 13px;
            letter-spacing: 1px;
            background: transparent;
            border: 1px solid {BORDER};
            border-radius: 5px;
            padding: 3px 10px;
        """)
        self.clock_label.setToolTip("London time (Europe/London)")
        layout.addWidget(self.clock_label)

        # Tick every second
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()     # paint immediately — no blank flash

        # Small spacer before button
        layout.addSpacing(12)

        # Add philosopher button
        self.btn_add = QPushButton("＋  Add Philosopher")
        self.btn_add.setObjectName("btn_primary")
        self.btn_add.setFixedHeight(36)
        self.btn_add.clicked.connect(self._on_add_philosopher)
        layout.addWidget(self.btn_add)

        return header

    def _update_clock(self):
        """Update clock label with current London time in 24-hour format."""
        try:
            # Use zoneinfo (Python 3.9+) for accurate London time inc. BST
            from zoneinfo import ZoneInfo
            from datetime import datetime
            now = datetime.now(ZoneInfo("Europe/London"))
            self.clock_label.setText(now.strftime("%H:%M:%S"))
        except Exception:
            # Fallback: system local time
            self.clock_label.setText(QTime.currentTime().toString("HH:mm:ss"))

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(300)
        sidebar.setStyleSheet(f"""
            QWidget {{
                background: {BG_SURFACE};
                border-right: 1px solid {BORDER};
            }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet(f"background: {BG_RAISED}; border-bottom: 1px solid {BORDER};")
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(14, 0, 10, 0)
        lbl = QLabel("PHILOSOPHERS")
        lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; letter-spacing: 2px; background: transparent; border: none;")
        tb.addWidget(lbl)
        tb.addStretch()
        self.count_lbl = QLabel("0")
        self.count_lbl.setStyleSheet(f"color: {GOLD_DIM}; font-size: 10px; background: transparent; border: none;")
        tb.addWidget(self.count_lbl)
        layout.addWidget(title_bar)

        self.philosopher_list = QListWidget()
        self.philosopher_list.setStyleSheet(f"""
            QListWidget {{
                background: {BG_SURFACE};
                border: none;
                border-radius: 0;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                color: {TEXT_PRI};
                border: none;
                margin: 1px 0;
            }}
            QListWidget::item:selected {{
                background: {GOLD_DIM};
                color: {GOLD_LIGHT};
            }}
            QListWidget::item:hover:!selected {{
                background: {BG_HOVER};
            }}
        """)
        self.philosopher_list.itemDoubleClicked.connect(self._on_list_double_click)
        self.philosopher_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.philosopher_list, stretch=1)

        actions = QWidget()
        actions.setFixedHeight(52)
        actions.setStyleSheet(f"background: {BG_RAISED}; border-top: 1px solid {BORDER};")
        act_layout = QHBoxLayout(actions)
        act_layout.setContentsMargins(10, 0, 10, 0)
        act_layout.setSpacing(8)

        self.btn_view = QPushButton("👁  View")
        self.btn_view.clicked.connect(self._on_view_philosopher)
        self.btn_view.setEnabled(False)

        self.btn_edit = QPushButton("✏  Edit")
        self.btn_edit.clicked.connect(self._on_edit_philosopher)
        self.btn_edit.setEnabled(False)

        self.btn_delete = QPushButton("✕")
        self.btn_delete.setObjectName("btn_danger")
        self.btn_delete.setFixedWidth(36)
        self.btn_delete.clicked.connect(self._on_delete_philosopher)
        self.btn_delete.setEnabled(False)

        act_layout.addWidget(self.btn_view)
        act_layout.addWidget(self.btn_edit)
        act_layout.addWidget(self.btn_delete)
        layout.addWidget(actions)

        return sidebar

    def _build_tabs(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)

        self.timeline_view = TimelineView()
        self.timeline_view.philosopher_clicked.connect(self._on_philosopher_clicked)
        self.tabs.addTab(self.timeline_view, "📅  Timeline")

        self.country_view = CountryView()
        self.country_view.philosopher_clicked.connect(self._on_philosopher_clicked)
        self.tabs.addTab(self.country_view, "🌍  By Country")

        layout.addWidget(self.tabs)
        return container

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_data(self):
        q, country, era, sort = self._current_filters
        self._philosophers = search_philosophers(q, country, era, sort)
        self._refresh_list()
        self._refresh_views()
        self._refresh_country_dropdown()

    def _refresh_list(self):
        self.philosopher_list.blockSignals(True)
        self.philosopher_list.clear()
        for p in self._philosophers:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            item.setText(f"{p.name}\n{p.lifespan_label}  ·  {p.birth_country}")
            item.setForeground(QColor(TEXT_PRI))
            self.philosopher_list.addItem(item)
        self.count_lbl.setText(str(len(self._philosophers)))
        self.philosopher_list.blockSignals(False)
        self._on_selection_changed()

    def _refresh_views(self):
        self.timeline_view.set_philosophers(self._philosophers)
        self.country_view.set_philosophers(self._philosophers)

    def _refresh_country_dropdown(self):
        self.search_bar.update_countries(get_all_countries())

    # ── Signals / Slots ───────────────────────────────────────────────────────

    @pyqtSlot(str, str, str, str)
    def _on_filters_changed(self, query: str, country: str, era: str, sort: str):
        self._current_filters = (query, country, era, sort)
        self._load_data()

    def _on_selection_changed(self):
        has_sel = bool(self.philosopher_list.selectedItems())
        self.btn_view.setEnabled(has_sel)
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)

    def _selected_philosopher_id(self) -> int | None:
        items = self.philosopher_list.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def _on_list_double_click(self, item: QListWidgetItem):
        self._show_detail(item.data(Qt.ItemDataRole.UserRole))

    @pyqtSlot(int)
    def _on_philosopher_clicked(self, pid: int):
        self._show_detail(pid)

    def _show_detail(self, pid: int):
        p = db.get_philosopher(pid)
        if p:
            dlg = DetailDialog(p, parent=self)
            dlg.exec()

    # ── CRUD actions ──────────────────────────────────────────────────────────

    def _on_add_philosopher(self):
        dlg = PhilosopherFormDialog(parent=self)
        if dlg.exec():
            self.quote_widget.refresh()
            self._load_data()

    def _on_view_philosopher(self):
        pid = self._selected_philosopher_id()
        if pid:
            self._show_detail(pid)

    def _on_edit_philosopher(self):
        pid = self._selected_philosopher_id()
        if pid:
            p = db.get_philosopher(pid)
            if p:
                dlg = PhilosopherFormDialog(parent=self, philosopher=p)
                if dlg.exec():
                    self.quote_widget.refresh()
                    self._load_data()

    def _on_delete_philosopher(self):
        pid = self._selected_philosopher_id()
        if not pid:
            return
        p = db.get_philosopher(pid)
        if not p:
            return
        reply = QMessageBox.question(
            self, "Delete Philosopher",
            f"Are you sure you want to delete '{p.name}'?\n"
            "All associated quotes will also be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_philosopher(pid)
            self.quote_widget.refresh()
            self._load_data()
