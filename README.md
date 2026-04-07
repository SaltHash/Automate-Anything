# Automate Anything

AI-powered desktop automation — describe what you want automated in plain English, and the app generates and executes a structured macro using image recognition.

---

## Features

- **Natural language → macro**: Describe any task; your selected AI provider converts it to structured automation steps
- **Image-based targeting**: Finds UI elements visually using OpenCV template matching — not fragile coordinates
- **Multi-scale matching**: Handles elements at different zoom levels
- **Retry logic**: Configurable retry count + delay per click action
- **Macro manager**: All macros auto-saved to SQLite; edit, run, or delete in-app
- **Live execution log**: Real-time feedback during macro execution
- **Non-blocking UI**: All heavy work runs in background threads
- **Graceful error handling**: Invalid keys, match failures, and missing elements handled cleanly

---

## Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- pip

### 2. Install dependencies

```bash
cd automate_anything
pip install -r requirements.txt
```

> **macOS note**: PyAutoGUI requires Accessibility permissions. Go to:
> System Preferences → Security & Privacy → Accessibility → add your Terminal.

> **Linux note**: You may need `python3-xlib` or `xdotool`:
> ```bash
> sudo apt install python3-xlib
> ```

### 3. Add one or more provider API keys

The app supports multiple providers (Groq, OpenAI, Anthropic, Google Gemini, OpenRouter).
All keys are optional, but you need at least one key to continue.

### 4. Run the app

```bash
python main.py
```

On first launch, you'll be prompted to choose a provider and optionally add keys for each provider. Keys are stored locally (base64-obfuscated) in `~/.automate_anything/config.json` with restricted file permissions.

---

## How to Use

### Generating a Macro

1. Type a task description in the prompt field, e.g.:
   - *"Open the browser and search for Python tutorials"*
   - *"Click the Save button and wait for the dialog"*
   - *"Select all text, copy it, and open Notepad"*
2. Press **Enter** or click **Generate**
3. Review the generated steps in the preview panel
4. Click **▶ Run Macro** or **Save Macro**

### Image Capture (for click_image steps)

For each "Click Image" step in a macro:
1. Open the macro editor (Edit button)
2. Click **📷 Capture Element** on any click_image step
3. The app hides itself — drag to select the UI element on screen
4. The screenshot is stored in the macro for matching

### Macro Manager (left panel)

- **▶ Run** — Execute the macro immediately
- **Edit** — Open the step editor to reorder, modify, or add steps
- **Delete** — Permanently remove the macro

### Settings

Click **⚙ Settings** or go to File → Settings to manage provider keys, switch providers, and select provider-specific models (dropdown for most providers, free-text model for OpenRouter).

---

## Architecture

```
automate_anything/
├── main.py                  # Entry point
├── requirements.txt
├── core/
│   ├── config.py            # Secure config storage
│   ├── storage.py           # SQLite ORM (macros, run history)
│   ├── api_client.py        # Groq API client + macro parser
│   └── engine.py            # OpenCV matching + PyAutoGUI execution
└── ui/
    ├── theme.py             # Colors + Qt stylesheet
    ├── main_window.py       # Primary application window
    ├── setup_dialog.py      # API key setup / settings dialog
    ├── macro_list.py        # Left-panel macro manager
    └── macro_editor.py      # Step editor + screen capture overlay
```

### Data Flow

```
User prompt
    → GenerateThread (background)
    → GroqClient.generate_macro()
    → Groq API (llama-3.3-70b-versatile)
    → Parsed Macro object
    → Auto-saved to SQLite
    → Preview panel shown

Run macro
    → RunThread (background)
    → AutomationEngine.execute_macro()
    → Per-step: OpenCV template match → PyAutoGUI click/type/etc.
    → Live log updates in UI
    → Result logged to run_history table
```

---

## Supported Action Types

| Type | Description |
|------|-------------|
| `click_image` | Find element via OpenCV, click it. Retries N times, optional coordinate fallback. |
| `type_text` | Type a string with configurable keystroke delay |
| `wait` | Interruptible sleep (checks stop flag every 100ms) |
| `scroll` | Scroll up/down/left/right by N clicks at optional position |
| `key_press` | Single key or hotkey combo (e.g. Ctrl+C) |
| `screenshot_capture` | Capture the screen (for verification/logging) |

---

## Data Storage

All data is stored locally:
- **Config**: `~/.automate_anything/config.json` (permissions: 600)
- **Database**: `~/.automate_anything/macros.db` (SQLite)
  - `macros` table: id, name, prompt, summary, actions (JSON), timestamps
  - `run_history` table: macro_id, ran_at, success, error_msg

---

## Troubleshooting

**"Invalid API key"** — Check your key at console.groq.com. Make sure it starts with `gsk_`.

**PyAutoGUI fails on macOS** — Grant Accessibility permissions to Terminal in System Preferences.

**OpenCV not finding element** — Lower the confidence threshold in the macro editor, or re-capture the element at the correct zoom level.

**Macro generation returns invalid JSON** — Try a different model (llama-3.1-8b-instant is faster but less accurate; llama-3.3-70b is more reliable).

**PyAutoGUI FAILSAFE triggered** — Move mouse to corner of screen causes a safety stop. This is intentional. Re-run the macro.
