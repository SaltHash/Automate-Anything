"""
Automation Engine - OpenCV image matching + PyAutoGUI execution
"""
import time
import base64
import tempfile
import os
import threading
from typing import Callable, Optional, Tuple, List
from dataclasses import dataclass

import pyautogui
import cv2
import numpy as np
from PIL import ImageGrab

from core.storage import Macro, MacroAction


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


@dataclass
class StepResult:
    action_index: int
    action_type: str
    success: bool
    message: str
    duration: float = 0.0


class ImageMatchError(Exception):
    pass


class AutomationEngine:
    """Executes macros using image recognition and input simulation."""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback or (lambda msg: None)
        self._stop_flag = threading.Event()

    def stop(self):
        self._stop_flag.set()

    def _log(self, msg: str):
        self.log_callback(msg)

    def capture_screen(self) -> np.ndarray:
        """Capture the full screen as an OpenCV BGR image."""
        img = ImageGrab.grab()
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def find_image_on_screen(
        self,
        template_b64: str,
        confidence: float = 0.8,
    ) -> Optional[Tuple[int, int]]:
        """
        Find a template image on the current screen.
        Returns (center_x, center_y) or None if not found.
        """
        # Decode template
        img_data = base64.b64decode(template_b64)
        nparr = np.frombuffer(img_data, np.uint8)
        template = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if template is None:
            raise ImageMatchError("Invalid template image data.")

        screen = self.capture_screen()

        # Multi-scale matching for robustness
        best_val = 0.0
        best_loc = None
        th, tw = template.shape[:2]

        for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
            scaled_w = int(tw * scale)
            scaled_h = int(th * scale)
            if scaled_w < 10 or scaled_h < 10:
                continue
            scaled = cv2.resize(template, (scaled_w, scaled_h))

            if screen.shape[0] < scaled_h or screen.shape[1] < scaled_w:
                continue

            result = cv2.matchTemplate(screen, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_val:
                best_val = max_val
                best_loc = (
                    max_loc[0] + scaled_w // 2,
                    max_loc[1] + scaled_h // 2,
                )

        if best_val >= confidence and best_loc is not None:
            return best_loc
        return None

    def execute_macro(
        self,
        macro: Macro,
        step_callback: Optional[Callable[[StepResult], None]] = None,
    ) -> List[StepResult]:
        """Execute all actions in a macro. Returns list of step results."""
        self._stop_flag.clear()
        results = []

        # Small delay before starting
        time.sleep(0.5)

        for i, action in enumerate(macro.actions):
            if self._stop_flag.is_set():
                self._log("⏹ Execution stopped by user.")
                break

            start = time.time()
            result = self._execute_action(i, action)
            result.duration = time.time() - start

            results.append(result)
            if step_callback:
                step_callback(result)

            if not result.success:
                self._log(f"❌ Step {i+1} failed: {result.message}")
                # Continue unless it's a critical failure
                # Future: add conditional branching here

        return results

    def _execute_action(self, index: int, action: MacroAction) -> StepResult:
        p = action.params
        atype = action.type

        try:
            if atype == "click_image":
                return self._do_click_image(index, p)
            elif atype == "type_text":
                return self._do_type_text(index, p)
            elif atype == "wait":
                return self._do_wait(index, p)
            elif atype == "scroll":
                return self._do_scroll(index, p)
            elif atype == "key_press":
                return self._do_key_press(index, p)
            elif atype == "screenshot_capture":
                return self._do_screenshot(index, p)
            else:
                return StepResult(index, atype, False, f"Unknown action type: {atype}")
        except Exception as e:
            return StepResult(index, atype, False, str(e))

    def _do_click_image(self, idx: int, p: dict) -> StepResult:
        desc = p.get("description", "element")
        confidence = float(p.get("confidence", 0.8))
        retry_count = int(p.get("retry_count", 3))
        retry_delay = float(p.get("retry_delay", 1.0))
        fallback = p.get("fallback_coords")  # [x, y] or None
        image_b64 = p.get("image_b64", "")

        if not image_b64:
            # No image captured yet — this action needs user to capture it
            # In a real run, we skip with a warning
            msg = f"No image captured for '{desc}'. Please capture the element first."
            self._log(f"⚠️  {msg}")
            return StepResult(idx, "click_image", False, msg)

        for attempt in range(retry_count):
            if self._stop_flag.is_set():
                return StepResult(idx, "click_image", False, "Stopped")

            self._log(f"🔍 Looking for '{desc}' (attempt {attempt+1}/{retry_count})...")
            loc = self.find_image_on_screen(image_b64, confidence)

            if loc:
                x, y = loc
                pyautogui.moveTo(x, y, duration=0.2)
                pyautogui.click()
                self._log(f"✅ Clicked '{desc}' at ({x}, {y})")
                return StepResult(idx, "click_image", True, f"Clicked '{desc}' at ({x}, {y})")

            if attempt < retry_count - 1:
                self._log(f"  Not found, retrying in {retry_delay}s...")
                time.sleep(retry_delay)

        # Fallback to coordinates
        if fallback and len(fallback) == 2:
            x, y = fallback
            self._log(f"⚠️  Image not found, using fallback coords ({x}, {y})")
            pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.click()
            return StepResult(idx, "click_image", True, f"Clicked fallback coords ({x}, {y})")

        return StepResult(idx, "click_image", False, f"Could not find '{desc}' on screen")

    def _do_type_text(self, idx: int, p: dict) -> StepResult:
        text = p.get("text", "")
        delay = float(p.get("delay_between_keys", 0.05))
        self._log(f"⌨️  Typing: {text[:40]}{'...' if len(text) > 40 else ''}")
        pyautogui.write(text, interval=delay)
        return StepResult(idx, "type_text", True, f"Typed {len(text)} characters")

    def _do_wait(self, idx: int, p: dict) -> StepResult:
        seconds = float(p.get("seconds", 1.0))
        desc = p.get("description", "")
        self._log(f"⏳ Waiting {seconds}s{f' — {desc}' if desc else ''}...")

        # Interruptible wait
        end = time.time() + seconds
        while time.time() < end:
            if self._stop_flag.is_set():
                return StepResult(idx, "wait", False, "Stopped")
            time.sleep(0.1)

        return StepResult(idx, "wait", True, f"Waited {seconds}s")

    def _do_scroll(self, idx: int, p: dict) -> StepResult:
        direction = p.get("direction", "down")
        amount = int(p.get("amount", 3))
        x = p.get("x")
        y = p.get("y")

        clicks = amount if direction == "up" else -amount

        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks)

        self._log(f"🖱️  Scrolled {direction} {amount} clicks")
        return StepResult(idx, "scroll", True, f"Scrolled {direction} {amount} clicks")

    def _do_key_press(self, idx: int, p: dict) -> StepResult:
        keys = p.get("keys", [])
        desc = p.get("description", "")
        if not keys:
            return StepResult(idx, "key_press", False, "No keys specified")

        key_str = "+".join(keys)
        self._log(f"⌨️  Key press: {key_str}{f' ({desc})' if desc else ''}")

        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)

        return StepResult(idx, "key_press", True, f"Pressed {key_str}")

    def _do_screenshot(self, idx: int, p: dict) -> StepResult:
        desc = p.get("description", "screenshot")
        screen = self.capture_screen()
        self._log(f"📸 Screenshot captured ({desc})")
        return StepResult(idx, "screenshot_capture", True, f"Screenshot taken")


def capture_region_b64(x: int, y: int, w: int, h: int) -> str:
    """Capture a screen region and return as base64 PNG."""
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    _, buf = cv2.imencode(".png", arr)
    return base64.b64encode(buf.tobytes()).decode("utf-8")
