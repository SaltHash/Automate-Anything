"""
Setup Dialog - API key configuration on first launch
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap

from core.config import Config
from core.api_client import GroqClient, AVAILABLE_MODELS
from ui.theme import COLORS


class ValidateThread(QThread):
    result = Signal(bool, str)

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        client = GroqClient(self.api_key)
        valid, message = client.validate_key()
        if valid:
            self.result.emit(True, "")
        else:
            self.result.emit(False, message or "Invalid API key. Please check and try again.")


class SetupDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Welcome to Automate Anything")
        self.setFixedSize(520, 480)
        self.setModal(True)
        self._api_key_visible = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(0)

        # Logo / title area
        title = QLabel("Automate Anything")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {COLORS['text_primary']}; margin-bottom: 6px;")
        layout.addWidget(title)

        subtitle = QLabel("AI-powered desktop automation")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px; margin-bottom: 36px;")
        layout.addWidget(subtitle)

        # Card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(16)

        # API Key section
        api_label = QLabel("Groq API Key")
        api_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; border: none; background: transparent;")
        card_layout.addWidget(api_label)

        api_input_row = QHBoxLayout()
        api_input_row.setSpacing(8)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter Groq API key")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setText(self.config.get_api_key())
        self.api_input.setFixedHeight(44)
        api_input_row.addWidget(self.api_input, stretch=1)

        self.toggle_visibility_btn = QPushButton("View")
        self.toggle_visibility_btn.setProperty("secondary", True)
        self.toggle_visibility_btn.setFixedHeight(44)
        self.toggle_visibility_btn.setFixedWidth(72)
        self.toggle_visibility_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_visibility_btn.clicked.connect(self._toggle_api_visibility)
        self.toggle_visibility_btn.style().unpolish(self.toggle_visibility_btn)
        self.toggle_visibility_btn.style().polish(self.toggle_visibility_btn)
        api_input_row.addWidget(self.toggle_visibility_btn)

        card_layout.addLayout(api_input_row)

        hint = QLabel("Get your free API key at console.groq.com")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; border: none; background: transparent;")
        card_layout.addWidget(hint)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']}; border: none; background: {COLORS['border']}; max-height: 1px;")
        card_layout.addWidget(sep)

        # Model selection
        model_label = QLabel("Model")
        model_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; border: none; background: transparent;")
        card_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        for m in AVAILABLE_MODELS:
            self.model_combo.addItem(m, m)

        current = self.config.get_model()
        idx = self.model_combo.findData(current)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.setFixedHeight(40)
        card_layout.addWidget(self.model_combo)

        layout.addWidget(card)
        layout.addSpacing(24)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
        layout.addWidget(self.status_label)

        layout.addSpacing(8)

        # Save button
        self.save_btn = QPushButton("Save & Continue")
        self.save_btn.setFixedHeight(44)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

        layout.addStretch()

    def _toggle_api_visibility(self):
        self._api_key_visible = not self._api_key_visible
        if self._api_key_visible:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_visibility_btn.setText("Hide")
        else:
            self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_visibility_btn.setText("View")

    def _save(self):
        key = self.api_input.text().strip()
        if not key:
            self.status_label.setText("Please enter your API key.")
            return

        self.save_btn.setText("Validating...")
        self.save_btn.setEnabled(False)
        self.status_label.setText("")

        self._thread = ValidateThread(key)
        self._thread.result.connect(self._on_validate)
        self._thread.start()

    def _on_validate(self, valid: bool, error: str):
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save & Continue")

        if valid:
            self.config.set_api_key(self.api_input.text().strip())
            self.config.set_model(self.model_combo.currentData())
            self.accept()
        else:
            self.status_label.setText(error or "Validation failed.")
            self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
