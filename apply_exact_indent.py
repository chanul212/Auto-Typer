with open('auto_typer.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update UI
old_ui_block = """        code_opts_row1 = ttk.Frame(coding_group)
        code_opts_row1.pack(fill=tk.X, pady=(0, 3))

        self.smart_ide_var = tk.BooleanVar(value=True)
        chk_smart_ide = ttk.Checkbutton(
            code_opts_row1,
            text="Smart IDE Auto-Indent (Syncs with VS Code / IDEs to eliminate double indenting)",
            variable=self.smart_ide_var
        )
        chk_smart_ide.pack(side=tk.LEFT, padx=(0, 16))

        self.wrap_var = tk.BooleanVar(value=False)
        chk_wrap = ttk.Checkbutton(
            code_opts_row1,
            text="Wrap long lines (leave unchecked for clean code view)",
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
        chk_tab_key.pack(side=tk.LEFT, padx=(0, 16))

        ttk.Label(code_opts_row2, text="Spaces per Tab/Indent:").pack(side=tk.LEFT)
        self.spin_spaces_per_tab = ttk.Spinbox(code_opts_row2, from_=2, to=8, increment=2, width=3)
        self.spin_spaces_per_tab.set(4)
        self.spin_spaces_per_tab.pack(side=tk.LEFT, padx=6)

        ttk.Label(code_opts_row2, text="spaces  (4 spaces = 1 Tab)", style="Stats.TLabel").pack(side=tk.LEFT)"""

new_ui_block = """        code_opts_row1 = ttk.Frame(coding_group)
        code_opts_row1.pack(fill=tk.X, pady=(0, 3))

        self.clean_auto_indent_var = tk.BooleanVar(value=True)
        chk_clean_indent = ttk.Checkbutton(
            code_opts_row1,
            text="Exact Indentation Matching (Wipes editor auto-indent to match window 100%)",
            variable=self.clean_auto_indent_var
        )
        chk_clean_indent.pack(side=tk.LEFT, padx=(0, 16))

        self.wrap_var = tk.BooleanVar(value=False)
        chk_wrap = ttk.Checkbutton(
            code_opts_row1,
            text="Wrap long lines (leave unchecked for clean code view)",
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
        chk_tab_key.pack(side=tk.LEFT, padx=(0, 16))

        ttk.Label(code_opts_row2, text="Spaces per Tab/Indent:").pack(side=tk.LEFT)
        self.spin_spaces_per_tab = ttk.Spinbox(code_opts_row2, from_=2, to=8, increment=2, width=3)
        self.spin_spaces_per_tab.set(4)
        self.spin_spaces_per_tab.pack(side=tk.LEFT, padx=6)

        ttk.Label(code_opts_row2, text="spaces  (4 spaces = 1 Tab)", style="Stats.TLabel").pack(side=tk.LEFT)"""

assert old_ui_block in code, "old_ui_block not found"
code = code.replace(old_ui_block, new_ui_block)

# 2. Update reset_all
old_reset = """        # 4. Reset Coding & Indentation Settings to defaults
        self.smart_ide_var.set(True)
        self.use_tab_key_var.set(True)
        self.spin_spaces_per_tab.set(4)
        self.wrap_var.set(False)
        self.text_area.config(wrap=tk.NONE)"""

new_reset = """        # 4. Reset Coding & Indentation Settings to defaults
        self.clean_auto_indent_var.set(True)
        self.use_tab_key_var.set(True)
        self.spin_spaces_per_tab.set(4)
        self.wrap_var.set(False)
        self.text_area.config(wrap=tk.NONE)"""

assert old_reset in code, "old_reset not found"
code = code.replace(old_reset, new_reset)

# 3. Update start_typing
old_start = """        smart_ide_mode = self.smart_ide_var.get()
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
            args=(text, base_delay, randomize, start_delay, auto_minimize, smart_ide_mode, use_tab_key, spaces_per_tab),
            daemon=True
        )"""

new_start = """        clean_auto_indent = self.clean_auto_indent_var.get()
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
            args=(text, base_delay, randomize, start_delay, auto_minimize, clean_auto_indent, use_tab_key, spaces_per_tab),
            daemon=True
        )"""

assert old_start in code, "old_start not found"
code = code.replace(old_start, new_start)

# 4. Replace helper methods and _typing_worker
old_worker_section = """    @staticmethod
    def _measure_indent_spaces(line: str, spaces_per_tab: int) -> int:
        \"\"\"Measure the leading indentation of a line in equivalent spaces.\"\"\"
        leading_len = len(line) - len(line.lstrip(" \\t"))
        leading = line[:leading_len]
        total = 0
        for ch in leading:
            if ch == "\\t":
                total += spaces_per_tab
            elif ch == " ":
                total += 1
        return total

    @staticmethod
    def _is_block_opener(line_text: str) -> bool:
        \"\"\"
        Check if a code line triggers auto-indent on newline in modern IDEs.
        Handles Python (ending in ':'), C/C++/Java/JS/TS/PHP/Rust (ending in '{', '(', '[').
        Strips inline comments cleanly before checking.
        \"\"\"
        stripped = line_text.strip()
        if not stripped:
            return False

        # Strip Python/Bash style comments (#) unless part of a string
        if "#" in stripped:
            parts = stripped.split("#", 1)
            left = parts[0].rstrip()
            if left:
                double_quotes = left.count('"')
                single_quotes = left.count("'")
                if double_quotes % 2 == 0 and single_quotes % 2 == 0:
                    stripped = left

        # Strip C-style comments (//)
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

    def _apply_indent_delta(
        self,
        delta: int,
        spaces_per_tab: int,
        use_tab_key: bool,
        base_delay: float
    ) -> int:
        \"\"\"Type extra indentation spaces or tabs when delta > 0. Returns typed character count.\"\"\"
        typed = 0
        if delta <= 0:
            return typed

        if use_tab_key and spaces_per_tab > 0:
            tabs = delta // spaces_per_tab
            rem_spaces = delta % spaces_per_tab
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
            for _ in range(delta):
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
        smart_ide_mode: bool,
        use_tab_key: bool,
        spaces_per_tab: int
    ):
        \"\"\"
        Background thread executing countdown and keystroke simulation.
        Smart IDE Mode eliminates double indentation by calculating IDE auto-indentation
        and sending exact deltas / backspaces so code matches source window with 100% precision.
        \"\"\"
        # Normalize newlines to ensure clean splitting
        clean_text = text.replace("\\r\\n", "\\n").replace("\\r", "\\n")
        lines = clean_text.split("\\n")
        total_lines = len(lines)
        total_chars = max(1, len(clean_text))
        typed_count = 0

        # Auto-minimize window if enabled to reveal the target window
        if auto_minimize:
            self.msg_queue.put(("minimize", None))

        # 1. Countdown Phase
        for remaining in range(start_delay, 0, -1):
            if self.stop_event.is_set():
                reason = self.stop_reason or "Stopped during countdown"
                self.msg_queue.put(("stopped", reason))
                return

            status_msg = f"Starting in {remaining}s... Click into your target code editor! (Press F8/Esc to abort)"
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

        # Indentation tracking for Smart IDE Mode
        current_editor_indent = 0
        block_opener_pending = False

        for line_idx, line in enumerate(lines):
            if self.stop_event.is_set():
                reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                self.msg_queue.put(("stopped", reason))
                return

            # Press Enter to create a new line cleanly for lines after the first
            if line_idx > 0:
                self.keyboard.press(Key.enter)
                self.keyboard.release(Key.enter)
                typed_count += 1

                # Clean pause after Enter so target editor registers the newline cleanly
                enter_pause = max(0.06, base_delay * 1.4)
                if randomize:
                    enter_pause += random.uniform(0.03, 0.10)

                if self.stop_event.wait(enter_pause):
                    reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                    self.msg_queue.put(("stopped", reason))
                    return

                # If the previous line opened a block (: or {), the IDE auto-indents by 1 level
                if smart_ide_mode:
                    if block_opener_pending:
                        current_editor_indent += spaces_per_tab
                        block_opener_pending = False

            # If the line is empty (blank line), nothing to type on it
            if not line:
                continue

            target_indent = self._measure_indent_spaces(line, spaces_per_tab)
            content = line.lstrip(" \\t")

            # Handle Indentation
            if smart_ide_mode:
                delta = target_indent - current_editor_indent

                if delta > 0:
                    # Line needs more indentation than IDE automatically provided
                    typed_count += self._apply_indent_delta(delta, spaces_per_tab, use_tab_key, base_delay)
                    current_editor_indent = target_indent
                elif delta < 0:
                    # Line unindents (e.g. after return, pass, or closing a block)
                    unindent_spaces = abs(delta)
                    # In code editors, 1 Backspace at indent deletes 1 tab stop (spaces_per_tab)
                    num_backspaces = max(1, (unindent_spaces + spaces_per_tab - 1) // spaces_per_tab)
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
                    current_editor_indent = target_indent
                else:
                    # delta == 0: Target editor cursor is ALREADY at the EXACT indentation!
                    # Do not type extra spaces or tabs.
                    pass

            else:
                # Raw Mode (for plain text / Notepad): Type full indentation from column 0
                if target_indent > 0:
                    typed_count += self._apply_indent_delta(target_indent, spaces_per_tab, use_tab_key, base_delay)

            # Type line content character by character
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

            # Check if this non-empty line opened a block (: or {) for subsequent lines
            if smart_ide_mode:
                if self._is_block_opener(line):
                    block_opener_pending = True
                else:
                    block_opener_pending = False

        # 3. Finished Successfully
        self.msg_queue.put(("finished", total_chars))"""

new_worker_section = """    def _type_indentation(
        self,
        leading: str,
        spaces_per_tab: int,
        use_tab_key: bool,
        base_delay: float
    ) -> int:
        \"\"\"
        Type the exact leading indentation from the source line.
        If use_tab_key is True, converts each spaces_per_tab spaces into 1 Tab keypress.
        Otherwise types literal spaces and tabs.
        \"\"\"
        typed = 0
        if not leading:
            return typed

        if use_tab_key and spaces_per_tab > 0:
            total_spaces = 0
            for ch in leading:
                if ch == "\\t":
                    total_spaces += spaces_per_tab
                elif ch == " ":
                    total_spaces += 1

            tabs = total_spaces // spaces_per_tab
            rem_spaces = total_spaces % spaces_per_tab

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
            for ch in leading:
                if self.stop_event.is_set():
                    return typed
                if ch == "\\t":
                    self.keyboard.press(Key.tab)
                    self.keyboard.release(Key.tab)
                    typed += spaces_per_tab
                elif ch == " ":
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
        clean_auto_indent: bool,
        use_tab_key: bool,
        spaces_per_tab: int
    ):
        \"\"\"
        Background thread executing countdown and keystroke simulation.
        Exact Indentation Matching: On every new line, wipes any editor-inserted auto-indent
        back to column 0, then types the source line's exact indentation and code content.
        Guarantees 100% identical layout to the Auto Typer window in ANY editor.
        \"\"\"
        clean_text = text.replace("\\r\\n", "\\n").replace("\\r", "\\n")
        lines = clean_text.split("\\n")
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

            status_msg = f"Starting in {remaining}s... Click into your target code editor! (Press F8/Esc to abort)"
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

        for line_idx, line in enumerate(lines):
            if self.stop_event.is_set():
                reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                self.msg_queue.put(("stopped", reason))
                return

            # Press Enter cleanly for lines after the first
            if line_idx > 0:
                self.keyboard.press(Key.enter)
                self.keyboard.release(Key.enter)
                typed_count += 1

                enter_pause = max(0.06, base_delay * 1.3)
                if randomize:
                    enter_pause += random.uniform(0.02, 0.08)

                if self.stop_event.wait(enter_pause):
                    reason = self.stop_reason or f"Stopped at line {line_idx+1} of {total_lines}"
                    self.msg_queue.put(("stopped", reason))
                    return

                # Clean any editor auto-indentation on the fresh line so cursor is at column 0
                if clean_auto_indent:
                    # Select from cursor to column 0
                    with self.keyboard.pressed(Key.shift):
                        self.keyboard.press(Key.home)
                        self.keyboard.release(Key.home)
                        self.keyboard.press(Key.home)
                        self.keyboard.release(Key.home)
                    time.sleep(0.015)
                    # Replace selection with space
                    self.keyboard.press(" ")
                    self.keyboard.release(" ")
                    time.sleep(0.015)
                    # Delete the space (leaves cursor at col 0 without touching previous line)
                    self.keyboard.press(Key.backspace)
                    self.keyboard.release(Key.backspace)
                    time.sleep(0.015)

            # If the line is empty (blank line), nothing to type on it
            if not line:
                continue

            # Separate leading indentation from content
            leading_len = len(line) - len(line.lstrip(" \\t"))
            leading = line[:leading_len]
            content = line[leading_len:]

            # Type exact indentation from column 0
            if leading:
                typed_count += self._type_indentation(leading, spaces_per_tab, use_tab_key, base_delay)

            # Type line content character by character
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

        # 3. Finished Successfully
        self.msg_queue.put(("finished", total_chars))"""

assert old_worker_section in code, "old_worker_section not found"
code = code.replace(old_worker_section, new_worker_section)

with open('auto_typer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Exact Indentation patch applied successfully!")

