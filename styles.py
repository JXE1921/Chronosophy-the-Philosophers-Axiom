"""
styles.py — Central dark-theme stylesheet.
Colour palette inspired by aged parchment and candlelight — warm gold on deep charcoal.
"""

# ─── Colour tokens ────────────────────────────────────────────────────────────
BG_DEEP    = "#0C0C0E"          # deepest background
BG_BASE    = "#12121A"          # main window background
BG_SURFACE = "#1A1A24"          # panels / cards
BG_RAISED  = "#22222E"          # inputs, list items
BG_HOVER   = "#2A2A38"          # hover state
BORDER     = "#2E2E40"          # subtle dividers
BORDER_LT  = "#3A3A50"          # lighter border / focus ring

GOLD       = "#C9A84C"          # primary accent — warm gold
GOLD_LIGHT = "#DFC073"          # lighter gold for headings
GOLD_DIM   = "#8B6914"          # dimmed gold for less prominent accents
GOLD_MUTED = "#5A4010"          # very muted background tint
GOLD_HOVER = "#A8862C"          # mid-gold — primary button hover (keeps light text readable)

TEXT_PRI   = "#EEEEF5"          # primary text
TEXT_SEC   = "#9090A8"          # secondary / captions
TEXT_DIM   = "#60607A"          # disabled / very quiet

RED        = "#E05C5C"          # destructive actions
RED_DIM    = "#7A2A2A"
GREEN      = "#5CBB8A"          # success / live indicator
TEAL       = "#4AAFB4"          # info accent

# Era colour map — muted, legible
ERA_COLORS = {
    "Pre-Socratic":        "#5E4A7E",   # dusty violet
    "Classical":           "#7E5A3C",   # warm terracotta
    "Hellenistic / Roman": "#3C6B5E",   # sea-green
    "Medieval":             "#4E5E7E",   # slate blue
    "Renaissance":          "#6B4E3C",   # sienna
    "Early Modern":         "#3C6B6B",   # teal slate
    "Modern":               "#5E6B3C",   # olive
    "Contemporary":         "#4E4E7E",   # indigo
}

# Country badge colors (muted)
COUNTRY_COLORS = [
    "#4A5E7E", "#5E4A7E", "#7E5A3C", "#3C6B5E",
    "#6B4E3C", "#5E6B3C", "#3C5E6B", "#7E3C5E",
    "#3C7E6B", "#5E3C7E", "#6B5E3C", "#3C4E7E",
]

# ─── v10 additions ─────────────────────────────────────────────────────────────
# Graph view tokens
GRAPH_NODE_FILL      = "#22222E"
GRAPH_NODE_HOVER     = "#3A3A50"
GRAPH_EDGE           = "#3A3A50"
GRAPH_EDGE_HIGHLIGHT = "#C9A84C"

# World map tokens
MAP_LAND        = "#1E1E2A"
MAP_LAND_BORDER = "#2E2E40"
MAP_OCEAN       = "#0C0C0E"
MAP_DOT         = "#C9A84C"
MAP_DOT_HOVER   = "#DFC073"

# Favourite (heart/star) accent
FAVOURITE       = "#E0A050"


# ─── Main QSS stylesheet ──────────────────────────────────────────────────────
def get_stylesheet(scale: float = 1.0) -> str:
    """Return the full QSS stylesheet. `scale` multiplies all explicit font
    sizes so Ctrl+= / Ctrl+- can zoom the entire UI without rebuilding widgets."""

    def px(base: int) -> str:
        return f"{max(7, round(base * scale))}px"

    return f"""
    /* ── Global ────────────────────────────────────────────────── */
    * {{
        font-family: "Georgia", "Times New Roman", serif;
        color: {TEXT_PRI};
        selection-background-color: {GOLD_DIM};
    }}

    QMainWindow, QDialog {{
        background-color: {BG_BASE};
    }}

    QWidget {{
        background-color: transparent;
    }}

    /* ── Scroll bars ────────────────────────────────────────────── */
    QScrollBar:vertical {{
        background: {BG_BASE};
        width: 8px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_LT};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {GOLD_DIM}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QScrollBar:horizontal {{
        background: {BG_BASE};
        height: 8px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_LT};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {GOLD_DIM}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ── Tab Widget ─────────────────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        border-top: none;
        background: {BG_SURFACE};
        border-radius: 0 0 8px 8px;
    }}
    QTabBar::tab {{
        background: {BG_RAISED};
        color: {TEXT_SEC};
        padding: 10px 22px;
        margin-right: 2px;
        border: 1px solid {BORDER};
        border-bottom: none;
        border-radius: 6px 6px 0 0;
        font-size: {px(13)};
        letter-spacing: 0.5px;
    }}
    QTabBar::tab:selected {{
        background: {BG_SURFACE};
        color: {GOLD};
        border-color: {BORDER_LT};
    }}
    QTabBar::tab:hover:!selected {{ background: {BG_HOVER}; color: {TEXT_PRI}; }}

    /* ── Push Buttons ───────────────────────────────────────────── */
    QPushButton {{
        background-color: {BG_RAISED};
        color: {TEXT_SEC};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 18px;
        font-size: {px(13)};
        font-family: "Georgia", serif;
    }}
    QPushButton:hover {{
        background-color: {BG_HOVER};
        border-color: {BORDER_LT};
        color: {TEXT_PRI};
    }}
    QPushButton:pressed {{ background-color: {GOLD_MUTED}; border-color: {GOLD_DIM}; }}
    QPushButton:disabled {{
        background-color: {BG_BASE};
        color: {TEXT_DIM};
        border-color: {BORDER};
    }}

    QPushButton#btn_primary {{
        background-color: {GOLD_DIM};
        color: {TEXT_PRI};
        border: 1px solid {GOLD};
        font-weight: bold;
    }}
    /* Hover keeps a warm mid-gold with light text — it must never invert to a
       near-black fill/text, which is what previously made the button look black. */
    QPushButton#btn_primary:hover {{
        background-color: {GOLD_HOVER};
        color: {TEXT_PRI};
        border-color: {GOLD_LIGHT};
    }}
    QPushButton#btn_primary:pressed {{
        background-color: {GOLD_DIM};
        color: {TEXT_PRI};
        border-color: {GOLD};
    }}

    QPushButton#btn_danger {{
        background-color: {RED_DIM};
        color: {RED};
        border: 1px solid {RED};
    }}
    QPushButton#btn_danger:hover {{ background-color: {RED}; color: white; }}

    /* ── Line edits / Text areas ────────────────────────────────── */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {BG_RAISED};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 10px;
        font-size: {px(13)};
        color: {TEXT_PRI};
        selection-background-color: {GOLD_DIM};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {GOLD_DIM};
        background-color: #1E1E2C;
    }}
    QLineEdit::placeholder {{ color: {TEXT_DIM}; }}

    /* ── Combo / Spin boxes ─────────────────────────────────────── */
    QComboBox {{
        background-color: {BG_RAISED};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 10px;
        font-size: {px(13)};
        color: {TEXT_PRI};
        min-width: 120px;
    }}
    QComboBox:focus {{ border-color: {GOLD_DIM}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox::down-arrow {{ image: none; width: 0; }}
    QComboBox QAbstractItemView {{
        background: {BG_SURFACE};
        border: 1px solid {BORDER_LT};
        selection-background-color: {GOLD_DIM};
        outline: none;
    }}

    QSpinBox {{
        background-color: {BG_RAISED};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 10px;
        font-size: {px(13)};
        color: {TEXT_PRI};
    }}
    QSpinBox:focus {{ border-color: {GOLD_DIM}; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 20px; }}

    /* ── Labels ─────────────────────────────────────────────────── */
    QLabel {{ background: transparent; }}
    QLabel#heading {{
        font-size: {px(22)};
        color: {GOLD_LIGHT};
        font-family: "Georgia", serif;
    }}
    QLabel#subheading {{
        font-size: {px(15)};
        color: {TEXT_SEC};
        font-style: italic;
    }}
    QLabel#field_label {{
        font-size: {px(12)};
        color: {TEXT_SEC};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    /* ── List / Tree widgets ────────────────────────────────────── */
    QListWidget, QTreeWidget {{
        background-color: {BG_SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        outline: none;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 10px 14px;
        border-radius: 6px;
        color: {TEXT_PRI};
        margin: 2px 0;
    }}
    QListWidget::item:selected {{
        background-color: {GOLD_DIM};
        color: {GOLD_LIGHT};
    }}
    QListWidget::item:hover:!selected {{ background-color: {BG_HOVER}; }}

    /* ── Splitter ───────────────────────────────────────────────── */
    QSplitter::handle {{
        background-color: {BORDER};
        width: 2px;
    }}
    QSplitter::handle:hover {{ background-color: {GOLD_DIM}; }}

    /* ── Tool tips ──────────────────────────────────────────────── */
    QToolTip {{
        background-color: {BG_SURFACE};
        color: {TEXT_PRI};
        border: 1px solid {BORDER_LT};
        padding: 6px 10px;
        border-radius: 6px;
        font-size: {px(12)};
    }}

    /* ── Menu bar ───────────────────────────────────────────────── */
    QMenuBar {{
        background-color: {BG_DEEP};
        color: {TEXT_SEC};
        border-bottom: 1px solid {BORDER};
        padding: 2px 8px;
        font-size: {px(12)};
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 6px 12px;
        border-radius: 4px;
    }}
    QMenuBar::item:selected {{
        background-color: {BG_RAISED};
        color: {GOLD};
    }}
    QMenu {{
        background-color: {BG_SURFACE};
        border: 1px solid {BORDER_LT};
        padding: 4px;
        font-size: {px(12)};
    }}
    QMenu::item {{
        padding: 7px 24px 7px 16px;
        border-radius: 4px;
        color: {TEXT_PRI};
    }}
    QMenu::item:selected {{
        background-color: {GOLD_DIM};
        color: {GOLD_LIGHT};
    }}
    QMenu::item:disabled {{ color: {TEXT_DIM}; }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER};
        margin: 4px 8px;
    }}

    /* ── Message boxes ──────────────────────────────────────────── */
    QMessageBox {{
        background-color: {BG_SURFACE};
    }}
    QMessageBox QLabel {{ color: {TEXT_PRI}; font-size: {px(14)}; }}

    /* ── CheckBox ───────────────────────────────────────────────── */
    QCheckBox {{
        color: {TEXT_PRI};
        font-size: {px(12)};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {BORDER_LT};
        border-radius: 3px;
        background: {BG_RAISED};
    }}
    QCheckBox::indicator:checked {{
        background: {GOLD_DIM};
        border-color: {GOLD};
    }}
    QCheckBox::indicator:hover {{ border-color: {GOLD_DIM}; }}
    """
