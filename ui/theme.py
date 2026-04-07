"""
UI Theme - Dark, refined aesthetic for Automate Anything
"""

# Color palette
COLORS = {
    "bg_primary": "#0D0D0F",
    "bg_secondary": "#141418",
    "bg_card": "#1A1A20",
    "bg_hover": "#22222A",
    "bg_input": "#16161C",
    "border": "#2A2A35",
    "border_focus": "#5B5BF0",
    "accent": "#5B5BF0",
    "accent_hover": "#7070F5",
    "accent_dim": "#2A2A60",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "text_primary": "#F0F0F5",
    "text_secondary": "#8888A0",
    "text_muted": "#55556A",
    "run_green": "#10B981",
    "run_green_hover": "#059669",
}

STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {COLORS['bg_primary']};
}}

QWidget {{
    background-color: transparent;
    color: {COLORS['text_primary']};
    font-family: 'SF Pro Display', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: {COLORS['bg_secondary']};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 3px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS['text_muted']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {COLORS['bg_secondary']};
    height: 6px;
    border-radius: 3px;
}}

QScrollBar::handle:horizontal {{
    background: {COLORS['border']};
    border-radius: 3px;
}}

QLineEdit {{
    background-color: {COLORS['bg_input']};
    border: 1.5px solid {COLORS['border']};
    border-radius: 10px;
    padding: 10px 16px;
    color: {COLORS['text_primary']};
    font-size: 14px;
    selection-background-color: {COLORS['accent_dim']};
}}

QLineEdit:focus {{
    border-color: {COLORS['border_focus']};
    background-color: {COLORS['bg_card']};
}}

QLineEdit::placeholder {{
    color: {COLORS['text_muted']};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {COLORS['bg_input']};
    border: 1.5px solid {COLORS['border']};
    border-radius: 10px;
    padding: 10px 14px;
    color: {COLORS['text_primary']};
    font-size: 13px;
    selection-background-color: {COLORS['accent_dim']};
}}

QTextEdit:focus {{
    border-color: {COLORS['border_focus']};
}}

QPushButton {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

QPushButton:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton:pressed {{
    background-color: {COLORS['accent_dim']};
}}

QPushButton:disabled {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_muted']};
}}

QPushButton[secondary="true"] {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_secondary']};
    border: 1.5px solid {COLORS['border']};
}}

QPushButton[secondary="true"]:hover {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text_primary']};
    border-color: {COLORS['border_focus']};
}}

QPushButton[danger="true"] {{
    background-color: transparent;
    color: {COLORS['error']};
    border: 1.5px solid transparent;
}}

QPushButton[danger="true"]:hover {{
    background-color: rgba(239,68,68,0.1);
    border-color: {COLORS['error']};
}}

QPushButton[success="true"] {{
    background-color: {COLORS['run_green']};
}}

QPushButton[success="true"]:hover {{
    background-color: {COLORS['run_green_hover']};
}}

QComboBox {{
    background-color: {COLORS['bg_input']};
    border: 1.5px solid {COLORS['border']};
    border-radius: 8px;
    padding: 6px 12px;
    color: {COLORS['text_primary']};
    font-size: 13px;
    min-width: 180px;
}}

QComboBox:focus {{
    border-color: {COLORS['border_focus']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_card']};
    border: 1.5px solid {COLORS['border']};
    border-radius: 8px;
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['accent_dim']};
    padding: 4px;
    outline: none;
}}

QLabel {{
    color: {COLORS['text_primary']};
    background: transparent;
}}

QSplitter::handle {{
    background: {COLORS['border']};
    width: 1px;
}}

QTabWidget::pane {{
    border: none;
    background: transparent;
}}

QTabBar::tab {{
    background: transparent;
    color: {COLORS['text_muted']};
    padding: 8px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    color: {COLORS['text_primary']};
    border-bottom: 2px solid {COLORS['accent']};
}}

QTabBar::tab:hover:!selected {{
    color: {COLORS['text_secondary']};
}}

QMenuBar {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_secondary']};
    border-bottom: 1px solid {COLORS['border']};
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_hover']};
    border-radius: 4px;
}}

QMenu {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS['accent_dim']};
    color: {COLORS['text_primary']};
}}

QProgressBar {{
    background-color: {COLORS['bg_card']};
    border: none;
    border-radius: 4px;
    height: 4px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

QSplitter {{
    background: {COLORS['bg_primary']};
}}

QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {COLORS['border']};
}}
"""
