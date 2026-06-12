"""
Mouse Answer - Configurable mouse shortcuts for Anki review
Version 1.2.0
"""
import webbrowser
from aqt import mw, gui_hooks
from aqt.qt import *

VERSION    = "1.2.0"
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

_config_cache    = None
_installed       = False
_feedback_widget = None


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


def do_action(action, reviewer):
    """Execute a configured action; return True if consumed."""
    if not action or action == "do_nothing":
        return False
    state = getattr(reviewer, "state", None)
    if action == "show_answer":
        if state != "question":
            return False
        for name in ("_showAnswer", "show_answer"):
            fn = getattr(reviewer, name, None)
            if callable(fn):
                try:
                    fn(); return True
                except Exception:
                    pass
        return False
    ease = {"again": 1, "hard": 2, "good": 3, "easy": 4}.get(action)
    if ease is not None and state == "answer":
        for name in ("_answerCard", "_answer"):
            fn = getattr(reviewer, name, None)
            if callable(fn):
                try:
                    fn(ease); return True
                except Exception:
                    pass
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
        self._show(action.capitalize(), _FEEDBACK_COLORS.get(action, "#4a90d9"))

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

        sub = QLabel("Use your mouse buttons as shortcuts during Anki card review.")
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
        heading("What it does")
        item("Right click, middle click, scroll wheel, and extra buttons are configurable")
        item("Each action: Show Answer, Again, Hard, Good, Easy, or Do Nothing")
        item("Separate actions for the question side and the answer side")
        item("Supports right double-click and extra mouse buttons (back / forward)")
        item("Speeds up review — rate cards without ever touching the keyboard")
        vb.addSpacing(10)

        heading("How to use")
        item("During review, perform the configured mouse action to trigger it")
        item("Context-aware: different behaviour on question vs answer side")
        item("Right single-click and double-click are configured independently")
        item("Scroll up / down are ideal for quick ratings (e.g. Easy / Again)")
        item("Back & forward side buttons work on gaming and multi-button mice")
        vb.addSpacing(10)

        heading("Settings  (Tools → Mouse Answer Settings)")
        item("General tab: set a toggle key to enable / disable the addon mid-review")
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
        bl.setContentsMargins(16, 8, 16, 8)
        open_btn = QPushButton("Open Settings")
        open_btn.clicked.connect(self._open_settings)
        ok_btn = QPushButton("Got it  ✓")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet(
            "QPushButton{background:#4a90d9;color:#fff;border:none;"
            "font-weight:bold;border-radius:4px;padding:6px 18px;}"
            "QPushButton:hover{background:#5a9de3;}"
        )
        bl.addWidget(open_btn); bl.addStretch(); bl.addWidget(ok_btn)
        root.addWidget(bar)

        root.addWidget(_sep())

        # Footer
        foot = QLabel(f"Mouse Answer  v{VERSION}  —  Created by Adel")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setStyleSheet(
            f"font-size:11px; color:{muted}; padding:6px 0;")
        root.addWidget(foot)

        self.adjustSize()

    def _open_settings(self):
        self.accept()
        # If Help was opened from an existing SettingsDialog, closing this
        # dialog is enough — the parent settings window returns to focus.
        # Only spawn a new one when Help was opened from elsewhere (e.g. the
        # Tools menu or the Help Guide button directly).
        if not isinstance(self.parent(), SettingsDialog):
            QTimer.singleShot(0, show_settings)


# ── Settings dialog ────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mouse Answer Settings")
        self.setMinimumWidth(520)
        self._cfg            = get_config()
        self._combos         = {}
        self._key_capture    = None
        self._feedback_check = None
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
            lambda b: self._cfg.update({"toggle_binding": b}))
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
        for i, (v, _) in enumerate(ACTIONS):
            if v == current:
                c.setCurrentIndex(i); break
        self._combos[key] = c
        return c

    def _save(self):
        cfg = {k: c.currentData() for k, c in self._combos.items()}
        cfg["toggle_binding"]       = self._cfg.get("toggle_binding", _DEFAULT_TOGGLE)
        cfg["addon_active"]         = self._cfg.get("addon_active", True)
        cfg["show_answer_feedback"] = self._feedback_check.isChecked()
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
        save_config(DEFAULT_CONFIG.copy())
        self._cfg = DEFAULT_CONFIG.copy()
        for key, combo in self._combos.items():
            val = DEFAULT_CONFIG.get(key, "do_nothing")
            for i, (v, _) in enumerate(ACTIONS):
                if v == val:
                    combo.setCurrentIndex(i); break
        if self._key_capture:
            self._key_capture.set_binding(_DEFAULT_TOGGLE)
        if self._feedback_check:
            self._feedback_check.setChecked(False)


def show_settings():
    SettingsDialog(mw).exec()


# ── Event filter ───────────────────────────────────────────────────────────────

_T_KEY    = QEvent.Type.KeyPress
_T_CTX    = QEvent.Type.ContextMenu
_T_WHEEL  = QEvent.Type.Wheel
_T_PRESS  = QEvent.Type.MouseButtonPress
_T_DBLCLK = QEvent.Type.MouseButtonDblClick
_HANDLED  = frozenset((_T_KEY, _T_CTX, _T_WHEEL, _T_PRESS, _T_DBLCLK))


class MouseFilter(QObject):
    def eventFilter(self, obj, event):
        t = event.type()
        if t not in _HANDLED:
            return False
        # Never intercept events on dialogs or any window other than the main
        # Anki window — this lets KeyCaptureBox receive middle-click freely
        # window() is the correct PyQt6 API; topLevelWidget() is unavailable
        # on some internal Qt6 objects (e.g. QWebEngineView sub-widgets)
        try:
            if not isinstance(obj, QWidget) or obj.window() is not mw:
                return False
        except Exception:
            return False
        if mw.state != "review":
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

        # ── Mouse events ───────────────────────────────────────────────────────
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

        # Addon inactive – pass all mouse events through
        if not cfg.get("addon_active", True):
            return False

        # Suppress OS context menu when right-click is bound
        if t == _T_CTX:
            key = "right_click_question" if state == "question" else "right_click_answer"
            return cfg.get(key, "do_nothing") != "do_nothing"

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

        if t == _T_DBLCLK and event.button() == Qt.MouseButton.RightButton:
            key = ("right_double_click_question" if state == "question"
                   else "right_double_click_answer")
            return _act(cfg.get(key, "do_nothing"))

        if t == _T_PRESS:
            btn = event.button()
            if btn == Qt.MouseButton.RightButton:
                key = "right_click_question" if state == "question" else "right_click_answer"
                return _act(cfg.get(key, "do_nothing"))
            if btn == Qt.MouseButton.MiddleButton:
                key = "middle_click_question" if state == "question" else "middle_click_answer"
                return _act(cfg.get(key, "do_nothing"))
            if btn == Qt.MouseButton.XButton1:
                key = "extra1_click_question" if state == "question" else "extra1_click_answer"
                return _act(cfg.get(key, "do_nothing"))
            if btn == Qt.MouseButton.XButton2:
                key = "extra2_click_question" if state == "question" else "extra2_click_answer"
                return _act(cfg.get(key, "do_nothing"))

        return False


_filter = MouseFilter()


def _install():
    global _config_cache, _installed, _feedback_widget
    _config_cache = None
    if not _installed:
        mw.app.installEventFilter(_filter)
        _feedback_widget = FeedbackWidget(mw)
        _installed = True
    if not any(a.text() == "Mouse Answer Settings"
               for a in mw.form.menuTools.actions()):
        action = QAction("Mouse Answer Settings", mw)
        action.triggered.connect(show_settings)
        mw.form.menuTools.addAction(action)


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(500, _install))
