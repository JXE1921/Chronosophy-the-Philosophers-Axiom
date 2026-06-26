"""
ui/main_window.py — Root application window for Chronosophy v9.

v9 additions:
  · Reset View button now also resets scroll position to the first philosopher
  · UI zoom (Ctrl + = / − / 0) is persisted across sessions in QSettings
"""

import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QFrame, QMessageBox, QSizePolicy, QFileDialog,
    QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, QTime, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QIcon, QAction

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
from ui.influence_graph import InfluenceGraphView
from ui.world_map import WorldMapView
from ui.statistics_view import StatisticsView
from ui.search_bar import SearchBar
from ui.philosopher_form import PhilosopherFormDialog
from ui.detail_dialog import DetailDialog
from ui.comparison_dialog import ComparisonDialog
from ui.about_dialog import AboutDialog
from ui.shortcuts_dialog import ShortcutsDialog
from ui.shortcut_manager import ShortcutManager
from services.export import export_csv, export_json
from services.import_data import import_json as _import_json, import_csv as _import_csv


# Tab indices — keep in sync with _build_tabs()
TAB_TIMELINE  = 0
TAB_COUNTRY   = 1
TAB_GRAPH     = 2
TAB_MAP       = 3
TAB_STATS     = 4


class MainWindow(QMainWindow):
    """Application root window."""

    def __init__(self, settings: QSettings = None, icon_path: str = ""):
        super().__init__()
        self._settings = settings
        self._icon_path = icon_path
        self._current_filters: tuple = ("", "All", "All", "birth_year", False)
        self._philosophers: list[Philosopher] = []
        self._ui_scale: float = 1.0

        self.setWindowTitle("Chronosophy — The Philosopher's Axiom")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(1050, 680)

        # Central registry for every customisable shortcut — must exist before
        # _build_ui(), since the dropdown menu reads its current bindings.
        self.shortcuts = ShortcutManager(self, settings)

        self._build_ui()
        self._build_shortcuts()

    # ── Called by main.py after window.show() ───────────────────────────────

    def load_initial_data(self):
        self._load_data()
        self.stats_view.refresh()
        # Restore persisted UI state from the previous session
        if self._settings:
            # UI scale (Ctrl+= / Ctrl+- / Ctrl+0)
            saved_scale = self._settings.value("uiScale", type=float)
            if saved_scale and 0.6 <= saved_scale <= 2.0:
                self._set_ui_scale(saved_scale, persist=False)
            # Timeline zoom level
            saved_zoom = self._settings.value("timelineZoom", type=float)
            if saved_zoom and saved_zoom > 0:
                self.timeline_view.canvas.set_zoom(saved_zoom)

    @pyqtSlot(float)
    def _on_timeline_zoom_changed(self, zoom: float):
        """Immediately persist the new timeline zoom to QSettings."""
        if self._settings:
            self._settings.setValue("timelineZoom", zoom)

    # ── Window state persistence ─────────────────────────────────────────────

    def closeEvent(self, event):
        if self._settings:
            self._settings.setValue("windowGeometry", self.saveGeometry())
            self._settings.setValue("windowState", self.saveState())
            self._settings.setValue("windowMaximised",
                                    self.windowState() == Qt.WindowState.WindowMaximized)
            self._settings.setValue("windowFullscreen", self.isFullScreen())
            # Persist UI scale and timeline zoom so the next session opens identically
            self._settings.setValue("uiScale", self._ui_scale)
            if hasattr(self, 'timeline_view'):
                self._settings.setValue(
                    "timelineZoom", self.timeline_view.canvas.zoom()
                )
        super().closeEvent(event)

    # ── Global keyboard shortcuts ────────────────────────────────────────────

    def _build_shortcuts(self):
        """Register every action with the ShortcutManager, then build the live
        QShortcuts.  The manager is the single source of truth — bindings here,
        the menu hints, and the customiser dialog all stay in sync, and any user
        overrides saved in QSettings are honoured automatically."""
        sc = self.shortcuts

        # Navigation — switch tabs
        sc.register("tab_timeline", lambda: self.tabs.setCurrentIndex(TAB_TIMELINE))
        sc.register("tab_country",  lambda: self.tabs.setCurrentIndex(TAB_COUNTRY))
        sc.register("tab_graph",    lambda: self.tabs.setCurrentIndex(TAB_GRAPH))
        sc.register("tab_map",      lambda: self.tabs.setCurrentIndex(TAB_MAP))
        sc.register("tab_stats",    lambda: self.tabs.setCurrentIndex(TAB_STATS))

        # Philosophers
        sc.register("add",     self._on_add_philosopher)
        sc.register("search",  lambda: self.search_bar.inp_search.setFocus())
        sc.register("view",    self._on_view_philosopher)
        sc.register("edit",    self._on_edit_philosopher)
        sc.register("delete",  self._on_delete_philosopher)
        sc.register("compare", self._on_compare)

        # General
        sc.register("zoom_in",    lambda: self._set_ui_scale(self._ui_scale + 0.1))
        sc.register("zoom_out",   lambda: self._set_ui_scale(self._ui_scale - 0.1))
        sc.register("zoom_reset", lambda: self._set_ui_scale(1.0))
        sc.register("export_csv", self._on_export_csv)
        sc.register("export_json", self._on_export_json)
        sc.register("fullscreen", self._toggle_fullscreen)
        sc.register("shortcuts",  self._open_shortcuts_dialog)
        sc.register("quit",       self.close)

        sc.build()

    def _set_ui_scale(self, new_scale: float, persist: bool = True):
        """Re-apply the entire stylesheet with a new font-size scale factor."""
        from styles import get_stylesheet
        self._ui_scale = max(0.6, min(2.0, new_scale))
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        app.setStyleSheet(get_stylesheet(self._ui_scale))
        f = app.font()
        f.setPointSizeF(max(7, 12 * self._ui_scale))
        app.setFont(f)
        # Re-apply every inline stylesheet that has hardcoded font sizes
        # (inline styles have higher CSS specificity than the app stylesheet,
        # so they must be regenerated separately on every scale change)
        self._apply_scaled_styles(self._ui_scale)
        if persist and self._settings:
            self._settings.setValue("uiScale", self._ui_scale)

    def _apply_scaled_styles(self, scale: float):
        """Re-apply all inline widget stylesheets that contain explicit font sizes.

        Called once at build time (scale=1.0) and again on every zoom change.
        Without this, inline stylesheets on the sidebar list, labels and buttons
        override the app-level QSS and ignore the scale factor entirely.
        """
        s = scale  # shorthand

        def px(base: float) -> str:
            return f"{max(7, round(base * s))}px"

        # ── Sidebar title label ("PHILOSOPHERS") ─────────────────────────────
        if hasattr(self, '_sidebar_title_lbl'):
            self._sidebar_title_lbl.setStyleSheet(f"""
                color: {TEXT_DIM};
                font-size: {px(9)};
                letter-spacing: 2px;
                background: transparent;
                border: none;
            """)

        # ── Philosopher count badge ───────────────────────────────────────────
        if hasattr(self, 'count_lbl'):
            self.count_lbl.setStyleSheet(f"""
                color: {GOLD_DIM};
                font-size: {px(10)};
                background: transparent;
                border: none;
            """)

        # ── Philosopher list — item font size must be set inline because the
        #    widget's own stylesheet beats the app-level QListWidget::item rule
        if hasattr(self, 'philosopher_list'):
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
                    font-size: {px(13)};
                    border: none;
                    margin: 1px 0;
                }}
                QListWidget::item:selected {{
                    background: {GOLD_DIM};
                    color: {GOLD_LIGHT};
                }}
                QListWidget::item:hover:!selected {{ background: {BG_HOVER}; }}
            """)

        # ── Header: clock label ───────────────────────────────────────────────
        if hasattr(self, 'clock_label'):
            self.clock_label.setStyleSheet(f"""
                color: {TEXT_SEC};
                font-family: 'Georgia', serif;
                font-size: {px(12)};
                letter-spacing: 1px;
                background: transparent;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 2px 9px;
            """)



    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(f"background: {BG_BASE};")
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_header())

        self.quote_widget = QuoteWidget()
        self.quote_widget.favourite_toggled.connect(self._on_favourite_toggled)
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
        header.setFixedHeight(46)
        header.setStyleSheet(f"""
            QWidget {{
                background: {BG_DEEP};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 0, 22, 0)
        layout.setSpacing(0)

        # ── ⟁ Logo button — click to show File / View / Help menu ────────────
        logo_btn = QPushButton("⟁")
        logo_btn.setFixedSize(36, 36)
        logo_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        logo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logo_btn.setToolTip("Menu  (File · View · Help)")
        logo_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {GOLD};
                font-size: 20px;
                border-radius: 6px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {BG_RAISED};
                color: {GOLD_LIGHT};
            }}
            QPushButton:pressed {{
                background: {GOLD_MUTED};
            }}
            QPushButton::menu-indicator {{ width: 0; image: none; }}
        """)
        # Attach the popup menu — clicking the button shows it automatically.
        # Stored so the menu can be rebuilt when shortcut bindings change.
        self._logo_btn = logo_btn
        logo_btn.setMenu(self._build_app_menu())
        layout.addWidget(logo_btn)
        layout.addSpacing(10)

        # ── App title ─────────────────────────────────────────────────────────
        title_lbl = QLabel("Chronosophy:  The Philosopher's Axiom")
        title_lbl.setStyleSheet(f"""
            color: {GOLD_LIGHT};
            font-family: 'Georgia', serif;
            font-size: 14px;
            letter-spacing: 0.4px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(title_lbl)

        layout.addStretch()

        # ── London clock ─────────────────────────────────────────────────────
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"""
            color: {TEXT_SEC}; font-family: 'Georgia', serif;
            font-size: 12px; letter-spacing: 1px; background: transparent;
            border: 1px solid {BORDER}; border-radius: 5px; padding: 2px 9px;
        """)
        self.clock_label.setToolTip("London time (Europe/London)")
        layout.addWidget(self.clock_label)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        layout.addSpacing(12)

        # ── Add philosopher button ────────────────────────────────────────────
        self.btn_add = QPushButton("＋  Add Philosopher")
        self.btn_add.setObjectName("btn_primary")
        self.btn_add.setFixedHeight(32)
        self.btn_add.setToolTip(
            f"Add a new philosopher  ({self.shortcuts.display('add')})")
        self.btn_add.clicked.connect(self._on_add_philosopher)
        layout.addWidget(self.btn_add)

        return header

    def _menu_label(self, text: str, action_id: str) -> str:
        """Compose a menu-item label with the action's current binding appended.

        Reads the live binding from the ShortcutManager so the hint always
        matches whatever the user has customised (or nothing, if unbound)."""
        binding = self.shortcuts.display(action_id)
        if not binding or binding == "Unbound":
            return text
        return f"{text}  ({binding})"

    def _build_app_menu(self) -> "QMenu":
        """Build the popup QMenu that drops down from the ⟁ logo button.

        Three submenus — File, View, Help — exactly mirroring what the old
        inline menu bar had, but now hidden until the user clicks the logo.
        All keyboard shortcuts are active via the ShortcutManager; the labels
        below show each item's current binding as a hint only.
        """
        qss = f"""
            QMenu {{
                background: {BG_SURFACE};
                border: 1px solid {BORDER_LT};
                border-radius: 8px;
                padding: 4px;
                font-family: 'Georgia', serif;
                font-size: 12px;
            }}
            QMenu::item {{
                padding: 7px 28px 7px 18px;
                border-radius: 5px;
                color: {TEXT_PRI};
            }}
            QMenu::item:selected {{
                background: {GOLD_DIM};
                color: {GOLD_LIGHT};
            }}
            QMenu::item:disabled {{ color: {TEXT_DIM}; }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER};
                margin: 4px 8px;
            }}
            QMenu::right-arrow {{ width: 0; }}
        """

        from PyQt6.QtWidgets import QMenu as _QMenu
        root = _QMenu(self)
        root.setStyleSheet(qss)

        # ── File ──────────────────────────────────────────────────────────
        file_menu = root.addMenu("  File")
        file_menu.setStyleSheet(qss)

        act_csv = QAction(self._menu_label("Export to CSV…", "export_csv"), self)
        act_csv.triggered.connect(self._on_export_csv)
        file_menu.addAction(act_csv)

        act_json = QAction(self._menu_label("Export to JSON…", "export_json"), self)
        act_json.triggered.connect(self._on_export_json)
        file_menu.addAction(act_json)

        file_menu.addSeparator()

        act_import_json = QAction("Import from JSON…", self)
        act_import_json.triggered.connect(self._on_import_json)
        file_menu.addAction(act_import_json)

        act_import_csv = QAction("Import from CSV…", self)
        act_import_csv.triggered.connect(self._on_import_csv)
        file_menu.addAction(act_import_csv)

        file_menu.addSeparator()

        act_quit = QAction(self._menu_label("Quit", "quit"), self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── View ──────────────────────────────────────────────────────────
        view_menu = root.addMenu("  View")
        view_menu.setStyleSheet(qss)

        act_fs = QAction(self._menu_label("Toggle Fullscreen", "fullscreen"), self)
        act_fs.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(act_fs)

        view_menu.addSeparator()

        tab_items = [
            ("Timeline",         "tab_timeline", TAB_TIMELINE),
            ("By Country",       "tab_country",  TAB_COUNTRY),
            ("Influence Graph",  "tab_graph",    TAB_GRAPH),
            ("World Map",        "tab_map",      TAB_MAP),
            ("Statistics",       "tab_stats",    TAB_STATS),
        ]
        for label, action_id, index in tab_items:
            act = QAction(self._menu_label(label, action_id), self)
            act.triggered.connect(lambda checked, i=index: self.tabs.setCurrentIndex(i))
            view_menu.addAction(act)

        # ── Help ──────────────────────────────────────────────────────────
        help_menu = root.addMenu("  Help")
        help_menu.setStyleSheet(qss)

        act_sc = QAction(self._menu_label("Keyboard Shortcuts…", "shortcuts"), self)
        act_sc.triggered.connect(self._open_shortcuts_dialog)
        help_menu.addAction(act_sc)

        help_menu.addSeparator()

        act_ab = QAction("About Chronosophy…", self)
        act_ab.triggered.connect(lambda: AboutDialog(self).exec())
        help_menu.addAction(act_ab)

        return root

    def _update_clock(self):
        try:
            from zoneinfo import ZoneInfo
            from datetime import datetime
            now = datetime.now(ZoneInfo("Europe/London"))
            self.clock_label.setText(now.strftime("%H:%M:%S"))
        except Exception:
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

        # Store as self so _apply_scaled_styles can update it on zoom change
        self._sidebar_title_lbl = QLabel("PHILOSOPHERS")
        tb.addWidget(self._sidebar_title_lbl)
        tb.addStretch()
        self.count_lbl = QLabel("0")
        tb.addWidget(self.count_lbl)
        layout.addWidget(title_bar)

        self.philosopher_list = QListWidget()
        self.philosopher_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        self.philosopher_list.itemDoubleClicked.connect(self._on_list_double_click)
        self.philosopher_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.philosopher_list, stretch=1)

        actions = QWidget()
        actions.setFixedHeight(90)
        actions.setStyleSheet(f"background: {BG_RAISED}; border-top: 1px solid {BORDER};")
        act_layout = QVBoxLayout(actions)
        act_layout.setContentsMargins(10, 6, 10, 6)
        act_layout.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.btn_view = QPushButton("👁  View")
        self.btn_view.clicked.connect(self._on_view_philosopher)
        self.btn_view.setEnabled(False)
        self.btn_view.setToolTip(
            f"Open detail view  ({self.shortcuts.display('view')})")
        row1.addWidget(self.btn_view)

        self.btn_edit = QPushButton("✏  Edit")
        self.btn_edit.clicked.connect(self._on_edit_philosopher)
        self.btn_edit.setEnabled(False)
        self.btn_edit.setToolTip(
            f"Edit selected philosopher  ({self.shortcuts.display('edit')})")
        row1.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("✕")
        self.btn_delete.setObjectName("btn_danger")
        self.btn_delete.setFixedWidth(34)
        self.btn_delete.clicked.connect(self._on_delete_philosopher)
        self.btn_delete.setEnabled(False)
        self.btn_delete.setToolTip(
            f"Delete selected philosopher  ({self.shortcuts.display('delete')})")
        row1.addWidget(self.btn_delete)
        act_layout.addLayout(row1)

        self.btn_compare = QPushButton("⇆  Compare")
        self.btn_compare.clicked.connect(self._on_compare)
        self.btn_compare.setEnabled(False)
        self.btn_compare.setToolTip(
            "Compare two selected philosophers side-by-side  "
            f"({self.shortcuts.display('compare')})")
        act_layout.addWidget(self.btn_compare)

        layout.addWidget(actions)

        # Apply the initial (scale=1.0) inline styles — also called on every zoom change
        self._apply_scaled_styles(self._ui_scale)

        return sidebar

    def _build_tabs(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # TAB_TIMELINE = 0
        self.timeline_view = TimelineView()
        self.timeline_view.philosopher_clicked.connect(self._on_philosopher_clicked)
        # Persist zoom as it changes so the value survives crashes too
        self.timeline_view.canvas.zoom_changed.connect(self._on_timeline_zoom_changed)
        self.tabs.addTab(self.timeline_view, "📅  Timeline")

        # TAB_COUNTRY = 1
        self.country_view = CountryView()
        self.country_view.philosopher_clicked.connect(self._on_philosopher_clicked)
        self.tabs.addTab(self.country_view, "🌍  By Country")

        # TAB_GRAPH = 2
        self.graph_view = InfluenceGraphView()
        self.graph_view.philosopher_clicked.connect(self._on_philosopher_clicked)
        self.tabs.addTab(self.graph_view, "🕸  Graph")

        # TAB_MAP = 3
        self.map_view = WorldMapView()
        self.map_view.country_clicked.connect(self._on_map_country_clicked)
        self.tabs.addTab(self.map_view, "🗺  World Map")

        # TAB_STATS = 4
        self.stats_view = StatisticsView()
        # Clickable statistics → filtered views / graph / detail dialogs
        self.stats_view.era_selected.connect(self._on_stat_era_selected)
        self.stats_view.country_selected.connect(self._on_stat_country_selected)
        self.stats_view.philosopher_selected.connect(self._on_philosopher_clicked)
        self.stats_view.favourites_requested.connect(self._on_stat_favourites)
        self.stats_view.graph_requested.connect(
            lambda: self.tabs.setCurrentIndex(TAB_GRAPH))
        self.stats_view.show_all_requested.connect(self._on_stat_show_all)
        self.tabs.addTab(self.stats_view, "📊  Statistics")

        layout.addWidget(self.tabs)
        return container

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_data(self):
        q, country, era, sort, favs_only = self._current_filters
        self._philosophers = search_philosophers(q, country, era, sort, favs_only)
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
        self.graph_view.set_philosophers(self._philosophers)
        self.map_view.set_philosophers(self._philosophers)

    def _refresh_country_dropdown(self):
        self.search_bar.update_countries(get_all_countries())

    # ── Signals / Slots ──────────────────────────────────────────────────────

    @pyqtSlot(str, str, str, str, bool)
    def _on_filters_changed(self, query: str, country: str, era: str,
                             sort: str, favs_only: bool):
        self._current_filters = (query, country, era, sort, favs_only)
        self._load_data()

    def _on_selection_changed(self):
        items = self.philosopher_list.selectedItems()
        count = len(items)
        self.btn_view.setEnabled(count == 1)
        self.btn_edit.setEnabled(count == 1)
        self.btn_delete.setEnabled(count >= 1)
        self.btn_compare.setEnabled(count == 2)

    def _selected_philosopher_id(self) -> int | None:
        items = self.philosopher_list.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def _selected_philosopher_ids(self) -> list[int]:
        return [item.data(Qt.ItemDataRole.UserRole)
                for item in self.philosopher_list.selectedItems()]

    def _on_list_double_click(self, item: QListWidgetItem):
        self._show_detail(item.data(Qt.ItemDataRole.UserRole))

    @pyqtSlot(int)
    def _on_philosopher_clicked(self, pid: int):
        self._show_detail(pid)

    def _show_detail(self, pid: int):
        p = db.get_philosopher(pid)
        if not p:
            return
        dlg = DetailDialog(p, parent=self)
        dlg.show_in_graph.connect(self._on_show_in_graph)
        dlg.favourite_toggled.connect(self._on_favourite_toggled)
        dlg.exec()

    def _on_tab_changed(self, index: int):
        # Refresh statistics lazily when the user switches to that tab
        if index == TAB_STATS:
            self.stats_view.refresh()

    # ── World map → filter integration ───────────────────────────────────────

    @pyqtSlot(str)
    def _on_map_country_clicked(self, country: str):
        """Clicking a country dot on the map sets the country filter and
        switches back to the By Country tab for the filtered card view."""
        self.search_bar.cmb_country.setCurrentText(country)
        # If the country isn't found (new entry), add it temporarily
        if self.search_bar.cmb_country.currentText() != country:
            self.search_bar.cmb_country.addItem(country)
            self.search_bar.cmb_country.setCurrentText(country)
        self.tabs.setCurrentIndex(TAB_COUNTRY)

    # ── Statistics → filter integration ──────────────────────────────────────

    def _apply_stat_filter(self, *, country: str = "All", era: str = "All",
                           favourites: bool = False, tab: int = TAB_TIMELINE):
        """Atomically set the search-bar filters from a statistics click and
        switch to the requested tab.

        Statistics are computed across the *whole* archive, so each click resets
        the other filters first — that way the resulting view contains exactly
        the number of philosophers the clicked value advertised.
        """
        sb = self.search_bar
        widgets = (sb.inp_search, sb.cmb_country, sb.cmb_era, sb.cmb_sort, sb.chk_fav)
        for w in widgets:
            w.blockSignals(True)

        sb.inp_search.clear()
        if country != "All" and sb.cmb_country.findText(country) < 0:
            sb.cmb_country.addItem(country)
        sb.cmb_country.setCurrentText(
            country if sb.cmb_country.findText(country) >= 0 else "All")
        sb.cmb_era.setCurrentText(era if sb.cmb_era.findText(era) >= 0 else "All")
        sb.chk_fav.setChecked(favourites)

        for w in widgets:
            w.blockSignals(False)

        sb._emit()                          # single reload of list + views
        self.tabs.setCurrentIndex(tab)

    @pyqtSlot(str)
    def _on_stat_era_selected(self, era: str):
        self._apply_stat_filter(era=era, tab=TAB_TIMELINE)

    @pyqtSlot(str)
    def _on_stat_country_selected(self, country: str):
        self._apply_stat_filter(country=country, tab=TAB_COUNTRY)

    def _on_stat_favourites(self):
        self._apply_stat_filter(favourites=True, tab=TAB_TIMELINE)

    def _on_stat_show_all(self):
        self._apply_stat_filter(tab=TAB_TIMELINE)

    # ── Influence graph → centre on ──────────────────────────────────────────

    @pyqtSlot(int)
    def _on_show_in_graph(self, pid: int):
        self.tabs.setCurrentIndex(TAB_GRAPH)
        self.graph_view.centre_on(pid)

    # ── Favourite toggled anywhere ────────────────────────────────────────────

    def _on_favourite_toggled(self, *args):
        """Refresh the philosopher list and stats."""
        self._refresh_list()
        if self.tabs.currentIndex() == TAB_STATS:
            self.stats_view.refresh()

    # ── CRUD actions ─────────────────────────────────────────────────────────

    def _on_add_philosopher(self):
        dlg = PhilosopherFormDialog(parent=self)
        if dlg.exec():
            self.quote_widget.refresh()
            self._load_data()
            self.stats_view.refresh()

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
                    self.stats_view.refresh()

    def _on_delete_philosopher(self):
        pids = self._selected_philosopher_ids()
        if not pids:
            return
        if len(pids) == 1:
            p = db.get_philosopher(pids[0])
            msg = f"Are you sure you want to delete '{p.name}'?\nAll associated quotes will also be removed."
        else:
            msg = f"Are you sure you want to delete {len(pids)} philosophers?\nAll associated quotes will also be removed."
        reply = QMessageBox.question(
            self, "Delete Philosopher", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Yes:
            for pid in pids:
                delete_philosopher(pid)
            self.quote_widget.refresh()
            self._load_data()
            self.stats_view.refresh()

    def _on_compare(self):
        pids = self._selected_philosopher_ids()
        if len(pids) != 2:
            return
        left = db.get_philosopher(pids[0])
        right = db.get_philosopher(pids[1])
        if left and right:
            ComparisonDialog(left, right, parent=self).exec()

    # ── Export actions ────────────────────────────────────────────────────────

    def _on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", "chronosophy_export.csv",
            "CSV files (*.csv);;All files (*)"
        )
        if path:
            from services.export import export_csv
            ok, msg = export_csv(path)
            if ok:
                QMessageBox.information(self, "Export Complete", msg)
            else:
                QMessageBox.warning(self, "Export Failed", msg)

    def _on_export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to JSON", "chronosophy_export.json",
            "JSON files (*.json);;All files (*)"
        )
        if path:
            from services.export import export_json
            ok, msg = export_json(path)
            if ok:
                QMessageBox.information(self, "Export Complete", msg)
            else:
                QMessageBox.warning(self, "Export Failed", msg)

    def _on_import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import from JSON", "",
            "JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        reply = QMessageBox.warning(
            self, "Replace Database?",
            "Importing will replace your entire database with the contents of this file.\n\n"
            "This cannot be undone. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg = _import_json(path)
        if ok:
            self.quote_widget.refresh()
            self._load_data()
            self.stats_view.refresh()
            QMessageBox.information(self, "Import Complete", msg)
        else:
            QMessageBox.warning(self, "Import Failed", msg)

    def _on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import from CSV", "",
            "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        reply = QMessageBox.warning(
            self, "Replace Database?",
            "Importing will replace your entire database with the contents of this file.\n\n"
            "This cannot be undone. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg = _import_csv(path)
        if ok:
            self.quote_widget.refresh()
            self._load_data()
            self.stats_view.refresh()
            QMessageBox.information(self, "Import Complete", msg)
        else:
            QMessageBox.warning(self, "Import Failed", msg)

    # ── Shortcuts ──────────────────────────────────────────────────────────────

    def _open_shortcuts_dialog(self):
        """Open the editable shortcut customiser.

        Edits apply live and persist as they happen, so once the dialog closes
        we only need to refresh the hints shown in the menu and tooltips."""
        ShortcutsDialog(self.shortcuts, parent=self).exec()
        self._refresh_shortcut_labels()

    def _refresh_shortcut_labels(self):
        """Rebuild the dropdown menu and tooltips so their binding hints match
        whatever the user just customised."""
        old_menu = self._logo_btn.menu()
        self._logo_btn.setMenu(self._build_app_menu())
        if old_menu is not None:
            old_menu.deleteLater()
        self.btn_add.setToolTip(
            f"Add a new philosopher  ({self.shortcuts.display('add')})")
        self.btn_view.setToolTip(
            f"Open detail view  ({self.shortcuts.display('view')})")
        self.btn_edit.setToolTip(
            f"Edit selected philosopher  ({self.shortcuts.display('edit')})")
        self.btn_delete.setToolTip(
            f"Delete selected philosopher  ({self.shortcuts.display('delete')})")
        self.btn_compare.setToolTip(
            "Compare two selected philosophers side-by-side  "
            f"({self.shortcuts.display('compare')})")

    # ── View helpers ──────────────────────────────────────────────────────────

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
