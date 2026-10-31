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
- Large multi-line code/text editor with 4-space tab stops and 2D scrollbars (No-wrap).
- Code Mode: Types indentation using the Tab key (Key.tab) with smart space mapping.
- Smart IDE Mode: Accounts for VS Code/IDE auto-indent to eliminate double indentation
  without ever deleting or collapsing lines.
- Clean Line Separation: Guarantees every single line stays on its own line.
- True-to-source Clipboard Paste: Preserves exact indentation, tabs, and line endings.
- In-editor Tab key support: Pressing Tab inserts a tab instead of losing focus.
- Quick toolbar buttons for "Spaces ➔ Tabs" and "Tabs ➔ Spaces".
- Prominent Start and Stop buttons (toolbar + pinned bottom bar) with hotkeys (F6, Ctrl+Enter).
- Keystroke delay slider (speed control) showing delay in ms and chars/second.
- "Humanize speed" option with natural delay jitter and punctuation cadence.
- Configurable countdown delay before typing starts so you can switch windows.
- Optional window auto-minimize during typing and auto-restore when finished.
- Global emergency stop hotkey (F8) that works even when unfocused.
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
from tkinter import ttk, messagebox, font
from typing import Optional, Tuple, Any

import pyperclip
from pynput import keyboard
from pynput.keyboard import Controller, Key


class TypingApp:
    """Main desktop application class for the Auto Typer simulator."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Typer - Code & Text Keyboard Simulator")
        self.root.geometry("920x720")
        self.root.minsize(720, 560)

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

        # Start global emergency stop listener (F8)
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
        self.style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#1a1a1a")
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
        header_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        lbl_title = ttk.Label(title_box, text="⌨️ Human Auto Typer (Coding & Text)", style="Header.TLabel")
        lbl_title.pack(anchor=tk.W)

        lbl_subtitle = ttk.Label(
            title_box,
            text="Simulate realistic keystrokes & clean lines with exact Tab indentation",
            style="SubHeader.TLabel"
        )
        lbl_subtitle.pack(anchor=tk.W)

        # Emergency Stop Badge in top right
        hotkey_badge = ttk.Label(
            header_frame,
            text="Emergency Stop: F8",
            style="Badge.TLabel",
            relief=tk.GROOVE
        )
        hotkey_badge.pack(side=tk.RIGHT, pady=2)

        # -------------------------------------------------------------
        # 2. Action Buttons (Pinned to the Very Bottom)
        # -------------------------------------------------------------
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))

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
            text="⏹  STOP TYPING  (F8)",
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
            text="Ready. Paste your code, configure options, and click 'Start Typing'.",
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
        # 4. Coding & Indentation Settings (Pinned above status)
        # -------------------------------------------------------------
        coding_group = ttk.LabelFrame(main_container, text=" 💻 Coding & Indentation Settings ", padding="8")
        coding_group.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 6))

        code_opts_row1 = ttk.Frame(coding_group)
        code_opts_row1.pack(fill=tk.X, pady=(0, 3))

        self.code_mode_var = tk.BooleanVar(value=True)
        chk_code_mode = ttk.Checkbutton(
            code_opts_row1,
            text="Code Mode: Smart IDE Indentation (Optimized for VS Code, Cursor, PyCharm)",
            variable=self.code_mode_var
        )
        chk_code_mode.pack(side=tk.LEFT, padx=(0, 14))

        self.dismiss_autocomplete_var = tk.BooleanVar(value=True)
        chk_dismiss = ttk.Checkbutton(
            code_opts_row1,
            text="Dismiss Autocomplete (Esc before Enter prevents unwanted completions)",
            variable=self.dismiss_autocomplete_var
        )
        chk_dismiss.pack(side=tk.LEFT, padx=(0, 14))

        self.wrap_var = tk.BooleanVar(value=False)
        chk_wrap = ttk.Checkbutton(
            code_opts_row1,
            text="Wrap lines",
            variable=self.wrap_var,
            command=self._on_wrap_toggle
        )
        chk_wrap.pack(side=tk.RIGHT)

        code_opts_row2 = ttk.Frame(coding_group)
        code_opts_row2.pack(fill=tk.X, pady=(2, 0))

        self.use_tab_key_var = tk.BooleanVar(value=True)
        chk_tab_key = ttk.Checkbutton(
            code_opts_row2,
            text="Use Tab key (Key.tab) for indenting",
            variable=self.use_tab_key_var
        )
        chk_tab_key.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(code_opts_row2, text="Spaces per Tab:").pack(side=tk.LEFT)
        self.spin_spaces_per_tab = ttk.Spinbox(code_opts_row2, from_=2, to=8, increment=2, width=3)
        self.spin_spaces_per_tab.set(4)
        self.spin_spaces_per_tab.pack(side=tk.LEFT, padx=4)

        ttk.Label(code_opts_row2, text="spaces  (4 spaces = 1 Tab)", style="Stats.TLabel").pack(side=tk.LEFT, padx=(2, 0))

        ttk.Label(code_opts_row2, text="💡 Turn Code Mode OFF for plain text/Notepad", style="Stats.TLabel").pack(side=tk.RIGHT)

        # -------------------------------------------------------------
        # 5. Speed & General Options (Pinned above coding settings)
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
        slider_row.pack(fill=tk.X, pady=(0, 4))

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

        # General Options Row
        opts_row = ttk.Frame(settings_group)
        opts_row.pack(fill=tk.X, pady=(2, 0))

        self.randomize_var = tk.BooleanVar(value=True)
        chk_random = ttk.Checkbutton(
            opts_row,
            text="Humanize speed (random jitter & natural pauses)",
            variable=self.randomize_var
        )
        chk_random.pack(side=tk.LEFT, padx=(0, 10))

        self.minimize_var = tk.BooleanVar(value=True)
        chk_minimize = ttk.Checkbutton(
            opts_row,
            text="Minimize window during typing (restores on finish)",
            variable=self.minimize_var
        )
        chk_minimize.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(opts_row, text="Start Countdown:").pack(side=tk.LEFT)
        self.spin_delay = ttk.Spinbox(opts_row, from_=1, to=30, width=3)
        self.spin_delay.set(5)
        self.spin_delay.pack(side=tk.LEFT, padx=4)
        ttk.Label(opts_row, text="s").pack(side=tk.LEFT)

        # -------------------------------------------------------------
        # 6. Text / Code Input Area (Expands to fill all remaining vertical space)
        # -------------------------------------------------------------
        text_group = ttk.LabelFrame(main_container, text=" Code / Text to Type ", padding="8")
        text_group.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 6))

        # Toolbar above the text area
        text_toolbar = ttk.Frame(text_group)
        text_toolbar.pack(fill=tk.X, pady=(0, 6))

        # Quick Start button right in the toolbar
        self.btn_start_top = tk.Button(
            text_toolbar,
            text="▶ Start",
            font=("Segoe UI", 9, "bold"),
            bg="#107c10",
            fg="#ffffff",
            activebackground="#0b5a0b",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            bd=1,
            cursor="hand2",
            padx=8,
            pady=1,
            command=self.start_typing
        )
        self.btn_start_top.pack(side=tk.LEFT, padx=(0, 5))

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
            pady=1,
            state=tk.DISABLED,
            command=lambda: self.stop_typing(source="Stop button")
        )
        self.btn_stop_top.pack(side=tk.LEFT, padx=(0, 8))

        btn_paste = ttk.Button(text_toolbar, text="📋 Paste", command=self._paste_clipboard)
        btn_paste.pack(side=tk.LEFT, padx=(0, 5))

        btn_detect = ttk.Button(text_toolbar, text="🪄 Auto-Detect Indent", command=lambda: self.auto_detect_indent(silent=False))
        btn_detect.pack(side=tk.LEFT, padx=(0, 5))

        btn_clear = ttk.Button(text_toolbar, text="🗑️ Clear", command=self._clear_text)
        btn_clear.pack(side=tk.LEFT, padx=(0, 5))

        btn_reset = ttk.Button(text_toolbar, text="🔄 Reset All", command=self.reset_all)
        btn_reset.pack(side=tk.LEFT, padx=(0, 5))

        self.lbl_text_stats = ttk.Label(text_toolbar, text="0 characters | 0 lines", style="Stats.TLabel")
        self.lbl_text_stats.pack(side=tk.RIGHT, padx=4)

        # Text Box with 2D Scrollbars (Horizontal + Vertical)
        text_container = ttk.Frame(text_group)
        text_container.pack(fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(text_container, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        h_scroll = ttk.Scrollbar(text_container, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure font and exact 4-space tab stop in pixels
        self.code_font = font.Font(family="Consolas", size=10)
        tab_px = self.code_font.measure("    ")  # Exactly 4 spaces width in pixels

        self.text_area = tk.Text(
            text_container,
            wrap=tk.NONE,  # Preserves code indentation perfectly without wrapping lines
            undo=True,
            height=10,
            tabs=(tab_px,),
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set,
            font=self.code_font,
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
        h_scroll.config(command=self.text_area.xview)

        # Keybindings for coding & tab key handling inside text box
        self.text_area.bind("<KeyRelease>", lambda e: self._update_stats())
        self.text_area.bind("<Control-a>", self._select_all_text)
        self.text_area.bind("<Control-A>", self._select_all_text)
        self.text_area.bind("<Control-v>", self._handle_paste_event)
        self.text_area.bind("<Control-V>", self._handle_paste_event)
        self.text_area.bind("<<Paste>>", self._handle_paste_event)

        # Tab & Shift+Tab handling inside the text box (keeps focus & indents)
        self.text_area.bind("<Tab>", self._on_text_tab_press)
        self.text_area.bind("<Shift-Tab>", self._on_text_shift_tab_press)
        self.text_area.bind("<ISO_Left_Tab>", self._on_text_shift_tab_press)

        self._setup_context_menu()

    # -----------------------------------------------------------------
    # UI Helper Methods & Event Handlers
    # -----------------------------------------------------------------
    def _on_wrap_toggle(self):
        """Toggle text box wrapping mode between NONE (code) and WORD."""
        if self.wrap_var.get():
            self.text_area.config(wrap=tk.WORD)
        else:
            self.text_area.config(wrap=tk.NONE)

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
        self.context_menu.add_command(label="Paste (Preserve Indent)", command=self._paste_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=self._select_all_text)
        self.context_menu.add_command(label="Clear", command=self._clear_text)
        self.context_menu.add_command(label="Reset Everything", command=self.reset_all)

        self.text_area.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        """Display the context menu at mouse position."""
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _select_all_text(self, event=None):
        """Select all text inside the text widget."""
        self.text_area.tag_add("sel", "1.0", "end")
        return "break"

    def _on_text_tab_press(self, event):
        """Insert a tab or indent selected lines without losing focus."""
        if self.text_area.tag_ranges("sel"):
            self._indent_selection()
        else:
            self.text_area.insert(tk.INSERT, "\t")
        self._update_stats()
        return "break"

    def _on_text_shift_tab_press(self, event):
        """Unindent current line or selected block."""
        self._unindent_selection()
        self._update_stats()
        return "break"

    def _indent_selection(self):
        """Indent all lines in current selection with a Tab."""
        try:
            start = self.text_area.index("sel.first linestart")
            end = self.text_area.index("sel.last linestart")
            cur = start
            while self.text_area.compare(cur, "<=", end):
                self.text_area.insert(cur, "\t")
                cur = self.text_area.index(f"{cur} + 1 line linestart")
        except Exception:
            pass

    def _unindent_selection(self):
        """Unindent all lines in current selection by 1 Tab or 4 spaces."""
        try:
            if self.text_area.tag_ranges("sel"):
                start = self.text_area.index("sel.first linestart")
                end = self.text_area.index("sel.last linestart")
            else:
                start = self.text_area.index("insert linestart")
                end = start

            cur = start
            sp_tab = self._get_spaces_per_tab()
            while self.text_area.compare(cur, "<=", end):
                line_text = self.text_area.get(cur, f"{cur} lineend")
                if line_text.startswith("\t"):
                    self.text_area.delete(cur, f"{cur} + 1 chars")
                elif line_text.startswith(" " * sp_tab):
                    self.text_area.delete(cur, f"{cur} + {sp_tab} chars")
                elif line_text.startswith(" "):
                    leading_spaces = len(line_text) - len(line_text.lstrip(" "))
                    remove_count = min(sp_tab, leading_spaces)
                    if remove_count > 0:
                        self.text_area.delete(cur, f"{cur} + {remove_count} chars")
                cur = self.text_area.index(f"{cur} + 1 line linestart")
        except Exception:
            pass

    def _set_preset(self, spaces: int, use_tab: bool):
        """Set language indentation preset (e.g. Python 4 spaces or JS 2 spaces)."""
        self.spin_spaces_per_tab.set(spaces)
        self.use_tab_key_var.set(use_tab)
        self._set_status("PRESET", f"Applied {spaces}-space indentation preset.", self.primary_color)

    def auto_detect_indent(self, silent: bool = False):
        """Analyze code in editor and automatically configure spaces per tab."""
        raw = self.text_area.get("1.0", "end-1c")
        if not raw.strip():
            if not silent:
                messagebox.showinfo("Auto-Detect", "No code in editor to analyze. Paste your code first!")
            return

        lines = raw.splitlines()
        space_counts = {2: 0, 4: 0}
        tab_count = 0
        for line in lines:
            leading = line[:len(line) - len(line.lstrip(" \t"))]
            if not leading:
                continue
            if leading.startswith("\t"):
                tab_count += 1
            else:
                sp = len(leading)
                if sp % 4 == 0:
                    space_counts[4] += 1
                elif sp % 2 == 0:
                    space_counts[2] += 1

        if tab_count > (space_counts[2] + space_counts[4]):
            self.spin_spaces_per_tab.set(4)
            self.use_tab_key_var.set(True)
            msg = "Detected Tab indentation. Configured Tab mode."
        elif space_counts[2] > space_counts[4]:
            self.spin_spaces_per_tab.set(2)
            msg = "Detected 2-space indentation (JS/Web/React). Configured 2 spaces."
        else:
            self.spin_spaces_per_tab.set(4)
            msg = "Detected 4-space indentation (Python/Java/C++). Configured 4 spaces."

        if not silent:
            self._set_status("AUTO-DETECT", msg, self.success_color)

    def _get_spaces_per_tab(self) -> int:
        """Get the current spaces per tab setting."""
        try:
            val = int(self.spin_spaces_per_tab.get())
            return max(1, min(16, val))
        except Exception:
            return 4

    def _handle_paste_event(self, event=None):
        """Paste clipboard content preserving exact formatting and indentation."""
        self._paste_clipboard()
        return "break"

    def _paste_clipboard(self):
        """Paste clipboard content into the text area with clean normalization."""
        try:
            content = pyperclip.paste()
            if content:
                # Normalize CRLF to \n while keeping exact tabs and indentation intact
                content = content.replace("\r\n", "\n").replace("\r", "\n")
                if self.text_area.tag_ranges("sel"):
                    self.text_area.delete("sel.first", "sel.last")
                self.text_area.insert(tk.INSERT, content)
                self._update_stats()
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Could not paste clipboard content:\n{e}")

    def _clear_text(self):
        """Clear the text area."""
        self.text_area.delete("1.0", tk.END)
        self._update_stats()

    def reset_all(self):
        """Reset text, all settings, speed, progress, and state back to defaults."""
        # Confirm with user if there is content in the text box
        has_text = bool(self.text_area.get("1.0", "end-1c").strip())
        if has_text:
            if not messagebox.askyesno("Reset Everything", "Are you sure you want to reset all text, settings, and progress to default?"):
                return

        # 1. Stop any active typing session safely
        if self.is_running:
            self.stop_typing(source="Reset All")

        # 2. Clear text box
        self.text_area.delete("1.0", tk.END)

        # 3. Reset Typing Speed & Options to defaults
        self.speed_slider.set(45)
        self._on_speed_slider_change(45)
        self.randomize_var.set(True)
        self.minimize_var.set(True)
        self.spin_delay.set(5)

        # 4. Reset Coding & Indentation Settings to defaults
        self.code_mode_var.set(True)
        self.dismiss_autocomplete_var.set(True)
        self.use_tab_key_var.set(True)
        self.spin_spaces_per_tab.set(4)
        self.wrap_var.set(False)
        self.text_area.config(wrap=tk.NONE)

        # 5. Reset Progress and Status
        self.progress_bar["value"] = 0
        self.lbl_progress_pct.config(text="0%")
        self._set_status(
            "IDLE",
            "Reset complete. All settings and text restored to default.",
            self.subtext_color
        )

        # 6. Reset Buttons State
        self._set_buttons_state(running=False)

        # 7. Update Stats
        self._update_stats()

    def _update_stats(self):
        """Update live character and line count labels."""
        raw_text = self.text_area.get("1.0", "end-1c")
        chars = len(raw_text)
        lines = len(raw_text.splitlines()) if raw_text else 0
        self.lbl_text_stats.config(text=f"{chars:,} characters | {lines:,} lines")

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
        """Listen globally for F8 to halt typing immediately (Esc excluded to avoid simulated key conflict)."""
        def on_press(key):
            try:
                if key == Key.f8:
                    if self.is_running:
                        self.stop_reason = "Emergency Hotkey (F8)"
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
            messagebox.showwarning("No Text", "Please paste or enter some code/text to type before starting.")
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

        code_mode = self.code_mode_var.get()
        dismiss_autocomplete = self.dismiss_autocomplete_var.get()
        use_tab_key = self.use_tab_key_var.get()
        spaces_per_tab = self._get_spaces_per_tab()

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
            args=(text, base_delay, randomize, start_delay, auto_minimize, code_mode, dismiss_autocomplete, use_tab_key, spaces_per_tab),
            daemon=True
        )
        self.typing_thread.start()

    def stop_typing(self, source: str = "User"):
        """Abort typing process on request."""
        if self.is_running:
            self.stop_reason = source
            self.stop_event.set()
            self._release_all_modifiers()

    @staticmethod
    def _measure_indent_spaces(line: str, spaces_per_tab: int) -> int:
        """Measure the leading indentation of a line in equivalent spaces."""
        leading_len = len(line) - len(line.lstrip(" \t"))
        leading = line[:leading_len]
        total = 0
        for ch in leading:
            if ch == "\t":
                total += spaces_per_tab
            elif ch == " ":
                total += 1
        return total

    @staticmethod
    def _is_block_opener(line_text: str) -> bool:
        """
        Check if a code line triggers auto-indent on newline in modern IDEs.
        Handles Python (':'), C/C++/Java/JS/TS/PHP/Rust/Go ('{', '(', '[').
        Strips inline comments cleanly before checking.
        """
        stripped = line_text.strip()
        if not stripped:
            return False

        if "#" in stripped:
            parts = stripped.split("#", 1)
            left = parts[0].rstrip()
            if left:
                double_quotes = left.count('"')
                single_quotes = left.count("'")
                if double_quotes % 2 == 0 and single_quotes % 2 == 0:
                    stripped = left

        if "//" in stripped:
            parts = stripped.split("//", 1)
            left = parts[0].rstrip()
            if left:
                double_quotes = left.count('"')
                single_quotes = left.count("'")
                if double_quotes % 2 == 0 and single_quotes % 2 == 0:
                    stripped = left

        stripped = stripped.rstrip()
        return stripped.endswith((":", "{", "(", "["))

    def _type_indent_diff(
        self,
        diff: int,
        spaces_per_tab: int,
        use_tab_key: bool,
        base_delay: float
    ) -> int:
        """Type extra indentation spaces or tabs when diff > 0. Returns typed character count."""
        typed = 0
        if diff <= 0:
            return typed

        if use_tab_key and spaces_per_tab > 0:
            tabs = diff // spaces_per_tab
            rem_spaces = diff % spaces_per_tab
            for _ in range(tabs):
                if self.stop_event.is_set():
                    return typed
                self.keyboard.press(Key.tab)
                self.keyboard.release(Key.tab)
                typed += spaces_per_tab
                time.sleep(max(0.015, base_delay * 0.7))
            for _ in range(rem_spaces):
                if self.stop_event.is_set():
                    return typed
                self.keyboard.press(" ")
                self.keyboard.release(" ")
                typed += 1
                time.sleep(max(0.015, base_delay * 0.7))
        else:
            for _ in range(diff):
                if self.stop_event.is_set():
                    return typed
                self.keyboard.press(" ")
                self.keyboard.release(" ")
                typed += 1
                time.sleep(max(0.015, base_delay * 0.7))

        return typed

    def _typing_worker(
        self,
        text: str,
        base_delay: float,
        randomize: bool,
        start_delay: int,
        auto_minimize: bool,
        code_mode: bool,
        dismiss_autocomplete: bool,
        use_tab_key: bool,
        spaces_per_tab: int
    ):
        """
        Background thread executing countdown and keystroke simulation.
        - Code Mode ON: Smart IDE Indentation Tracking for VS Code/IDEs eliminates double indenting.
        - Code Mode OFF: Verbatim typing (types whatever is in the window exactly as it is).
        """
        clean_text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = clean_text.split("\n")
        total_lines = len(lines)
        total_chars = max(1, len(clean_text))
        typed_count = 0

        # Auto-minimize window if enabled
        if auto_minimize:
            self.msg_queue.put(("minimize", None))

        # 1. Countdown Phase
        for remaining in range(start_delay, 0, -1):
            if self.stop_event.is_set():
                reason = self.stop_reason or "Stopped during countdown"
                self.msg_queue.put(("stopped", reason))
                return

            status_msg = f"Starting in {remaining}s... Click into your target code editor! (Press F8 to abort)"
            self.msg_queue.put((
                "status",
                (f"COUNTDOWN ({remaining}s)", status_msg, "#b06000")
            ))

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
            ("TYPING", f"Typing: Line 1 / {total_lines} (0%)", self.primary_color)
        ))

        if not code_mode:
            # ==================================================================
            # Plain Text / Verbatim Mode: Types exactly whatever is in window
            # ==================================================================
            for line_idx, line in enumerate(lines):
                if self.stop_event.is_set():
                    reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                    self.msg_queue.put(("stopped", reason))
                    return

                if line_idx > 0:
                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)
                    typed_count += 1
                    enter_pause = max(0.05, base_delay * 1.3)
                    if randomize:
                        enter_pause += random.uniform(0.02, 0.08)
                    if self.stop_event.wait(enter_pause):
                        reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                        self.msg_queue.put(("stopped", reason))
                        return

                for char in line:
                    if self.stop_event.is_set():
                        reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                        self.msg_queue.put(("stopped", reason))
                        return
                    self._type_character(char)
                    typed_count += 1
                    delay = self._calculate_delay(char, base_delay, randomize)
                    pct = min(100.0, (typed_count / total_chars) * 100.0)
                    msg = f"Typing Line {line_idx+1} / {total_lines} ({pct:.0f}%)"
                    self.msg_queue.put(("progress", (typed_count, total_chars, pct, msg)))
                    if self.stop_event.wait(delay):
                        reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                        self.msg_queue.put(("stopped", reason))
                        return
        else:
            # ==================================================================
            # Code Mode (Smart IDE Indentation Tracking for VS Code / IDEs)
            # ==================================================================
            current_indent = 0
            last_block_opener = False

            for line_idx, line in enumerate(lines):
                if self.stop_event.is_set():
                    reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                    self.msg_queue.put(("stopped", reason))
                    return

                if line_idx > 0:
                    # In IDEs (VS Code, Cursor, PyCharm), dismiss any open IntelliSense / Copilot suggestion popup
                    if dismiss_autocomplete:
                        self.keyboard.press(Key.esc)
                        self.keyboard.release(Key.esc)
                        time.sleep(0.015)

                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)
                    typed_count += 1

                    # Optimized pause after Enter so IDE language server / formatter settles cleanly
                    enter_pause = max(0.06, base_delay * 1.3)
                    if randomize:
                        enter_pause += random.uniform(0.02, 0.08)

                    if self.stop_event.wait(enter_pause):
                        reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                        self.msg_queue.put(("stopped", reason))
                        return

                    # In VS Code/IDEs, pressing Enter after a block opener (: or { or [) indents by 1 level
                    if last_block_opener:
                        current_indent += spaces_per_tab
                        last_block_opener = False
                    # Otherwise, the IDE retains the previous line's indentation

                # Blank line
                if not line:
                    continue

                target_indent = self._measure_indent_spaces(line, spaces_per_tab)
                content = line.lstrip(" \t")

                delta = target_indent - current_indent

                if delta > 0:
                    # Line needs more indentation than editor already has -> type difference
                    typed_count += self._type_indent_diff(delta, spaces_per_tab, use_tab_key, base_delay)
                    current_indent = target_indent
                elif delta < 0:
                    # Line unindents (e.g. after return, pass, or closing a block) -> backspace
                    unindent = abs(delta)
                    num_backspaces = max(1, (unindent + spaces_per_tab - 1) // spaces_per_tab)
                    for _ in range(num_backspaces):
                        if self.stop_event.is_set():
                            reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                            self.msg_queue.put(("stopped", reason))
                            return
                        self.keyboard.press(Key.backspace)
                        self.keyboard.release(Key.backspace)
                        backspace_delay = max(0.02, base_delay * 0.6)
                        if self.stop_event.wait(backspace_delay):
                            reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                            self.msg_queue.put(("stopped", reason))
                            return
                    current_indent = target_indent
                else:
                    # delta == 0: Editor cursor is ALREADY at the exact target indentation!
                    # Do not type extra spaces or tabs!
                    pass

                # Type line content
                for char in content:
                    if self.stop_event.is_set():
                        reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                        self.msg_queue.put(("stopped", reason))
                        return

                    self._type_character(char)
                    typed_count += 1
                    delay = self._calculate_delay(char, base_delay, randomize)

                    pct = min(100.0, (typed_count / total_chars) * 100.0)
                    msg = f"Typing Line {line_idx+1} / {total_lines} ({pct:.0f}%)"
                    self.msg_queue.put(("progress", (typed_count, total_chars, pct, msg)))

                    if self.stop_event.wait(delay):
                        reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                        self.msg_queue.put(("stopped", reason))
                        return

                # Record if this non-empty line opened a block for the next line
                if self._is_block_opener(line):
                    last_block_opener = True
                else:
                    last_block_opener = False

        # 3. Finished Successfully
        self.msg_queue.put(("finished", total_chars))

    def _type_character(self, char: str):
        """
        Simulate typing an individual character.
        Handles newlines, tabs, standard characters, and falls back to
        clipboard paste for complex unicode or unsupported symbols.
        """
        if char == "\r":
            return

        if char == "\n":
            self.keyboard.press(Key.enter)
            self.keyboard.release(Key.enter)
            return

        if char == "\t":
            self.keyboard.press(Key.tab)
            self.keyboard.release(Key.tab)
            return

        # Standard typing via pynput controller
        try:
            self.keyboard.type(char)
        except Exception:
            # Clipboard fallback for characters not directly supported by keyboard layout
            self._paste_character(char)

    def _paste_character(self, char: str):
        """Fallback mechanism: copies character to clipboard and simulates paste."""
        try:
            pyperclip.copy(char)
            time.sleep(0.01)
            # Use Cmd on macOS, Ctrl on Windows and Linux
            mod = Key.cmd if platform.system() == "Darwin" else Key.ctrl
            with self.keyboard.pressed(mod):
                self.keyboard.press("v")
                self.keyboard.release("v")
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
        if char in (".", "!", "?"):
            delay += random.uniform(0.14, 0.30)  # Sentence ending pause
        elif char in (",", ";", ":", "—", "-"):
            delay += random.uniform(0.06, 0.16)  # Clause pause
        elif char == "\n":
            delay += random.uniform(0.16, 0.35)  # Line break pause
        elif char == " ":
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
