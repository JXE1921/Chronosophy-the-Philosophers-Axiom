"""
ui/main_window.py — Root application window for Chronosophy v2.

Coordinates:
· Sidebar list (philosophers)
· Search / filter bar (now 5-arg signal including favourites_only)
· Daily quote widget (with favourite toggle)
· Clock (London time)
· Five tabs: Timeline, By Country, Influence Graph, World Map, Statistics
· Menu bar: File, View, Help
· Keyboard shortcuts (Ctrl+1–5 tabs, Ctrl+N, Ctrl+F, Ctrl+E, F11)
· Comparison dialog (select two philosophers, click Compare)
· "Show in Graph" wiring from DetailDialog → Influence Graph tab + centre_on
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QFrame, QMessageBox, QSizePolicy, QFileDialog,
    QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, QTime, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QIcon, QAction, QKeySequence, QShortcut

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
from services.export import export_csv, export_json


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
        # 5-tuple: (query, country, era, sort, favourites_only)
        self._current_filters: tuple = ("", "All", "All", "birth_year", False)
        self._philosophers: list[Philosopher] = []

        self.setWindowTitle("Chronosophy — The Philosopher's Axiom")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(1050, 680)

        self._build_menu()
        self._build_ui()
        self._build_shortcuts()

    # ── Called by main.py after window.show() ───────────────────────────────

    def load_initial_data(self):
        self._load_data()
        self.stats_view.refresh()

    # ── Window state persistence ─────────────────────────────────────────────

    def closeEvent(self, event):
        if self._settings:
            self._settings.setValue("windowGeometry", self.saveGeometry())
            self._settings.setValue("windowState", self.saveState())
            self._settings.setValue("windowMaximised",
                                    self.windowState() == Qt.WindowState.WindowMaximized)
            self._settings.setValue("windowFullscreen", self.isFullScreen())
        super().closeEvent(event)

    # ── Menu bar ─────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # ── File ──────────────────────────────────────────────────────────
        file_menu = mb.addMenu("File")

        act_export_csv = QAction("Export to CSV…", self)
        act_export_csv.setShortcut(QKeySequence("Ctrl+E"))
        act_export_csv.triggered.connect(self._on_export_csv)
        file_menu.addAction(act_export_csv)

        act_export_json = QAction("Export to JSON…", self)
        act_export_json.triggered.connect(self._on_export_json)
        file_menu.addAction(act_export_json)

        file_menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── View ──────────────────────────────────────────────────────────
        view_menu = mb.addMenu("View")

        act_fullscreen = QAction("Toggle Fullscreen", self)
        act_fullscreen.setShortcut(QKeySequence("F11"))
        act_fullscreen.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(act_fullscreen)

        view_menu.addSeparator()

        # Tab switchers
        for idx, label in enumerate([
            "Timeline", "By Country", "Influence Graph", "World Map", "Statistics"
        ], start=1):
            act = QAction(f"{label}  (Ctrl+{idx})", self)
            act.setShortcut(QKeySequence(f"Ctrl+{idx}"))
            act.triggered.connect(lambda checked, i=idx - 1: self.tabs.setCurrentIndex(i))
            view_menu.addAction(act)

        # ── Help ──────────────────────────────────────────────────────────
        help_menu = mb.addMenu("Help")

        act_shortcuts = QAction("Keyboard Shortcuts…", self)
        act_shortcuts.triggered.connect(lambda: ShortcutsDialog(self).exec())
        help_menu.addAction(act_shortcuts)

        help_menu.addSeparator()

        act_about = QAction("About Chronosophy…", self)
        act_about.triggered.connect(lambda: AboutDialog(self).exec())
        help_menu.addAction(act_about)

    # ── Global keyboard shortcuts ────────────────────────────────────────────

    def _build_shortcuts(self):
        # Add philosopher
        sc_add = QShortcut(QKeySequence("Ctrl+N"), self)
        sc_add.activated.connect(self._on_add_philosopher)

        # Focus search
        sc_search = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_search.activated.connect(lambda: self.search_bar.inp_search.setFocus())

        # Delete selected
        sc_delete = QShortcut(QKeySequence("Delete"), self)
        sc_delete.activated.connect(self._on_delete_philosopher)

        # Open detail on Enter in list
        sc_enter = QShortcut(QKeySequence("Return"), self)
        sc_enter.activated.connect(self._on_view_philosopher)

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

        logo = QLabel("⟁")
        logo.setStyleSheet(f"color: {GOLD}; font-size: 22px; background: transparent; border: none;")
        layout.addWidget(logo)

        title = QLabel("Chronosophy:")
        title.setStyleSheet(f"""
            color: {GOLD_LIGHT}; font-family: 'Georgia', serif;
            font-size: 18px; letter-spacing: 0.5px; background: transparent; border: none;
        """)
        layout.addWidget(title)

        subtitle = QLabel("The Philosopher's Axiom")
        subtitle.setStyleSheet(f"""
            color: {TEXT_SEC}; font-family: 'Georgia', serif;
            font-size: 14px; font-style: italic; background: transparent; border: none;
        """)
        layout.addWidget(subtitle)
        layout.addStretch()

        # London clock
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"""
            color: {TEXT_SEC}; font-family: 'Georgia', serif;
            font-size: 13px; letter-spacing: 1px; background: transparent;
            border: 1px solid {BORDER}; border-radius: 5px; padding: 3px 10px;
        """)
        self.clock_label.setToolTip("London time (Europe/London)")
        layout.addWidget(self.clock_label)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        layout.addSpacing(12)

        self.btn_add = QPushButton("＋  Add Philosopher")
        self.btn_add.setObjectName("btn_primary")
        self.btn_add.setFixedHeight(36)
        self.btn_add.setToolTip("Add a new philosopher  (Ctrl+N)")
        self.btn_add.clicked.connect(self._on_add_philosopher)
        layout.addWidget(self.btn_add)

        return header

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
            QListWidget::item:hover:!selected {{ background: {BG_HOVER}; }}
        """)
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

        # Row 1: view / edit / delete
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.btn_view = QPushButton("👁  View")
        self.btn_view.clicked.connect(self._on_view_philosopher)
        self.btn_view.setEnabled(False)
        self.btn_view.setToolTip("Open detail view")
        row1.addWidget(self.btn_view)

        self.btn_edit = QPushButton("✏  Edit")
        self.btn_edit.clicked.connect(self._on_edit_philosopher)
        self.btn_edit.setEnabled(False)
        self.btn_edit.setToolTip("Edit selected philosopher")
        row1.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("✕")
        self.btn_delete.setObjectName("btn_danger")
        self.btn_delete.setFixedWidth(34)
        self.btn_delete.clicked.connect(self._on_delete_philosopher)
        self.btn_delete.setEnabled(False)
        self.btn_delete.setToolTip("Delete selected philosopher  (Delete key)")
        row1.addWidget(self.btn_delete)
        act_layout.addLayout(row1)

        # Row 2: compare (enabled only when exactly 2 are selected)
        self.btn_compare = QPushButton("⇆  Compare")
        self.btn_compare.clicked.connect(self._on_compare)
        self.btn_compare.setEnabled(False)
        self.btn_compare.setToolTip("Compare two selected philosophers side-by-side")
        act_layout.addWidget(self.btn_compare)

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
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # TAB_TIMELINE = 0
        self.timeline_view = TimelineView()
        self.timeline_view.philosopher_clicked.connect(self._on_philosopher_clicked)
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
            fav_mark = " ♥" if any(q.is_favourite for q in p.quotes) else ""
            item.setText(f"{p.name}{fav_mark}\n{p.lifespan_label}  ·  {p.birth_country}")
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

    # ── Influence graph → centre on ──────────────────────────────────────────

    @pyqtSlot(int)
    def _on_show_in_graph(self, pid: int):
        self.tabs.setCurrentIndex(TAB_GRAPH)
        self.graph_view.centre_on(pid)

    # ── Favourite toggled anywhere ────────────────────────────────────────────

    def _on_favourite_toggled(self, *args):
        """Refresh the philosopher list (which shows ♥ markers) and stats."""
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

    # ── View helpers ──────────────────────────────────────────────────────────

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
