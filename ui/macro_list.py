"""
Macro List - Scrollable manager panel for saved macros
"""
import time
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.storage import Database, Macro
from ui.theme import COLORS


def _time_ago(ts: float) -> str:
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    elif diff < 3600:
        return f"{int(diff // 60)}m ago"
    elif diff < 86400:
        return f"{int(diff // 3600)}h ago"
    else:
        return datetime.fromtimestamp(ts).strftime("%b %d")


class MacroCard(QFrame):
    run_clicked = Signal(object)
    edit_clicked = Signal(object)
    delete_clicked = Signal(object)

    def __init__(self, macro: Macro):
        super().__init__()
        self.macro = macro
        self._build()

    def _build(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                margin: 0;
            }}
            QFrame:hover {{
                border-color: {COLORS['border_focus']};
                background-color: {COLORS['bg_hover']};
            }}
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Top row: name + time
        top_row = QHBoxLayout()

        name = QLabel(self.macro.name)
        name_font = QFont()
        name_font.setPointSize(13)
        name_font.setWeight(QFont.Weight.DemiBold)
        name.setFont(name_font)
        name.setStyleSheet(f"color: {COLORS['text_primary']};")
        top_row.addWidget(name)

        top_row.addStretch()

        time_label = QLabel(_time_ago(self.macro.updated_at))
        time_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        top_row.addWidget(time_label)

        layout.addLayout(top_row)

        # Summary
        if self.macro.summary:
            summary = QLabel(self.macro.summary)
            summary.setWordWrap(True)
            summary.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            layout.addWidget(summary)

        # Stats row
        steps_label = QLabel(f"{len(self.macro.actions)} steps")
        steps_label.setStyleSheet(f"""
            color: {COLORS['accent']};
            background: {COLORS['accent_dim']};
            border-radius: 4px;
            padding: 2px 7px;
            font-size: 11px;
            font-weight: 600;
        """)

        # Bottom row: badge + actions
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(steps_label)
        bottom_row.addStretch()

        for label, prop, signal in [
            ("▶ Run", "success", self.run_clicked),
            ("Edit", "secondary", self.edit_clicked),
            ("Delete", "danger", self.delete_clicked),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setProperty(prop, True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, s=signal: s.emit(self.macro))
            bottom_row.addWidget(btn)

        layout.addLayout(bottom_row)


class MacroListPanel(QWidget):
    run_macro = Signal(object)
    edit_macro = Signal(object)

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._cards = {}
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"background: {COLORS['bg_secondary']}; border-bottom: 1px solid {COLORS['border']};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("Saved Macros")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._count_label = QLabel("0 macros")
        self._count_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        header_layout.addWidget(self._count_label)

        layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {COLORS['bg_primary']}; border: none;")

        self._list_container = QWidget()
        self._list_container.setStyleSheet(f"background: {COLORS['bg_primary']};")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(16, 16, 16, 16)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, stretch=1)

        # Empty state
        self._empty_label = QLabel("No macros yet.\nGenerate one using the prompt above.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px; line-height: 1.6;")
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

    def refresh(self):
        # Clear existing cards
        for card in self._cards.values():
            self._list_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        macros = self.db.list_macros()
        count = len(macros)
        self._count_label.setText(f"{count} macro{'s' if count != 1 else ''}")

        if count == 0:
            self._empty_label.show()
        else:
            self._empty_label.hide()
            for macro in macros:
                card = MacroCard(macro)
                card.run_clicked.connect(self.run_macro.emit)
                card.edit_clicked.connect(self.edit_macro.emit)
                card.delete_clicked.connect(self._confirm_delete)
                pos = self._list_layout.count() - 1
                self._list_layout.insertWidget(pos, card)
                self._cards[macro.id] = card

    def _confirm_delete(self, macro: Macro):
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Macro")
        msg.setText(f'Delete "{macro.name}"?')
        msg.setInformativeText("This cannot be undone.")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setStyleSheet(f"""
            QMessageBox {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_primary']};
            }}
        """)
        if msg.exec() == QMessageBox.Yes:
            self.db.delete_macro(macro.id)
            self.refresh()
