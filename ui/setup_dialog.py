"""
Setup Dialog - API provider and key configuration
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from core.config import Config
from core.api_client import AIClient, PROVIDER_CONFIG
from ui.theme import COLORS


class ValidateThread(QThread):
    result = Signal(bool, str)

    def __init__(self, provider: str, model: str, keys: dict[str, str]):
        super().__init__()
        self.provider = provider
        self.model = model
        self.keys = keys

    def run(self):
        client = AIClient(provider=self.provider, model=self.model, api_keys=self.keys)
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
        self.setFixedSize(620, 680)
        self.setModal(True)
        self._api_key_visible = False
        self._key_inputs = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(0)

        title = QLabel("Automate Anything")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {COLORS['text_primary']}; margin-bottom: 6px;")
        layout.addWidget(title)

        subtitle = QLabel("Choose an AI provider and add optional API keys")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px; margin-bottom: 20px;")
        layout.addWidget(subtitle)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 14px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)

        provider_row = QHBoxLayout()
        provider_label = QLabel("Active Provider")
        provider_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600;")
        provider_row.addWidget(provider_label)
        provider_row.addStretch()

        self.provider_combo = QComboBox()
        self.provider_combo.setFixedHeight(34)
        for provider, cfg in PROVIDER_CONFIG.items():
            self.provider_combo.addItem(cfg["label"], provider)
        idx = self.provider_combo.findData(self.config.get_provider())
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        provider_row.addWidget(self.provider_combo)
        card_layout.addLayout(provider_row)

        top_sep = QFrame()
        top_sep.setFrameShape(QFrame.Shape.HLine)
        top_sep.setStyleSheet(f"background: {COLORS['border']}; max-height: 1px;")
        card_layout.addWidget(top_sep)

        for provider, cfg in PROVIDER_CONFIG.items():
            label = QLabel(f"{cfg['label']} API Key (Optional)")
            label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600;")
            card_layout.addWidget(label)

            key_input = QLineEdit()
            key_input.setPlaceholderText(f"Enter {cfg['label']} API key")
            key_input.setEchoMode(QLineEdit.EchoMode.Password)
            key_input.setText(self.config.get_provider_key(provider))
            key_input.setFixedHeight(36)
            card_layout.addWidget(key_input)
            self._key_inputs[provider] = key_input

        hint = QLabel("All keys are optional, but at least one valid key is required to continue.")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; margin-top: 6px;")
        card_layout.addWidget(hint)

        controls = QHBoxLayout()
        self.toggle_visibility_btn = QPushButton("View Keys")
        self.toggle_visibility_btn.setProperty("secondary", True)
        self.toggle_visibility_btn.setFixedHeight(34)
        self.toggle_visibility_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_visibility_btn.clicked.connect(self._toggle_api_visibility)
        controls.addWidget(self.toggle_visibility_btn)
        controls.addStretch()
        card_layout.addLayout(controls)

        layout.addWidget(card)
        layout.addSpacing(18)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
        layout.addWidget(self.status_label)

        layout.addSpacing(8)

        self.save_btn = QPushButton("Save & Continue")
        self.save_btn.setFixedHeight(44)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

        layout.addStretch()

    def _toggle_api_visibility(self):
        self._api_key_visible = not self._api_key_visible
        mode = QLineEdit.EchoMode.Normal if self._api_key_visible else QLineEdit.EchoMode.Password
        for input_widget in self._key_inputs.values():
            input_widget.setEchoMode(mode)
        self.toggle_visibility_btn.setText("Hide Keys" if self._api_key_visible else "View Keys")

    def _save(self):
        keys = {provider: widget.text().strip() for provider, widget in self._key_inputs.items()}
        provider = self.provider_combo.currentData()
        model = self.config.get_model_for_provider(provider)

        if not any(keys.values()):
            self.status_label.setText("Please enter at least one API key.")
            return

        for p, key in keys.items():
            self.config.set_provider_key(p, key)
        self.config.set_provider(provider)

        if not keys.get(provider):
            self.status_label.setText(f"Saved. Add a key for {PROVIDER_CONFIG[provider]['label']} or switch provider later.")
            self.accept()
            return

        self.save_btn.setText("Validating...")
        self.save_btn.setEnabled(False)
        self.status_label.setText("")

        self._thread = ValidateThread(provider=provider, model=model, keys=keys)
        self._thread.result.connect(self._on_validate)
        self._thread.start()

    def _on_validate(self, valid: bool, error: str):
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save & Continue")

        if valid:
            self.accept()
        else:
            self.status_label.setText(error or "Validation failed.")
            self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
