"""
================================================================================
AUTO TYPER - Natural Human Typing Simulator Desktop Application
================================================================================

Required libraries to install before running:
    pip install pynput pyperclip

Optional: To build a standalone Windows .exe:
    pip install pyinstaller
    pyinstaller --noconsole --onefile auto_typer.py

Features:
- Large multi-line text input with live character, word, and line counters.
- Prominent Start and Stop buttons (toolbar + pinned bottom bar) with hotkeys.
- Keystroke delay slider (speed control) showing delay in ms and chars/second.
- "Humanize speed" option with natural delay jitter and punctuation cadence.
- Configurable countdown delay before typing starts so you can switch windows.
- Optional window auto-minimize during typing and auto-restore when finished.
- Global emergency stop hotkey (F8 or Esc) that works even when unfocused.
- Accurate character simulation with automatic fallback to clipboard paste.
- Multi-threaded execution with a thread-safe message queue so the GUI never freezes.
================================================================================
"""

import os
import sys
import time
import random
import queue
import platform
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple, Any

import pyperclip
from pynput import keyboard
from pynput.keyboard import Controller, Key


class TypingApp:
    """Main desktop application class for the Auto Typer simulator."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Typer - Human Typing Simulator")
        self.root.geometry("740x660")
        self.root.minsize(580, 520)

        # Keyboard simulation controller
        self.keyboard = Controller()

        # Concurrency & communication queue
        self.is_running = False
        self.stop_event = threading.Event()
        self.stop_reason: Optional[str] = None
        self.typing_thread: Optional[threading.Thread] = None
        self.msg_queue: queue.Queue = queue.Queue()
        self._queue_poll_job: Optional[str] = None

        # Apply a polished modern ttk theme
        self._configure_styles()

        # Build user interface
        self._create_widgets()

        # Keyboard shortcuts inside the window
        self.root.bind("<F6>", lambda e: self.start_typing())
        self.root.bind("<Control-Return>", lambda e: self.start_typing())

        # Start background queue poller for thread-safe UI updates
        self._start_queue_poller()

        # Start global emergency stop listener (F8 and Esc)
        self._start_global_hotkey_listener()

        # Handle window close event cleanly
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _configure_styles(self):
        """Set up ttk styling and color palette."""
        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        if "vista" in available_themes:
            self.style.theme_use("vista")
        elif "clam" in available_themes:
            self.style.theme_use("clam")

        # Color palette
        self.bg_color = "#f4f5f7"
        self.primary_color = "#0066cc"
        self.text_color = "#202124"
        self.subtext_color = "#5f6368"
        self.success_color = "#107c10"
        self.danger_color = "#d83b01"

        self.root.configure(bg=self.bg_color)

        # Custom ttk styles
        self.style.configure(".", font=("Segoe UI", 9))
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#1a1a1a")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground=self.subtext_color)
        self.style.configure("Badge.TLabel", font=("Segoe UI", 8, "bold"), foreground="#b3261e", background="#fce8e6", padding=4)
        self.style.configure("Stats.TLabel", font=("Segoe UI", 8), foreground=self.subtext_color)

    def _create_widgets(self):
        """Build and arrange all UI widgets with pinned bottom controls."""
        main_container = ttk.Frame(self.root, padding="12")
        main_container.pack(fill=tk.BOTH, expand=True)

        # -------------------------------------------------------------
        # 1. Header Section (Top)
        # -------------------------------------------------------------
        header_frame = ttk.Frame(main_container)
        header_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        lbl_title = ttk.Label(title_box, text="⌨️ Human Auto Typer", style="Header.TLabel")
        lbl_title.pack(anchor=tk.W)

        lbl_subtitle = ttk.Label(
            title_box,
            text="Simulate realistic keystrokes into any window or web application",
            style="SubHeader.TLabel"
        )
        lbl_subtitle.pack(anchor=tk.W)

        # Emergency Stop Badge in top right
        hotkey_badge = ttk.Label(
            header_frame,
            text="Emergency Stop: F8 or ESC",
            style="Badge.TLabel",
            relief=tk.GROOVE
        )
        hotkey_badge.pack(side=tk.RIGHT, pady=2)

        # -------------------------------------------------------------
        # 2. Action Buttons (Pinned to the Very Bottom)
        # -------------------------------------------------------------
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        # Big, highly visible Start Button
        self.btn_start = tk.Button(
            btn_frame,
            text="▶  START TYPING  (F6 or Ctrl+Enter)",
            font=("Segoe UI", 11, "bold"),
            bg="#107c10",
            fg="#ffffff",
            activebackground="#0b5a0b",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            height=2,
            command=self.start_typing
        )
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Big, highly visible Stop Button
        self.btn_stop = tk.Button(
            btn_frame,
            text="⏹  STOP TYPING  (Esc or F8)",
            font=("Segoe UI", 11, "bold"),
            bg="#d0d0d0",
            fg="#888888",
            activebackground="#a82e01",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            height=2,
            state=tk.DISABLED,
            command=lambda: self.stop_typing(source="Stop button")
        )
        self.btn_stop.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))

        # -------------------------------------------------------------
        # 3. Status & Progress Section (Pinned above buttons)
        # -------------------------------------------------------------
        status_group = ttk.LabelFrame(main_container, text=" Status & Progress ", padding="8")
        status_group.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 6))

        # Status row
        status_row = ttk.Frame(status_group)
        status_row.pack(fill=tk.X, pady=(0, 4))

        self.lbl_status_badge = ttk.Label(status_row, text="IDLE", font=("Segoe UI", 9, "bold"), foreground="#5f6368")
        self.lbl_status_badge.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_status_text = ttk.Label(
            status_row,
            text="Ready. Paste your text, choose your options, and click 'Start Typing'.",
            font=("Segoe UI", 9)
        )
        self.lbl_status_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Progress bar with percentage
        prog_row = ttk.Frame(status_group)
        prog_row.pack(fill=tk.X)

        self.progress_bar = ttk.Progressbar(prog_row, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.lbl_progress_pct = ttk.Label(prog_row, text="0%", width=5, font=("Segoe UI", 9, "bold"))
        self.lbl_progress_pct.pack(side=tk.RIGHT)

        # -------------------------------------------------------------
        # 4. Settings & Controls Section (Pinned above status)
        # -------------------------------------------------------------
        settings_group = ttk.LabelFrame(main_container, text=" Typing Speed & Options ", padding="8")
        settings_group.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 6))

        # Speed Slider Row
        speed_header_row = ttk.Frame(settings_group)
        speed_header_row.pack(fill=tk.X, pady=(0, 2))

        ttk.Label(speed_header_row, text="Typing Delay:").pack(side=tk.LEFT)
        self.lbl_speed_val = ttk.Label(speed_header_row, text="45 ms / key (~22 chars/sec)", font=("Segoe UI", 9, "bold"))
        self.lbl_speed_val.pack(side=tk.RIGHT)

        slider_row = ttk.Frame(settings_group)
        slider_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(slider_row, text="Fast (10ms)", style="Stats.TLabel").pack(side=tk.LEFT)
        self.speed_slider = ttk.Scale(
            slider_row,
            from_=10,
            to=250,
            value=45,
            orient=tk.HORIZONTAL,
            command=self._on_speed_slider_change
        )
        self.speed_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Label(slider_row, text="Slow (250ms)", style="Stats.TLabel").pack(side=tk.RIGHT)

        # Option Checkboxes & Inputs Row
        opts_row = ttk.Frame(settings_group)
        opts_row.pack(fill=tk.X, pady=(2, 2))

        # Randomize delay checkbox
        self.randomize_var = tk.BooleanVar(value=True)
        chk_random = ttk.Checkbutton(
            opts_row,
            text="Humanize speed (random jitter & punctuation pauses)",
            variable=self.randomize_var
        )
        chk_random.pack(side=tk.LEFT)

        # Auto-minimize window checkbox
        self.minimize_var = tk.BooleanVar(value=True)
        chk_minimize = ttk.Checkbutton(
            opts_row,
            text="Minimize window during typing (restores on finish)",
            variable=self.minimize_var
        )
        chk_minimize.pack(side=tk.RIGHT)

        # Start Delay Row
        delay_row = ttk.Frame(settings_group)
        delay_row.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(delay_row, text="Countdown delay before typing begins:").pack(side=tk.LEFT)
        self.spin_delay = ttk.Spinbox(delay_row, from_=1, to=30, width=4)
        self.spin_delay.set(5)
        self.spin_delay.pack(side=tk.LEFT, padx=6)
        ttk.Label(delay_row, text="seconds  (gives you time to click into the target window)").pack(side=tk.LEFT)

        # -------------------------------------------------------------
        # 5. Text Input Area (Expands to fill all remaining vertical space)
        # -------------------------------------------------------------
        text_group = ttk.LabelFrame(main_container, text=" Text to Type ", padding="8")
        text_group.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 6))

        # Toolbar above the text area with Quick Start button
        text_toolbar = ttk.Frame(text_group)
        text_toolbar.pack(fill=tk.X, pady=(0, 6))

        # Quick Start button right in the toolbar
        self.btn_start_top = tk.Button(
            text_toolbar,
            text="▶ Start Typing",
            font=("Segoe UI", 9, "bold"),
            bg="#107c10",
            fg="#ffffff",
            activebackground="#0b5a0b",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            bd=1,
            cursor="hand2",
            padx=8,
            command=self.start_typing
        )
        self.btn_start_top.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_stop_top = tk.Button(
            text_toolbar,
            text="⏹ Stop",
            font=("Segoe UI", 9, "bold"),
            bg="#d0d0d0",
            fg="#888888",
            activebackground="#a82e01",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            bd=1,
            cursor="hand2",
            padx=8,
            state=tk.DISABLED,
            command=lambda: self.stop_typing(source="Stop button")
        )
        self.btn_stop_top.pack(side=tk.LEFT, padx=(0, 10))

        btn_paste = ttk.Button(text_toolbar, text="📋 Paste", command=self._paste_clipboard, width=9)
        btn_paste.pack(side=tk.LEFT, padx=(0, 4))

        btn_sample = ttk.Button(text_toolbar, text="📝 Sample", command=self._load_sample_text, width=9)
        btn_sample.pack(side=tk.LEFT, padx=(0, 4))

        btn_clear = ttk.Button(text_toolbar, text="🗑️ Clear", command=self._clear_text, width=9)
        btn_clear.pack(side=tk.LEFT, padx=(0, 4))

        self.lbl_text_stats = ttk.Label(text_toolbar, text="0 characters | 0 words | 0 lines", style="Stats.TLabel")
        self.lbl_text_stats.pack(side=tk.RIGHT, padx=4)

        # Text Box with Scrollbars (comfortable initial height of 9 lines)
        text_container = ttk.Frame(text_group)
        text_container.pack(fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(text_container, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(
            text_container,
            wrap=tk.WORD,
            undo=True,
            height=9,
            yscrollcommand=v_scroll.set,
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#1e1e1e",
            insertbackground="#000000",
            selectbackground="#cce8ff",
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=8
        )
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.config(command=self.text_area.yview)

        # Keybindings and right click menu for text box
        self.text_area.bind("<KeyRelease>", lambda e: self._update_stats())
        self.text_area.bind("<Control-a>", self._select_all_text)
        self.text_area.bind("<Control-A>", self._select_all_text)
        self._setup_context_menu()

    # -----------------------------------------------------------------
    # UI Helper Methods & Event Handlers
    # -----------------------------------------------------------------
    def _set_buttons_state(self, running: bool):
        """Update appearance and enable/disable state of all Start and Stop buttons."""
        if running:
            # Disable Start buttons
            for btn in (self.btn_start, self.btn_start_top):
                btn.config(state=tk.DISABLED, bg="#d0d0d0", fg="#888888")
            # Enable Stop buttons (vibrant alert red)
            for btn in (self.btn_stop, self.btn_stop_top):
                btn.config(state=tk.NORMAL, bg="#d83b01", fg="#ffffff")
        else:
            # Enable Start buttons (vibrant forest green)
            for btn in (self.btn_start, self.btn_start_top):
                btn.config(state=tk.NORMAL, bg="#107c10", fg="#ffffff")
            # Disable Stop buttons
            for btn in (self.btn_stop, self.btn_stop_top):
                btn.config(state=tk.DISABLED, bg="#d0d0d0", fg="#888888")

    def _setup_context_menu(self):
        """Context menu for right-clicking the text box."""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Cut", command=lambda: self.text_area.event_generate("<<Cut>>"))
        self.context_menu.add_command(label="Copy", command=lambda: self.text_area.event_generate("<<Copy>>"))
        self.context_menu.add_command(label="Paste", command=self._paste_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=self._select_all_text)
        self.context_menu.add_command(label="Clear", command=self._clear_text)

        self.text_area.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        """Display the context menu at mouse position."""
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _select_all_text(self, event=None):
        """Select all text inside the text widget."""
        self.text_area.tag_add("sel", "1.0", "end")
        return "break"

    def _paste_clipboard(self):
        """Paste clipboard content into the text area."""
        try:
            content = pyperclip.paste()
            if content:
                self.text_area.insert(tk.INSERT, content)
                self._update_stats()
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Could not paste clipboard content:\n{e}")

    def _clear_text(self):
        """Clear the text area."""
        self.text_area.delete("1.0", tk.END)
        self._update_stats()

    def _load_sample_text(self):
        """Insert a sample text snippet for demonstration."""
        sample = (
            "Hello World!\n"
            "This text is being automatically typed using natural keystroke simulation.\n"
            "Notice how it handles multiple lines, punctuation pauses (like this!), and tabs:\n"
            "\t• Item 1: Speed jitter mimics authentic human fingers.\n"
            "\t• Item 2: Special symbols (#, $, @, %) and emojis (🔥, 🚀) are supported.\n"
            "Press F8 or Esc anytime to instantly stop typing."
        )
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", sample)
        self._update_stats()

    def _update_stats(self):
        """Update live character, word, and line count labels."""
        raw_text = self.text_area.get("1.0", "end-1c")
        chars = len(raw_text)
        words = len(raw_text.split())
        lines = len(raw_text.splitlines()) if raw_text else 0
        self.lbl_text_stats.config(text=f"{chars:,} characters | {words:,} words | {lines:,} lines")

    def _on_speed_slider_change(self, val):
        """Update slider readout with ms delay and characters/sec."""
        ms = int(round(float(val)))
        cps = 1000.0 / ms if ms > 0 else 0
        wpm = int(cps * 60 / 5)
        self.lbl_speed_val.config(text=f"{ms} ms / key (~{cps:.1f} chars/sec, ~{wpm} WPM)")

    def _set_status(self, badge: str, message: str, color: str = "#202124"):
        """Update status badge and description message."""
        self.lbl_status_badge.config(text=badge.upper(), foreground=color)
        self.lbl_status_text.config(text=message, foreground=color)

    # -----------------------------------------------------------------
    # Thread-Safe Queue Processing (Dispatched on Main Tkinter Loop)
    # -----------------------------------------------------------------
    def _start_queue_poller(self):
        """Periodically drain the message queue on the main GUI thread."""
        try:
            while not self.msg_queue.empty():
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "status":
                    badge, text, color = data
                    self._set_status(badge, text, color)
                elif msg_type == "progress":
                    typed_count, total_chars, pct, msg = data
                    self._update_progress_ui(typed_count, total_chars, pct, msg)
                elif msg_type == "finished":
                    self._on_process_finished_ui(data)
                elif msg_type == "stopped":
                    self._on_process_stopped_ui(data)
                elif msg_type == "minimize":
                    self.root.iconify()
        except Exception as e:
            print(f"[Queue Poller Warning] {e}")
        finally:
            # Re-schedule poller every 30ms (~33 fps)
            self._queue_poll_job = self.root.after(30, self._start_queue_poller)

    def _update_progress_ui(self, current: int, total: int, pct: float, msg: str):
        """Update progress bar and status on GUI thread."""
        self.progress_bar["value"] = pct
        self.lbl_progress_pct.config(text=f"{pct:.0f}%")
        self._set_status("TYPING", msg, self.primary_color)

    def _on_process_finished_ui(self, total_chars: int):
        """Handle finish state on GUI thread."""
        self.is_running = False
        self._set_buttons_state(running=False)
        self.progress_bar["value"] = 100
        self.lbl_progress_pct.config(text="100%")
        self._set_status(
            "FINISHED",
            f"Finished! Successfully typed all {total_chars:,} characters.",
            self.success_color
        )
        if self.minimize_var.get():
            self._restore_window()

    def _on_process_stopped_ui(self, reason: str):
        """Handle stopped state on GUI thread."""
        self.is_running = False
        self._set_buttons_state(running=False)
        self._set_status(
            "STOPPED",
            f"Typing stopped ({reason}).",
            self.danger_color
        )
        if self.minimize_var.get():
            self._restore_window()

    def _restore_window(self):
        """Restore and bring the application window back to foreground."""
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(300, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception as e:
            print(f"[Restore Window Warning] {e}")

    # -----------------------------------------------------------------
    # Emergency Stop Global Hotkey
    # -----------------------------------------------------------------
    def _start_global_hotkey_listener(self):
        """Listen globally for F8 or Esc to halt typing immediately."""
        def on_press(key):
            try:
                if key in (Key.f8, Key.esc):
                    if self.is_running:
                        key_name = getattr(key, "name", "HOTKEY").upper()
                        # Immediately flag stop
                        self.stop_reason = f"Emergency Hotkey ({key_name})"
                        self.stop_event.set()
                        self._release_all_modifiers()
            except Exception:
                pass

        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def _release_all_modifiers(self):
        """Release modifier keys to avoid keyboard state lock."""
        for mod in (Key.ctrl, Key.shift, Key.alt, Key.cmd):
            try:
                self.keyboard.release(mod)
            except Exception:
                pass

    # -----------------------------------------------------------------
    # Typing Execution Logic
    # -----------------------------------------------------------------
    def start_typing(self):
        """Validate input and spawn typing background thread."""
        if self.is_running:
            return

        text = self.text_area.get("1.0", "end-1c")
        if not text:
            messagebox.showwarning("No Text", "Please paste or enter some text to type before starting.")
            return

        try:
            start_delay = int(self.spin_delay.get())
            if start_delay < 1:
                start_delay = 1
        except ValueError:
            start_delay = 5
            self.spin_delay.set(5)

        base_delay_ms = float(self.speed_slider.get())
        base_delay = max(0.005, base_delay_ms / 1000.0)
        randomize = self.randomize_var.get()
        auto_minimize = self.minimize_var.get()

        # Update application state and button visuals
        self.is_running = True
        self.stop_event.clear()
        self.stop_reason = None
        self._set_buttons_state(running=True)

        self.progress_bar["value"] = 0
        self.lbl_progress_pct.config(text="0%")

        # Launch typing thread
        self.typing_thread = threading.Thread(
            target=self._typing_worker,
            args=(text, base_delay, randomize, start_delay, auto_minimize),
            daemon=True
        )
        self.typing_thread.start()

    def stop_typing(self, source: str = "User"):
        """Abort typing process on request."""
        if self.is_running:
            self.stop_reason = source
            self.stop_event.set()
            self._release_all_modifiers()

    def _typing_worker(self, text: str, base_delay: float, randomize: bool, start_delay: int, auto_minimize: bool):
        """Background thread executing countdown and keystroke simulation."""
        total_chars = len(text)

        # Auto-minimize window if enabled to reveal the target window
        if auto_minimize:
            self.msg_queue.put(("minimize", None))

        # 1. Countdown Phase
        for remaining in range(start_delay, 0, -1):
            if self.stop_event.is_set():
                reason = self.stop_reason or "Stopped during countdown"
                self.msg_queue.put(("stopped", reason))
                return

            status_msg = f"Starting in {remaining}s... Click your target window now! (Press F8/Esc to abort)"
            self.msg_queue.put((
                "status",
                (f"COUNTDOWN ({remaining}s)", status_msg, "#b06000")
            ))

            # Wait 1.0 second in the worker thread (wakes immediately if stop_event is set)
            if self.stop_event.wait(1.0):
                reason = self.stop_reason or "Stopped during countdown"
                self.msg_queue.put(("stopped", reason))
                return

        if self.stop_event.is_set():
            reason = self.stop_reason or "Stopped before typing"
            self.msg_queue.put(("stopped", reason))
            return

        # 2. Typing Phase
        self.msg_queue.put((
            "status",
            ("TYPING", f"Typing: 0 / {total_chars:,} characters (0%)", self.primary_color)
        ))

        update_interval = 1 if total_chars < 300 else max(1, total_chars // 100)
        typed_count = 0

        for idx, char in enumerate(text):
            if self.stop_event.is_set():
                reason = self.stop_reason or f"Stopped at {typed_count:,} of {total_chars:,} characters"
                self.msg_queue.put(("stopped", reason))
                return

            # Simulate the character keystroke
            self._type_character(char)
            typed_count += 1

            # Compute realistic delay
            delay = self._calculate_delay(char, base_delay, randomize)

            # Update progress smoothly without choking Tkinter event queue
            if typed_count % update_interval == 0 or typed_count == total_chars:
                pct = (typed_count / total_chars) * 100.0
                msg = f"Typing: {typed_count:,} / {total_chars:,} characters ({pct:.0f}%)"
                self.msg_queue.put(("progress", (typed_count, total_chars, pct, msg)))

            # Wait for keystroke delay (wakes immediately if stop_event is set)
            if self.stop_event.wait(delay):
                reason = self.stop_reason or f"Stopped at {typed_count:,} of {total_chars:,} characters"
                self.msg_queue.put(("stopped", reason))
                return

        # 3. Finished Successfully
        self.msg_queue.put(("finished", total_chars))

    def _type_character(self, char: str):
        """
        Simulate typing an individual character.
        Handles newlines, tabs, standard characters, and falls back to
        clipboard paste for complex unicode or unsupported symbols.
        """
        # Carriage return alone (from Windows CRLF) is skipped
        if char == '\r':
            return

        # Newline maps to Enter key
        if char == '\n':
            self.keyboard.press(Key.enter)
            self.keyboard.release(Key.enter)
            return

        # Tab maps to Tab key
        if char == '\t':
            self.keyboard.press(Key.tab)
            self.keyboard.release(Key.tab)
            return

        # Standard typing via pynput controller
        try:
            self.keyboard.type(char)
        except Exception:
            # Clipboard fallback for characters not directly supported by current keyboard layout
            self._paste_character(char)

    def _paste_character(self, char: str):
        """Fallback mechanism: copies character to clipboard and simulates paste."""
        try:
            pyperclip.copy(char)
            time.sleep(0.01)
            # Use Cmd on macOS, Ctrl on Windows and Linux
            mod = Key.cmd if platform.system() == "Darwin" else Key.ctrl
            with self.keyboard.pressed(mod):
                self.keyboard.press('v')
                self.keyboard.release('v')
            time.sleep(0.01)
        except Exception as err:
            print(f"[Fallback Paste Warning] Could not paste '{char}': {err}")

    def _calculate_delay(self, char: str, base_delay: float, randomize: bool) -> float:
        """Calculate keystroke delay with authentic human-like cadence."""
        if not randomize:
            return base_delay

        # Base gaussian jitter (centered at base_delay, standard deviation ~25%)
        jitter = random.gauss(0, base_delay * 0.25)
        delay = max(0.005, base_delay + jitter)

        # Natural cadence pauses for punctuation & thinking breaks
        if char in ('.', '!', '?'):
            delay += random.uniform(0.14, 0.32)  # Sentence ending pause
        elif char in (',', ';', ':', '—', '-'):
            delay += random.uniform(0.06, 0.16)  # Clause pause
        elif char == '\n':
            delay += random.uniform(0.18, 0.38)  # New line / paragraph pause
        elif char == ' ':
            delay += random.uniform(0.01, 0.04)  # Space bar cadence
        elif random.random() < 0.03:
            delay += random.uniform(0.08, 0.22)  # 3% chance of brief hesitation

        return delay

    def _on_closing(self):
        """Cleanly handle application window closing."""
        if self.is_running:
            self.stop_typing(source="Window closed")

        if self._queue_poll_job is not None:
            try:
                self.root.after_cancel(self._queue_poll_job)
            except Exception:
                pass

        if hasattr(self, "hotkey_listener") and self.hotkey_listener.is_alive():
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass

        self.root.destroy()


# ==============================================================================
# Application Entry Point
# ==============================================================================
def main():
    root = tk.Tk()
    app = TypingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
