"""
Main Window - Primary application interface
"""
import time

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSplitter, QFrame, QScrollArea,
    QTextEdit, QProgressBar, QComboBox, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QAction

from core.config import Config
from core.storage import Database, Macro
from core.api_client import GroqClient, AVAILABLE_MODELS
from core.engine import AutomationEngine
from ui.theme import COLORS, STYLESHEET
from ui.setup_dialog import SetupDialog
from ui.macro_list import MacroListPanel
from ui.macro_editor import MacroEditorDialog


PLACEHOLDER_TEXT = "Prompt suggestions"


# ─── Background Workers ───────────────────────────────────────────────────────

class GenerateThread(QThread):
    progress = Signal(str)
    finished = Signal(object)  # Macro or None
    error = Signal(str)

    def __init__(self, client: GroqClient, prompt: str):
        super().__init__()
        self.client = client
        self.prompt = prompt

    def run(self):
        try:
            macro = self.client.generate_macro(self.prompt, self.progress.emit)
            self.finished.emit(macro)
        except Exception as e:
            self.error.emit(str(e))


class RunThread(QThread):
    step_done = Signal(object)  # StepResult
    log = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, engine: AutomationEngine, macro: Macro):
        super().__init__()
        self.engine = engine
        self.macro = macro

    def run(self):
        try:
            results = self.engine.execute_macro(self.macro, self.step_done.emit)
            success = all(r.success for r in results)
            msg = f"Completed {len(results)} steps"
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))


# ─── Prompt Panel ─────────────────────────────────────────────────────────────

class PromptPanel(QWidget):
    generate_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 32)
        layout.setSpacing(0)

        # App title
        title = QLabel("Automate Anything")
        title.setAlignment(Qt.AlignCenter)
        f = QFont()
        f.setPointSize(28)
        f.setWeight(QFont.Weight.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, -0.5)
        title.setFont(f)
        title.setStyleSheet(f"color: {COLORS['text_primary']}; margin-bottom: 8px;")
        layout.addWidget(title)

        tagline = QLabel("Describe what you want to automate")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px; margin-bottom: 40px;")
        layout.addWidget(tagline)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.prompt_input = QLineEdit()
        self.prompt_input.setFixedHeight(52)
        self.prompt_input.setPlaceholderText(PLACEHOLDER_TEXT)
        self.prompt_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_card']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 12px;
                padding: 0 20px;
                color: {COLORS['text_primary']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['border_focus']};
                background-color: {COLORS['bg_input']};
            }}
        """)
        self.prompt_input.returnPressed.connect(self._submit)
        input_row.addWidget(self.prompt_input, stretch=1)

        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setFixedHeight(52)
        self.generate_btn.setFixedWidth(110)
        self.generate_btn.setCursor(Qt.PointingHandCursor)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
            QPushButton:disabled {{ background-color: {COLORS['bg_card']}; color: {COLORS['text_muted']}; }}
        """)
        self.generate_btn.clicked.connect(self._submit)
        input_row.addWidget(self.generate_btn)

        layout.addLayout(input_row)
        layout.addSpacing(16)

        # Status / progress area
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background: {COLORS['border']}; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {COLORS['accent']}; border-radius: 1px; }}
        """)
        layout.addWidget(self.progress_bar)

        layout.addStretch()

    def _submit(self):
        text = self.prompt_input.text().strip()
        if text:
            self.generate_requested.emit(text)

    def set_loading(self, loading: bool, msg: str = ""):
        self.generate_btn.setEnabled(not loading)
        self.prompt_input.setEnabled(not loading)
        self.progress_bar.setVisible(loading)
        self.status_label.setText(msg)
        if not loading:
            self.generate_btn.setText("Generate")
        else:
            self.generate_btn.setText("···")

    def update_status(self, msg: str):
        self.status_label.setText(msg)


# ─── Macro Preview Panel ──────────────────────────────────────────────────────

class MacroPreviewPanel(QWidget):
    run_requested = Signal(object)
    save_requested = Signal(object)
    discard_requested = Signal()

    def __init__(self):
        super().__init__()
        self.macro = None
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 24)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Generated Macro")
        f = QFont()
        f.setPointSize(14)
        f.setWeight(QFont.Weight.DemiBold)
        title.setFont(f)
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        header.addWidget(title)
        header.addStretch()

        self.macro_name_label = QLabel("")
        self.macro_name_label.setStyleSheet(f"""
            color: {COLORS['accent']};
            background: {COLORS['accent_dim']};
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 600;
        """)
        header.addWidget(self.macro_name_label)
        layout.addLayout(header)

        # Summary
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(self.summary_label)

        # Steps scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(280)

        self._steps_widget = QWidget()
        self._steps_layout = QVBoxLayout(self._steps_widget)
        self._steps_layout.setContentsMargins(0, 0, 0, 0)
        self._steps_layout.setSpacing(4)
        self._steps_layout.addStretch()

        scroll.setWidget(self._steps_widget)
        layout.addWidget(scroll)

        # Action row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setProperty("secondary", True)
        self.discard_btn.style().unpolish(self.discard_btn)
        self.discard_btn.style().polish(self.discard_btn)
        self.discard_btn.setCursor(Qt.PointingHandCursor)
        self.discard_btn.clicked.connect(self.discard_requested.emit)

        self.save_btn = QPushButton("Save Macro")
        self.save_btn.setProperty("secondary", True)
        self.save_btn.style().unpolish(self.save_btn)
        self.save_btn.style().polish(self.save_btn)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(lambda: self.save_requested.emit(self.macro))

        self.run_btn = QPushButton("▶  Run Macro")
        self.run_btn.setProperty("success", True)
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(lambda: self.run_requested.emit(self.macro))

        btn_row.addWidget(self.discard_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.run_btn)
        layout.addLayout(btn_row)

        # Execution log
        log_label = QLabel("Execution Log")
        log_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(120)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text_secondary']};
                font-family: 'Menlo', 'Consolas', monospace;
                font-size: 11px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.log_text)

        # Stop button (hidden by default)
        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.style().unpolish(self.stop_btn)
        self.stop_btn.style().polish(self.stop_btn)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.hide()
        layout.addWidget(self.stop_btn)

    def show_macro(self, macro: Macro):
        self.macro = macro
        self.macro_name_label.setText(macro.name)
        self.summary_label.setText(macro.summary)
        self.log_text.clear()

        # Clear old steps
        for i in reversed(range(self._steps_layout.count() - 1)):
            item = self._steps_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        # Populate steps
        ACTION_ICONS = {
            "click_image": "🖱",
            "type_text": "⌨",
            "wait": "⏳",
            "scroll": "↕",
            "key_press": "⌨",
            "screenshot_capture": "📸",
        }

        for i, action in enumerate(macro.actions):
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['bg_card']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 7px;
                }}
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 7, 10, 7)
            row_layout.setSpacing(10)

            num = QLabel(str(i + 1))
            num.setFixedWidth(20)
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
            row_layout.addWidget(num)

            icon = ACTION_ICONS.get(action.type, "•")
            desc = self._action_desc(action)
            text = QLabel(f"{icon}  {desc}")
            text.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            text.setWordWrap(True)
            row_layout.addWidget(text, stretch=1)

            pos = self._steps_layout.count() - 1
            self._steps_layout.insertWidget(pos, row)

        self.show()

    def _action_desc(self, action) -> str:
        p = action.params
        t = action.type
        if t == "type_text":
            txt = p.get("text", "")
            return f'Type "{txt[:50]}{"…" if len(txt) > 50 else ""}"'
        elif t == "wait":
            return f"Wait {p.get('seconds', 1)}s — {p.get('description', '')}"
        elif t == "scroll":
            return f"Scroll {p.get('direction', 'down')} × {p.get('amount', 3)}"
        elif t == "key_press":
            return " + ".join(p.get("keys", []))
        elif t == "click_image":
            return p.get("description", "Click element")
        elif t == "screenshot_capture":
            return p.get("description", "Capture screenshot")
        return action.type

    def append_log(self, msg: str):
        self.log_text.append(msg)

    def set_running(self, running: bool):
        self.run_btn.setEnabled(not running)
        self.save_btn.setEnabled(not running)
        self.discard_btn.setEnabled(not running)
        self.stop_btn.setVisible(running)


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, config: Config, db: Database):
        super().__init__()
        self.config = config
        self.db = db
        self._gen_thread = None
        self._run_thread = None
        self._engine = None
        self._current_macro = None

        self.setWindowTitle("Automate Anything")
        self.setMinimumSize(900, 640)
        self.resize(1100, 720)

        self.setStyleSheet(STYLESHEET)
        self._set_palette()
        self._setup_ui()
        self._setup_menu()

        # First launch: show setup if no API key
        if not self.config.has_api_key():
            QTimer.singleShot(200, self._show_setup)

    def _set_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(COLORS["bg_primary"]))
        palette.setColor(QPalette.WindowText, QColor(COLORS["text_primary"]))
        palette.setColor(QPalette.Base, QColor(COLORS["bg_input"]))
        palette.setColor(QPalette.AlternateBase, QColor(COLORS["bg_card"]))
        palette.setColor(QPalette.Text, QColor(COLORS["text_primary"]))
        palette.setColor(QPalette.Button, QColor(COLORS["bg_card"]))
        palette.setColor(QPalette.ButtonText, QColor(COLORS["text_primary"]))
        palette.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
        palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
        self.setPalette(palette)

    def _setup_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background: {COLORS['bg_primary']};")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Splitter: left = macro list, right = main area
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {COLORS['border']}; }}")

        # Left: macro list panel
        self._macro_list = MacroListPanel(self.db)
        self._macro_list.setMinimumWidth(260)
        self._macro_list.setMaximumWidth(360)
        self._macro_list.run_macro.connect(self._run_macro)
        self._macro_list.edit_macro.connect(self._edit_macro)
        splitter.addWidget(self._macro_list)

        # Right: main content
        right = QWidget()
        right.setStyleSheet(f"background: {COLORS['bg_primary']};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Toolbar
        toolbar = self._build_toolbar()
        right_layout.addWidget(toolbar)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {COLORS['border']}; border: none;")
        right_layout.addWidget(div)

        # Prompt panel
        self._prompt_panel = PromptPanel()
        self._prompt_panel.generate_requested.connect(self._generate_macro)
        right_layout.addWidget(self._prompt_panel)

        # Preview panel (hidden until macro generated)
        self._preview_panel = MacroPreviewPanel()
        self._preview_panel.run_requested.connect(self._run_macro)
        self._preview_panel.save_requested.connect(self._save_macro)
        self._preview_panel.discard_requested.connect(self._discard_macro)
        self._preview_panel.stop_btn.clicked.connect(self._stop_run)
        right_layout.addWidget(self._preview_panel)

        splitter.addWidget(right)
        splitter.setSizes([280, 820])

        root.addWidget(splitter)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet(f"background: {COLORS['bg_secondary']};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Model selector
        model_label = QLabel("Model:")
        model_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.setFixedHeight(32)
        for m in AVAILABLE_MODELS:
            self._model_combo.addItem(m, m)
        cur = self.config.get_model()
        idx = self._model_combo.findData(cur)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        self._model_combo.currentIndexChanged.connect(self._on_model_change)
        layout.addWidget(self._model_combo)

        layout.addStretch()

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setProperty("secondary", True)
        settings_btn.style().unpolish(settings_btn)
        settings_btn.style().polish(settings_btn)
        settings_btn.setFixedHeight(32)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(self._show_setup)
        layout.addWidget(settings_btn)

        return bar

    def _setup_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        settings_action = QAction("Settings & API Key", self)
        settings_action.triggered.connect(self._show_setup)
        file_menu.addAction(settings_action)

        refresh_action = QAction("Refresh Macros", self)
        refresh_action.triggered.connect(self._macro_list.refresh)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_action)

    # ── API / Generation ──────────────────────────────────────────────────────

    def _generate_macro(self, prompt: str):
        if not self.config.has_api_key():
            self._show_setup()
            return

        client = GroqClient(
            api_key=self.config.get_api_key(),
            model=self.config.get_model(),
        )

        self._prompt_panel.set_loading(True, "Connecting to Groq…")
        self._preview_panel.hide()

        self._gen_thread = GenerateThread(client, prompt)
        self._gen_thread.progress.connect(self._prompt_panel.update_status)
        self._gen_thread.finished.connect(self._on_macro_generated)
        self._gen_thread.error.connect(self._on_generate_error)
        self._gen_thread.start()

    def _on_macro_generated(self, macro: Macro):
        self._prompt_panel.set_loading(False)
        self._current_macro = macro
        self._preview_panel.show_macro(macro)
        # Auto-save
        self._save_macro(macro, silent=True)

    def _on_generate_error(self, error: str):
        self._prompt_panel.set_loading(False, f"Error: {error}")

    # ── Macro Actions ─────────────────────────────────────────────────────────

    def _save_macro(self, macro: Macro, silent: bool = False):
        saved = self.db.save_macro(macro)
        self._current_macro = saved
        self._macro_list.refresh()
        if not silent:
            self._preview_panel.append_log("✅ Macro saved.")

    def _discard_macro(self):
        self._preview_panel.hide()
        self._current_macro = None

    def _edit_macro(self, macro: Macro):
        dlg = MacroEditorDialog(macro, self)
        if dlg.exec():
            self.db.save_macro(macro)
            self._macro_list.refresh()

    def _run_macro(self, macro: Macro):
        self._preview_panel.show_macro(macro)
        self._preview_panel.append_log("▶ Starting execution…")
        self._preview_panel.set_running(True)

        self._engine = AutomationEngine(
            log_callback=self._preview_panel.append_log
        )
        self._preview_panel.stop_btn.clicked.disconnect()
        self._preview_panel.stop_btn.clicked.connect(self._stop_run)

        self._run_thread = RunThread(self._engine, macro)
        self._run_thread.log.connect(self._preview_panel.append_log)
        self._run_thread.step_done.connect(self._on_step_done)
        self._run_thread.finished.connect(lambda ok, msg: self._on_run_finished(macro, ok, msg))
        self._run_thread.start()

    def _on_step_done(self, result):
        icon = "✅" if result.success else "❌"
        self._preview_panel.append_log(
            f"{icon} Step {result.action_index + 1}: {result.message} ({result.duration:.2f}s)"
        )

    def _on_run_finished(self, macro: Macro, success: bool, msg: str):
        self._preview_panel.set_running(False)
        icon = "✅" if success else "❌"
        self._preview_panel.append_log(f"{icon} {msg}")
        self.db.log_run(macro.id, success, "" if success else msg)

    def _stop_run(self):
        if self._engine:
            self._engine.stop()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _show_setup(self):
        dlg = SetupDialog(self.config, self)
        dlg.exec()
        # Update model combo after settings change
        cur = self.config.get_model()
        idx = self._model_combo.findData(cur)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

    def _on_model_change(self, idx: int):
        model = self._model_combo.currentData()
        if model:
            self.config.set_model(model)

    def closeEvent(self, event):
        if self._run_thread and self._run_thread.isRunning():
            if self._engine:
                self._engine.stop()
            self._run_thread.wait(2000)
        self.db.close()
        event.accept()
