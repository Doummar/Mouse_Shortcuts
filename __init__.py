# Mouse Answer
# Created by Adel Aitah
# GitHub: https://github.com/Doummar/Mouse-answer
# Copyright (c) 2026 Adel Aitah — All rights reserved
"""
Mouse Answer — Anki review shortcuts addon
Right click, middle click, scroll wheel, and extra mouse buttons for
rating cards, context-aware per question/answer side, optional toggle key.
"""
import webbrowser
from time import monotonic
from aqt import mw, gui_hooks
from aqt.qt import *

ADDON_NAME    = "Mouse Answer"
ADDON_AUTHOR  = "Adel Aitah"
ADDON_VERSION = "1.2.2"
ADDON_URL     = "https://github.com/Doummar/Mouse-answer"

VERSION    = "1.2.2"
ISSUE_URL  = "https://github.com/Doummar/Mouse-answer/issues"
_DEFAULT_TOGGLE = {"type": "key", "key_int": 189, "display": "½"}

DEFAULT_CONFIG = {
    "toggle_binding":       _DEFAULT_TOGGLE,
    "addon_active":         True,
    "show_answer_feedback": False,
    "right_click_question":        "show_answer",
    "right_click_answer":          "good",
    "right_double_click_question": "do_nothing",
    "right_double_click_answer":   "do_nothing",
    "middle_click_question":       "do_nothing",
    "middle_click_answer":         "do_nothing",
    "scroll_up_question":          "do_nothing",
    "scroll_up_answer":            "easy",
    "scroll_down_question":        "do_nothing",
    "scroll_down_answer":          "again",
    "extra1_click_question":       "do_nothing",
    "extra1_click_answer":         "do_nothing",
    "extra2_click_question":       "do_nothing",
    "extra2_click_answer":         "do_nothing",
}

ACTIONS = [
    ("do_nothing",  "— Do nothing —"),
    ("show_answer", "Show Answer"),
    ("again",       "Again"),
    ("hard",        "Hard"),
    ("good",        "Good"),
    ("easy",        "Easy"),
]

_FEEDBACK_COLORS = {
    "again": "#e55353",
    "hard":  "#999999",
    "good":  "#4aae6e",
    "easy":  "#4a90d9",
}

# Hoisted out of do_action(): unlike tuple literals, a dict literal is
# rebuilt from scratch on every function call in CPython, and do_action runs
# on every rating. A module-level constant is built once at import time.
_EASE_MAP = {"again": 1, "hard": 2, "good": 3, "easy": 4}

_config_cache    = None
_installed       = False
_feedback_widget = None
_debounce_key    = None   # (action, reviewer-state) tuple of last scheduled event
_debounce_ms     = 0      # monotonic ms timestamp of last scheduled event


# ── Core helpers ───────────────────────────────────────────────────────────────

def get_config():
    global _config_cache
    if _config_cache is None:
        raw = mw.addonManager.getConfig(__name__) or {}
        merged = {**DEFAULT_CONFIG, **raw}
        if "toggle_binding" not in raw:
            merged["toggle_binding"] = _DEFAULT_TOGGLE.copy()
        _config_cache = merged
    return _config_cache


def save_config(cfg):
    global _config_cache
    _config_cache = cfg
    mw.addonManager.writeConfig(__name__, cfg)


def is_dark_mode():
    try:
        from aqt.theme import theme_manager
        return bool(theme_manager.night_mode)
    except Exception:
        pass
    return mw.app.palette().color(QPalette.ColorRole.Window).lightness() < 128


# ── Deferred action callbacks ─────────────────────────────────────────────────
# BUG FIX: previously do_action called _answerCard synchronously inside the Qt
# event filter. Calling Anki's card-transition code while Qt is still dispatching
# the mouse event creates a race with QWebEngineView's renderer: the next card
# starts loading, but any subsequent handling of the same event by Chromium
# (see XButton fix in eventFilter) can navigate the WebView backward, leaving
# the card blank (text/images gone, audio still plays because Anki's audio system
# is independent of the WebView). Deferring via singleShot(0) lets Qt finish
# event dispatch fully before the card transition begins.

def _make_answer_cb(ease):
    """Return a zero-argument callable that safely answers the current card."""
    def _cb():
        if mw.state != "review":
            return
        reviewer = getattr(mw, "reviewer", None)
        if reviewer is None or getattr(reviewer, "state", None) != "answer":
            return
        for name in ("_answerCard", "_answer", "answer_card"):
            fn = getattr(reviewer, name, None)
            if callable(fn):
                try:
                    fn(ease)
                    return
                except Exception as exc:
                    print(f"MouseAnswer: {name}({ease}) raised {exc!r}")
    return _cb


def _make_show_answer_cb():
    """Return a zero-argument callable that safely reveals the answer."""
    def _cb():
        if mw.state != "review":
            return
        reviewer = getattr(mw, "reviewer", None)
        if reviewer is None or getattr(reviewer, "state", None) != "question":
            return
        for name in ("_showAnswer", "show_answer"):
            fn = getattr(reviewer, name, None)
            if callable(fn):
                try:
                    fn()
                    return
                except Exception as exc:
                    print(f"MouseAnswer: {name}() raised {exc!r}")
    return _cb


def do_action(action, reviewer):
    """Validate, debounce, and schedule a configured action.

    Returns True  → event should be consumed (action will fire, or was
                    a duplicate and is deliberately swallowed).
    Returns False → event may pass through to Qt / the WebView.
    """
    global _debounce_key, _debounce_ms
    if not action or action == "do_nothing":
        return False
    state = getattr(reviewer, "state", None)

    # ── Debounce ──────────────────────────────────────────────────────────────
    # BUG FIX: some mice (or Qt's internal routing through QWebEngineView child
    # widgets) deliver multiple MouseButtonPress events per physical click.
    # Identical (action, reviewer-state) pairs within 250 ms are consumed but
    # not executed, preventing double-answers.
    now_ms = int(monotonic() * 1000)
    key    = (action, state)
    if key == _debounce_key and now_ms - _debounce_ms < 250:
        return True   # consume the duplicate; don't double-answer
    _debounce_key = key
    _debounce_ms  = now_ms

    # ── show_answer ───────────────────────────────────────────────────────────
    if action == "show_answer":
        if state != "question":
            return False
        if not any(callable(getattr(reviewer, n, None))
                   for n in ("_showAnswer", "show_answer")):
            return False
        QTimer.singleShot(0, _make_show_answer_cb())
        return True

    # ── rate card ─────────────────────────────────────────────────────────────
    ease = _EASE_MAP.get(action)
    if ease is not None and state == "answer":
        if not any(callable(getattr(reviewer, n, None))
                   for n in ("_answerCard", "_answer", "answer_card")):
            return False
        QTimer.singleShot(0, _make_answer_cb(ease))
        return True

    return False


# ── Feedback overlay ───────────────────────────────────────────────────────────

class FeedbackWidget(QLabel):
    """Brief non-intrusive overlay showing the last action or toggle state."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def _show(self, text, color):
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: #ffffff;
                border-radius: 5px;
                padding: 5px 18px;
                font-size: 13px;
                font-weight: bold;
            }}
        """)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(1400)

    def show_action(self, action):
        label = action.replace("_", " ").title()
        self._show(label, _FEEDBACK_COLORS.get(action, "#4a90d9"))

    def show_toggle(self, active):
        self._show("Enabled ✓" if active else "Disabled",
                   "#4aae6e"   if active else "#888888")

    def _reposition(self):
        p = self.parent()
        if p:
            self.move((p.width() - self.width()) // 2,
                      p.height() - self.height() - 90)


# ── Key / mouse capture widget ─────────────────────────────────────────────────

class KeyCaptureBox(QLabel):
    """Shows current toggle binding. Click to enter capture mode and
    press any key or non-left mouse button to set a new binding."""

    binding_changed = pyqtSignal(dict)

    def __init__(self, binding, dark, bg, fg, border, hl, parent=None):
        super().__init__(parent)
        self._binding   = binding
        self._capturing = False
        self._dark, self._bg = dark, bg
        self._fg, self._border, self._hl = fg, border, hl
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh()

    def set_binding(self, binding):
        self._binding   = binding
        self._capturing = False
        self._refresh()

    def _refresh(self):
        active_border = self._hl if self._capturing else self._border
        text = ("Press any key or mouse button…"
                if self._capturing
                else f"Current:  {self._binding['display']}"
                if self._binding
                else "Click to set…")
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                border: 1px solid {active_border};
                border-radius: 4px;
                background: {self._bg};
                color: {self._fg};
                padding: 9px 14px;
                font-size: 13px;
            }}
        """)

    def mousePressEvent(self, event):
        if not self._capturing:
            self._capturing = True
            self._refresh()
            self.setFocus()
            return
        btn = event.button()
        if btn == Qt.MouseButton.LeftButton:
            return  # left-click just keeps waiting
        _names = {
            Qt.MouseButton.RightButton:  "Right Button",
            Qt.MouseButton.MiddleButton: "Middle Button",
            Qt.MouseButton.XButton1:     "Back Button",
            Qt.MouseButton.XButton2:     "Forward Button",
        }
        display = f"Mouse: {_names.get(btn, 'Button')}"
        self._binding   = {"type": "mouse", "button_int": btn.value, "display": display}
        self._capturing = False
        self._refresh()
        self.binding_changed.emit(self._binding)

    def keyPressEvent(self, event):
        if not self._capturing:
            return
        if int(event.key()) == int(Qt.Key.Key_Escape):
            self._capturing = False
            self._refresh()
            return
        text = event.text()
        display = f"Key: {text}" if text.strip() else f"Key: #{int(event.key())}"
        self._binding   = {"type": "key", "key_int": int(event.key()), "display": display}
        self._capturing = False
        self._refresh()
        self.binding_changed.emit(self._binding)

    def focusOutEvent(self, event):
        if self._capturing:
            self._capturing = False
            self._refresh()
        super().focusOutEvent(event)


# ── Help dialog ────────────────────────────────────────────────────────────────

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mouse Answer — Guide")
        self.setMinimumWidth(440)
        self._build()

    def _build(self):
        # No global setStyleSheet — styles applied only to specific widgets
        dark    = is_dark_mode()
        fg      = mw.app.palette().color(QPalette.ColorRole.Text).name()
        muted   = "#aaa" if dark else "#666"
        divider = "#444" if dark else "#e0e0e0"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Content (no scroll – all visible at once) ──────────────────────
        body = QWidget()
        vb   = QVBoxLayout(body)
        vb.setContentsMargins(28, 24, 28, 6)
        vb.setSpacing(0)

        title = QLabel("Mouse Answer")
        title.setStyleSheet(f"font-size:18px; font-weight:bold; color:{fg};")
        vb.addWidget(title)
        vb.addSpacing(4)

        sub = QLabel("Turn your mouse buttons into review shortcuts.")
        sub.setStyleSheet(f"font-size:13px; color:{muted};")
        sub.setWordWrap(True)
        vb.addWidget(sub)
        vb.addSpacing(14)

        def hr():
            f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
            f.setStyleSheet(
                f"color:{divider}; background:{divider}; max-height:1px; border:none;")
            vb.addWidget(f); vb.addSpacing(10)

        def heading(txt):
            l = QLabel(txt)
            l.setStyleSheet(f"font-size:13px; font-weight:bold; color:{fg};")
            vb.addWidget(l); vb.addSpacing(4)

        def item(txt):
            l = QLabel(f"• {txt}")
            l.setStyleSheet(f"font-size:13px; color:{fg};")
            l.setWordWrap(True); l.setContentsMargins(8, 0, 0, 0)
            vb.addWidget(l); vb.addSpacing(3)

        hr()
        heading("Features")
        item("Supports all mouse buttons, including scroll wheel and side buttons.")
        item("Each action: Show Answer, Again, Hard, Good, Easy, or Do Nothing")
        item("Separate actions for the question side and the answer side")
        item("Supports right double-click and extra mouse buttons (back / forward)")
        item("Speeds up review — rate cards without ever touching the keyboard")
        vb.addSpacing(10)

        heading("Quick Start")
        item("During review, perform the configured mouse action to trigger it")
        item("Context-aware: different behaviour on question vs answer side")
        item("Right single-click and double-click are configured independently")
        item("Scroll up / down are ideal for quick ratings (e.g. Easy / Again)")
        item("Back & forward side buttons work on gaming and multi-button mice")
        vb.addSpacing(10)

        heading("Customization  (Tools → Mouse Shortcuts)")
        item("Open Settings to customize mouse shortcuts.")
        item("General tab: enable answer feedback to see which button you pressed")
        item("Configure each mouse button for question and answer sides separately")
        item("Changes take effect immediately after saving")
        vb.addSpacing(6)

        root.addWidget(body)

        # Thin separator directly above buttons (tight, like Minimalistic Drawing Panel)
        def _sep():
            f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
            f.setStyleSheet(
                f"color:{divider}; background:{divider}; max-height:1px; border:none;")
            return f

        root.addWidget(_sep())

        # Bottom bar
        bar = QWidget()
        bl  = QHBoxLayout(bar)
        bl.setContentsMargins(16, 6, 16, 6)
        open_btn = QPushButton("Open Settings")
        open_btn.setDefault(True)
        open_btn.clicked.connect(self._open_settings)
        open_btn.setStyleSheet(
            "QPushButton{background:#4a90d9;color:#fff;border:none;"
            "font-weight:bold;border-radius:4px;padding:6px 18px;}"
            "QPushButton:hover{background:#5a9de3;}"
        )
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self._close)
        bl.addWidget(open_btn); bl.addStretch(); bl.addWidget(close_btn)
        root.addWidget(bar)

        root.addWidget(_sep())

        # Footer — version only, per the addon-guide design system
        foot = QLabel(f"v{VERSION}")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setStyleSheet(f"font-size:11px; color:{muted}; padding:2px 0;")
        root.addWidget(foot)

        self.adjustSize()
        # The fix above (locking to sizeHint() straight away) didn't work:
        # word-wrapped QLabels can't compute an accurate heightForWidth()
        # until the dialog has settled on its real width, so that first
        # sizeHint() pass over-reports height — adjustSize() had already
        # baked in the inflated number. Now that width is settled, ask the
        # layout again for the height it actually needs at that width.
        h = self.layout().heightForWidth(self.width())
        self.setFixedHeight(h if h > 0 else self.sizeHint().height())

    def _open_settings(self):
        self.accept()
        # If Help was opened from an existing SettingsDialog, closing this
        # dialog is enough — the parent settings window returns to focus.
        # Only spawn a new one when Help was opened from elsewhere (e.g. the
        # Tools menu or the Help Guide button directly).
        if not isinstance(self.parent(), SettingsDialog):
            QTimer.singleShot(0, show_settings)

    def _close(self):
        self.accept()
        # If Help was opened from Settings, Close backs all the way out
        # instead of just returning to the Settings window underneath.
        parent = self.parent()
        if isinstance(parent, SettingsDialog):
            parent.close()


# ── Settings dialog ────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mouse Answer Settings")
        self.setMinimumWidth(520)
        self._cfg             = get_config()
        self._combos          = {}
        self._key_capture     = None
        self._feedback_check  = None
        self._pending_binding = None   # Set by KeyCaptureBox; read in _save
        self._build()

    def _build(self):
        dark   = is_dark_mode()
        p      = mw.app.palette()
        base   = p.color(QPalette.ColorRole.Base).name()
        fg     = p.color(QPalette.ColorRole.WindowText).name()
        hl     = p.color(QPalette.ColorRole.Highlight).name()
        border = "#555" if dark else "#ccc"
        muted  = "#aaa" if dark else "#888"

        # No global setStyleSheet — Anki's native QSS handles tabs/combos/buttons.
        # Accent style is applied directly to save_btn only (see below).

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(8)

        tabs = QTabWidget()
        tabs.tabBar().setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(True)

        # Lazy tab loading: build each tab's widgets only when first selected.
        # This cuts open time from O(all_tabs) to O(one_tab).
        _lazy = [
            ("General", lambda: self._general_tab(dark, base, fg, border, muted, hl)),
            ("Right",   lambda: self._tab([
                ("RIGHT CLICK", None),
                ("right_click_question",        "Single click — on question"),
                ("right_click_answer",          "Single click — on answer"),
                ("DOUBLE CLICK", None),
                ("right_double_click_question", "Double click — on question"),
                ("right_double_click_answer",   "Double click — on answer"),
            ], muted)),
            ("Middle",  lambda: self._tab([
                ("MIDDLE CLICK", None),
                ("middle_click_question", "Click — on question"),
                ("middle_click_answer",   "Click — on answer"),
            ], muted)),
            ("Scroll",  lambda: self._tab([
                ("SCROLL UP", None),
                ("scroll_up_question",   "Scroll up — on question"),
                ("scroll_up_answer",     "Scroll up — on answer"),
                ("SCROLL DOWN", None),
                ("scroll_down_question", "Scroll down — on question"),
                ("scroll_down_answer",   "Scroll down — on answer"),
            ], muted)),
            ("Extra",   lambda: self._tab([
                ("BUTTON 4  (back button)", None),
                ("extra1_click_question", "Click — on question"),
                ("extra1_click_answer",   "Click — on answer"),
                ("BUTTON 5  (forward button)", None),
                ("extra2_click_question", "Click — on question"),
                ("extra2_click_answer",   "Click — on answer"),
            ], muted)),
            ("Help",    lambda: self._help_tab(muted)),
        ]
        _slots = []
        for label, builder in _lazy:
            ph = QWidget()
            tabs.addTab(ph, label)
            _slots.append((ph, builder))

        def _ensure(idx):
            ph, builder = _slots[idx]
            if ph.layout() is None:
                content = builder()
                lay = QVBoxLayout(ph)
                lay.setContentsMargins(0, 0, 0, 0)
                lay.addWidget(content)

        _ensure(0)                            # build General tab immediately
        tabs.currentChanged.connect(_ensure)  # build others on first click
        main.addWidget(tabs)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"color:{border}; background:{border}; max-height:1px; border:none;")
        main.addWidget(sep)

        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        save   = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(self._save)
        save.setStyleSheet(
            "QPushButton{background:#4a90d9;color:#fff;border:none;"
            "font-weight:bold;border-radius:4px;padding:6px 20px;}"
            "QPushButton:hover{background:#5a9de3;}"
        )
        row.addWidget(cancel); row.addWidget(save)
        main.addLayout(row)

    # ── General tab ───────────────────────────────────────────────────────────
    def _general_tab(self, dark, base, fg, border, muted, hl):
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(0)

        def sec_hdr(txt):
            l = QLabel(txt)
            l.setStyleSheet(
                f"font-weight:bold; color:{muted}; font-size:10px; "
                f"letter-spacing:1px; margin-top:14px; margin-bottom:6px;")
            lay.addWidget(l)

        # ── TOGGLE ────────────────────────────────────────────────────────────
        sec_hdr("TOGGLE")

        title_lbl = QLabel("Toggle key / mouse button")
        title_lbl.setStyleSheet(f"font-size:13px; font-weight:bold; color:{fg};")
        lay.addWidget(title_lbl)
        lay.addSpacing(3)

        desc_lbl = QLabel("Press any key or mouse button in this dialog to set it.")
        desc_lbl.setStyleSheet(f"font-size:12px; color:{muted};")
        lay.addWidget(desc_lbl)
        lay.addSpacing(8)

        binding = self._cfg.get("toggle_binding", _DEFAULT_TOGGLE)
        self._key_capture = KeyCaptureBox(
            binding, dark, base, fg, border, hl, w)
        self._key_capture.binding_changed.connect(
            lambda b: setattr(self, '_pending_binding', b))
        lay.addWidget(self._key_capture)

        # ── ANSWER FEEDBACK ───────────────────────────────────────────────────
        sec_hdr("ANSWER FEEDBACK")

        self._feedback_check = QCheckBox(
            "Show pressed answer after rating  (Again / Hard / Good / Easy)")
        self._feedback_check.setChecked(
            self._cfg.get("show_answer_feedback", False))
        lay.addWidget(self._feedback_check)
        lay.addSpacing(4)

        note_lbl = QLabel(
            "A small colour-coded label appears briefly at the bottom of the screen.")
        note_lbl.setStyleSheet(f"font-size:12px; color:{muted};")
        note_lbl.setWordWrap(True)
        lay.addWidget(note_lbl)

        lay.addStretch()
        return w

    # ── Shared tab builder ────────────────────────────────────────────────────
    def _tab(self, rows, muted):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 16); lay.setSpacing(0)
        for key, label in rows:
            if label is None:
                lbl = QLabel(key)
                lbl.setStyleSheet(
                    f"font-weight:bold; color:{muted}; font-size:10px; "
                    f"letter-spacing:1px; margin-top:12px; margin-bottom:4px;")
                lay.addWidget(lbl)
            else:
                rw = QWidget(); rw.setStyleSheet("background:transparent;")
                rl = QHBoxLayout(rw)
                rl.setContentsMargins(0, 4, 0, 4); rl.setSpacing(12)
                lbl = QLabel(label); lbl.setFixedWidth(220)
                rl.addWidget(lbl); rl.addWidget(self._combo(key)); rl.addStretch()
                lay.addWidget(rw)
        lay.addStretch()
        return w

    def _help_tab(self, muted):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 24, 24, 24); lay.setSpacing(8)
        hdr = QLabel("HELP")
        hdr.setStyleSheet(
            f"font-weight:bold; color:{muted}; font-size:10px; "
            f"letter-spacing:1px; margin-bottom:4px;")
        lay.addWidget(hdr)
        for text, slot in [
            ("Open Help Guide",      self._open_help),
            ("⚑  Report an Issue",  lambda: webbrowser.open(ISSUE_URL)),
            ("↺  Reset to Default", self._reset),
        ]:
            b = QPushButton(text); b.setMinimumHeight(34); b.clicked.connect(slot)
            lay.addWidget(b)
        lay.addStretch()
        return w

    def _combo(self, key):
        c = QComboBox()
        for val, label in ACTIONS:
            c.addItem(label, val)
        current = self._cfg.get(key, "do_nothing")
        idx = c.findData(current)
        if idx >= 0:
            c.setCurrentIndex(idx)
        self._combos[key] = c
        return c

    def _save(self):
        # Start from the full current config so settings for tabs the user
        # never opened (and therefore never built) are preserved, not wiped.
        cfg = dict(self._cfg)
        cfg.update({k: c.currentData() for k, c in self._combos.items()})
        # Use the newly captured binding if the user changed it; otherwise keep existing.
        if self._pending_binding is not None:
            cfg["toggle_binding"] = dict(self._pending_binding)
        else:
            tb = self._cfg.get("toggle_binding")
            cfg["toggle_binding"] = dict(tb) if tb else _DEFAULT_TOGGLE.copy()
        cfg["addon_active"]         = self._cfg.get("addon_active", True)
        cfg["show_answer_feedback"] = (self._feedback_check.isChecked()
                                       if self._feedback_check else False)
        save_config(cfg)
        self.accept()

    def _open_help(self):
        HelpDialog(self).exec()

    def _reset(self):
        if QMessageBox.question(
            self, "Reset to Default",
            "Reset all Mouse Answer settings to their defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        new_cfg = dict(DEFAULT_CONFIG)
        new_cfg["toggle_binding"] = _DEFAULT_TOGGLE.copy()
        save_config(new_cfg)
        self._cfg             = new_cfg   # same object as _config_cache now
        self._pending_binding = None
        for key, combo in self._combos.items():
            val = DEFAULT_CONFIG.get(key, "do_nothing")
            idx = combo.findData(val)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        if self._key_capture:
            self._key_capture.set_binding(_DEFAULT_TOGGLE.copy())
        if self._feedback_check:
            self._feedback_check.setChecked(False)


def show_settings():
    SettingsDialog(mw).exec()


# ── Right-click single / double disambiguation ─────────────────────────────────

class _RCState:
    """Holds deferred right-click state for single/double disambiguation."""
    def __init__(self):
        self.timer    = None   # QTimer (created lazily)
        self.action   = None   # Pending single-click action string
        self.reviewer = None   # mw.reviewer at press time

_rc = _RCState()


def _fire_pending_single_rc():
    """Timer callback: execute the deferred right-click single action."""
    action, reviewer = _rc.action, _rc.reviewer
    _rc.action = _rc.reviewer = None
    if not action or action == "do_nothing" or not reviewer:
        return
    if mw.state != "review":
        return
    cfg = get_config()
    if not cfg.get("addon_active", True):
        return
    if do_action(action, reviewer):
        if cfg.get("show_answer_feedback", False) and _feedback_widget:
            _feedback_widget.show_action(action)


# ── Event filter ───────────────────────────────────────────────────────────────

_T_KEY    = QEvent.Type.KeyPress
_T_CTX    = QEvent.Type.ContextMenu
_T_WHEEL  = QEvent.Type.Wheel
_T_PRESS  = QEvent.Type.MouseButtonPress
_T_DBLCLK = QEvent.Type.MouseButtonDblClick
_HANDLED  = frozenset((_T_KEY, _T_CTX, _T_WHEEL, _T_PRESS, _T_DBLCLK))

# Same idea as the _T_* aliases above: resolve these once instead of
# re-walking the Qt.MouseButton attribute chain on every mouse event.
_BTN_RIGHT  = Qt.MouseButton.RightButton
_BTN_MIDDLE = Qt.MouseButton.MiddleButton
_BTN_X1     = Qt.MouseButton.XButton1
_BTN_X2     = Qt.MouseButton.XButton2
_BTN_XSET   = (_BTN_X1, _BTN_X2)


class MouseFilter(QObject):
    def eventFilter(self, obj, event):
        t = event.type()
        if t not in _HANDLED:
            return False

        # ── Non-QWidget XButton guard ─────────────────────────────────────────
        # QWebEngineView's internal rendering surfaces are NOT QWidget instances.
        # They bypass the isinstance guard below, so the XButton event reaches
        # Chromium's input handler, which treats XButton1/2 as browser Back/
        # Forward navigation.  The WebView jumps backward exactly as Anki loads
        # the next card -> audio plays (independent pipeline) but text and images
        # disappear.
        #
        # Fix: catch ALL XButton presses on non-QWidget objects during review,
        # execute the configured action here, then consume the event so Chromium
        # never sees it.  If the same physical click also dispatches to the
        # QWidget path below, do_action's debounce swallows the duplicate.
        if t == _T_PRESS and mw.state == "review":
            try:
                btn = event.button()
                if btn in _BTN_XSET:
                    if not isinstance(obj, QWidget):
                        _rv = getattr(mw, "reviewer", None)
                        if _rv:
                            _cfg = get_config()
                            if _cfg.get("addon_active", True):
                                _rv_state = getattr(_rv, "state", "")
                                if btn == _BTN_X1:
                                    _key = ("extra1_click_question"
                                            if _rv_state == "question"
                                            else "extra1_click_answer")
                                else:
                                    _key = ("extra2_click_question"
                                            if _rv_state == "question"
                                            else "extra2_click_answer")
                                _action = _cfg.get(_key, "do_nothing")
                                if do_action(_action, _rv):
                                    if _cfg.get("show_answer_feedback") and _feedback_widget:
                                        _feedback_widget.show_action(_action)
                        return True  # always consume -- prevents Chromium nav
                    # QWidget: fall through to full handler below
            except Exception:
                pass

        # ── Standard guard ────────────────────────────────────────────────────
        # Never intercept events on dialogs or any window other than mw.
        # Cheapest check first: this filter is installed application-wide, so
        # it runs for every keypress/click/scroll everywhere in Anki (browser,
        # editor, Settings dialog, etc.), and almost all of that happens while
        # not reviewing. Bailing out on mw.state (a plain attribute check)
        # before touching isinstance()/.window() (PyQt/C++ calls) skips the
        # pricier check for the overwhelming majority of events app-wide.
        if mw.state != "review":
            return False
        try:
            if not isinstance(obj, QWidget) or obj.window() is not mw:
                return False
        except Exception:
            return False

        cfg     = get_config()
        binding = cfg.get("toggle_binding", _DEFAULT_TOGGLE)

        # ── Toggle key (keyboard) – active regardless of addon_active ─────────
        if t == _T_KEY:
            if (binding and binding.get("type") == "key"
                    and int(event.key()) == binding.get("key_int", 0)
                    and not isinstance(obj, (QLineEdit, QTextEdit,
                                             QComboBox, QSpinBox))):
                new_state = not cfg.get("addon_active", True)
                cfg["addon_active"] = new_state
                save_config(cfg)
                if _feedback_widget:
                    _feedback_widget.show_toggle(new_state)
                return True
            return False   # never consume other key events

        # ── Mouse events ──────────────────────────────────────────────────────
        reviewer = getattr(mw, "reviewer", None)
        if not reviewer:
            return False
        state = getattr(reviewer, "state", "")

        # Toggle via mouse button
        if (binding and binding.get("type") == "mouse" and t == _T_PRESS
                and event.button().value == binding.get("button_int", 0)):
            new_state = not cfg.get("addon_active", True)
            cfg["addon_active"] = new_state
            save_config(cfg)
            if _feedback_widget:
                _feedback_widget.show_toggle(new_state)
            return True

        # Addon inactive – pass most events through, but still eat XButton to
        # prevent the WebView from navigating away even when the addon is off.
        if not cfg.get("addon_active", True):
            if t == _T_PRESS and event.button() in _BTN_XSET:
                return True
            return False

        # Suppress OS context menu when right single-click OR right double-click is bound
        if t == _T_CTX:
            q = (state == "question")
            return (cfg.get("right_click_question"        if q else "right_click_answer",        "do_nothing") != "do_nothing"
                 or cfg.get("right_double_click_question" if q else "right_double_click_answer", "do_nothing") != "do_nothing")

        def _act(action):
            if do_action(action, reviewer):
                if cfg.get("show_answer_feedback") and _feedback_widget:
                    _feedback_widget.show_action(action)
                return True
            return False

        if t == _T_WHEEL:
            dy = event.angleDelta().y()
            key = ("scroll_up_question"   if state == "question" else "scroll_up_answer") \
                  if dy > 0 else \
                  ("scroll_down_question" if state == "question" else "scroll_down_answer")
            return _act(cfg.get(key, "do_nothing"))

        if t == _T_DBLCLK and event.button() == _BTN_RIGHT:
            # Cancel the deferred single-click (if pending) and fire double instead
            if _rc.timer and _rc.timer.isActive():
                _rc.timer.stop()
            _rc.action = _rc.reviewer = None
            q = (state == "question")
            return _act(cfg.get("right_double_click_question" if q else "right_double_click_answer", "do_nothing"))

        if t == _T_PRESS:
            btn = event.button()
            if btn == _BTN_RIGHT:
                q             = (state == "question")
                single_action = cfg.get("right_click_question"        if q else "right_click_answer",        "do_nothing")
                double_action = cfg.get("right_double_click_question" if q else "right_double_click_answer", "do_nothing")
                if double_action != "do_nothing":
                    # Defer single-click: _T_DBLCLK cancels the timer before it fires
                    if _rc.timer is None:
                        _rc.timer = QTimer()
                        _rc.timer.setSingleShot(True)
                        _rc.timer.timeout.connect(_fire_pending_single_rc)
                    _rc.action   = single_action
                    _rc.reviewer = reviewer
                    _rc.timer.start(QApplication.instance().doubleClickInterval())
                    return True   # consume press; action fires via timer or is cancelled
                return _act(single_action)
            if btn == _BTN_MIDDLE:
                key = "middle_click_question" if state == "question" else "middle_click_answer"
                return _act(cfg.get(key, "do_nothing"))
            if btn == _BTN_X1:
                # BUG FIX: previously returned _act(...) which returns False for
                # "do_nothing", allowing the event to reach the WebView and trigger
                # Chromium's built-in "browser back" navigation → blank card.
                # Now we always return True (consume) regardless of the configured
                # action, executing it only when it isn't "do_nothing".
                key = "extra1_click_question" if state == "question" else "extra1_click_answer"
                _act(cfg.get(key, "do_nothing"))
                return True  # always consume – prevents WebView browser-back
            if btn == _BTN_X2:
                key = "extra2_click_question" if state == "question" else "extra2_click_answer"
                _act(cfg.get(key, "do_nothing"))
                return True  # always consume – prevents WebView browser-forward

        return False


_filter = MouseFilter()


def _install():
    global _config_cache, _installed, _feedback_widget
    _config_cache = None
    if not _installed:
        mw.app.installEventFilter(_filter)
        _feedback_widget = FeedbackWidget(mw)
        _installed = True
    if not any(a.text() == "Mouse Shortcuts"
               for a in mw.form.menuTools.actions()):
        action = QAction("Mouse Shortcuts", mw)
        action.triggered.connect(show_settings)
        mw.form.menuTools.addAction(action)


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(500, _install))
