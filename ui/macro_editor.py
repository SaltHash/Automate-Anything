"""
Macro Editor Dialog - Edit macro steps, capture images, manage actions
"""
import base64
import time

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QFrame, QComboBox,
    QTextEdit, QSpinBox, QDoubleSpinBox, QApplication, QRubberBand,
    QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QSize, QPoint, QTimer
from PySide6.QtGui import QFont, QPixmap, QImage, QPainter, QColor, QScreen

from core.storage import Macro, MacroAction
from core.engine import capture_region_b64
from ui.theme import COLORS


ACTION_TYPES = [
    ("click_image", "🖱  Click Image"),
    ("type_text", "⌨  Type Text"),
    ("wait", "⏳  Wait"),
    ("scroll", "↕  Scroll"),
    ("key_press", "⌨  Key Press"),
    ("screenshot_capture", "📸  Screenshot"),
]


class ScreenCaptureOverlay(QWidget):
    """Full-screen overlay for selecting a region to capture."""
    region_selected = Signal(int, int, int, int)  # x, y, w, h
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self._start = None
        self._current = None
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)

        # Grab full screen
        screen = QApplication.primaryScreen()
        geo = screen.geometry()
        self.setGeometry(geo)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.pos()
            self._rubber.setGeometry(QRect(self._start, QSize()))
            self._rubber.show()

    def mouseMoveEvent(self, e):
        if self._start:
            self._rubber.setGeometry(QRect(self._start, e.pos()).normalized())
            self._current = e.pos()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._start:
            rect = QRect(self._start, e.pos()).normalized()
            self._rubber.hide()
            self.hide()
            if rect.width() > 10 and rect.height() > 10:
                self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
            else:
                self.cancelled.emit()
            self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))


class ActionWidget(QFrame):
    """Widget for displaying and editing a single macro action."""
    delete_requested = Signal(object)
    move_up = Signal(object)
    move_down = Signal(object)

    def __init__(self, action: MacroAction, index: int):
        super().__init__()
        self.action = action
        self.index = index
        self._build()

    def _build(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                margin: 2px 0;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header row
        header = QHBoxLayout()

        # Step number badge
        num_label = QLabel(f"{self.index + 1}")
        num_label.setFixedSize(24, 24)
        num_label.setAlignment(Qt.AlignCenter)
        num_label.setStyleSheet(f"""
            background-color: {COLORS['accent_dim']};
            color: {COLORS['accent']};
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
        """)
        header.addWidget(num_label)

        # Action type label
        type_name = dict(ACTION_TYPES).get(self.action.type, self.action.type)
        type_label = QLabel(type_name)
        type_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 600; font-size: 13px;")
        header.addWidget(type_label)

        header.addStretch()

        # Action buttons
        for icon, callback in [("↑", lambda: self.move_up.emit(self)), ("↓", lambda: self.move_down.emit(self)), ("✕", lambda: self.delete_requested.emit(self))]:
            btn = QPushButton(icon)
            btn.setFixedSize(26, 26)
            btn.setProperty("secondary", True)
            btn.clicked.connect(callback)
            btn.setCursor(Qt.PointingHandCursor)
            if icon == "✕":
                btn.setProperty("danger", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            header.addWidget(btn)

        layout.addLayout(header)

        # Params summary
        summary = self._build_summary()
        if summary:
            summary_label = QLabel(summary)
            summary_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            summary_label.setWordWrap(True)
            layout.addWidget(summary_label)

        # Image preview for click_image
        if self.action.type == "click_image":
            self._build_image_section(layout)

    def _build_summary(self) -> str:
        p = self.action.params
        t = self.action.type
        if t == "type_text":
            text = p.get("text", "")
            return f'"{text[:60]}{"..." if len(text) > 60 else ""}"'
        elif t == "wait":
            return f"Wait {p.get('seconds', 1)}s — {p.get('description', '')}"
        elif t == "scroll":
            return f"Scroll {p.get('direction', 'down')} × {p.get('amount', 3)}"
        elif t == "key_press":
            return " + ".join(p.get("keys", []))
        elif t == "click_image":
            return p.get("description", "Element")
        elif t == "screenshot_capture":
            return p.get("description", "Capture screen")
        return ""

    def _build_image_section(self, layout: QVBoxLayout):
        img_b64 = self.action.params.get("image_b64", "")

        img_row = QHBoxLayout()

        if img_b64:
            # Show thumbnail
            img_data = base64.b64decode(img_b64)
            qimg = QImage.fromData(img_data)
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg).scaledToHeight(48, Qt.SmoothTransformation)
                thumb = QLabel()
                thumb.setPixmap(pix)
                thumb.setStyleSheet(f"border: 1px solid {COLORS['border']}; border-radius: 4px;")
                img_row.addWidget(thumb)

        capture_btn = QPushButton("📷 Capture Element" if not img_b64 else "♻ Re-capture")
        capture_btn.setProperty("secondary", True)
        capture_btn.style().unpolish(capture_btn)
        capture_btn.style().polish(capture_btn)
        capture_btn.setCursor(Qt.PointingHandCursor)
        capture_btn.clicked.connect(lambda: self._capture_image(capture_btn, layout))
        img_row.addWidget(capture_btn)
        img_row.addStretch()

        layout.addLayout(img_row)

        conf = self.action.params.get("confidence", 0.8)
        conf_label = QLabel(f"Confidence: {conf:.0%}  |  Retries: {self.action.params.get('retry_count', 3)}")
        conf_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(conf_label)

    def _capture_image(self, btn: QPushButton, layout: QVBoxLayout):
        """Hide window and let user select a screen region."""
        window = self.window()
        window.hide()
        QApplication.processEvents()
        time.sleep(0.4)  # Let window fully hide

        self._overlay = ScreenCaptureOverlay()
        self._overlay.region_selected.connect(lambda x, y, w, h: self._on_region(x, y, w, h, btn, window))
        self._overlay.cancelled.connect(lambda: window.show())
        self._overlay.show()

    def _on_region(self, x, y, w, h, btn, window):
        b64 = capture_region_b64(x, y, w, h)
        self.action.params["image_b64"] = b64
        window.show()
        # Rebuild thumbnail
        btn.setText("♻ Re-capture")


class MacroEditorDialog(QDialog):
    def __init__(self, macro: Macro, parent=None):
        super().__init__(parent)
        self.macro = macro
        self.setWindowTitle(f"Edit Macro — {macro.name}")
        self.setMinimumSize(600, 700)
        self.resize(640, 720)
        self._action_widgets = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Name field
        name_label = QLabel("Macro Name")
        name_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600;")
        layout.addWidget(name_label)

        self.name_edit = QLineEdit(self.macro.name)
        self.name_edit.setFixedHeight(40)
        layout.addWidget(self.name_edit)

        # Summary
        summary_label = QLabel("Summary")
        summary_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600;")
        layout.addWidget(summary_label)

        self.summary_edit = QLineEdit(self.macro.summary)
        self.summary_edit.setFixedHeight(40)
        layout.addWidget(self.summary_edit)

        # Actions header
        actions_header = QHBoxLayout()
        actions_lbl = QLabel("Actions")
        actions_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600;")
        actions_header.addWidget(actions_lbl)
        actions_header.addStretch()

        add_btn = QPushButton("+ Add Step")
        add_btn.setProperty("secondary", True)
        add_btn.style().unpolish(add_btn)
        add_btn.style().polish(add_btn)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_action)
        actions_header.addWidget(add_btn)
        layout.addLayout(actions_header)

        # Scrollable actions list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._actions_container = QWidget()
        self._actions_layout = QVBoxLayout(self._actions_container)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(6)
        self._actions_layout.addStretch()

        scroll.setWidget(self._actions_container)
        layout.addWidget(scroll, stretch=1)

        # Populate existing actions
        for action in self.macro.actions:
            self._insert_action_widget(action)

        # Footer buttons
        footer = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("secondary", True)
        cancel_btn.style().unpolish(cancel_btn)
        cancel_btn.style().polish(cancel_btn)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Changes")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save)

        footer.addWidget(cancel_btn)
        footer.addStretch()
        footer.addWidget(save_btn)
        layout.addLayout(footer)

    def _insert_action_widget(self, action: MacroAction):
        idx = len(self._action_widgets)
        w = ActionWidget(action, idx)
        w.delete_requested.connect(self._remove_action)
        w.move_up.connect(self._move_up)
        w.move_down.connect(self._move_down)
        # Insert before stretch
        pos = self._actions_layout.count() - 1
        self._actions_layout.insertWidget(pos, w)
        self._action_widgets.append(w)

    def _add_action(self):
        action = MacroAction(type="wait", params={"seconds": 1.0, "description": "Wait"})
        self.macro.actions.append(action)
        self._insert_action_widget(action)

    def _remove_action(self, widget: ActionWidget):
        self._actions_layout.removeWidget(widget)
        widget.deleteLater()
        self._action_widgets.remove(widget)
        # Sync macro actions
        self.macro.actions = [w.action for w in self._action_widgets]

    def _move_up(self, widget: ActionWidget):
        idx = self._action_widgets.index(widget)
        if idx == 0:
            return
        self._action_widgets[idx], self._action_widgets[idx - 1] = (
            self._action_widgets[idx - 1], self._action_widgets[idx]
        )
        self._rebuild_layout()

    def _move_down(self, widget: ActionWidget):
        idx = self._action_widgets.index(widget)
        if idx >= len(self._action_widgets) - 1:
            return
        self._action_widgets[idx], self._action_widgets[idx + 1] = (
            self._action_widgets[idx + 1], self._action_widgets[idx]
        )
        self._rebuild_layout()

    def _rebuild_layout(self):
        for w in self._action_widgets:
            self._actions_layout.removeWidget(w)
        for w in self._action_widgets:
            pos = self._actions_layout.count() - 1
            self._actions_layout.insertWidget(pos, w)
        self.macro.actions = [w.action for w in self._action_widgets]

    def _save(self):
        self.macro.name = self.name_edit.text().strip() or self.macro.name
        self.macro.summary = self.summary_edit.text().strip()
        self.macro.actions = [w.action for w in self._action_widgets]
        self.accept()
