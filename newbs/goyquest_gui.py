#!/usr/bin/env python3
"""
Goyquest Windows GUI.

Normal launch: opens the form UI.
Worker launch:  Goyquest.exe --worker --token ...  (used internally; same CLI as react_http.py)
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

APP_NAME = "Goyquest"
WORKER_FLAG = "--worker"
HELP_TOKEN_URL = "https://github.com/UnityEQ/GoyQuest#getting-your-token"
HELP_IDS_URL = "https://github.com/UnityEQ/GoyQuest#getting-channel-and-server-ids"


class ArtDecoTheme:
    """Black, gold, and silver palette — minimal art deco."""

    BG = "#080808"
    PANEL = "#101010"
    INSET = "#161616"
    GOLD = "#c9a962"
    GOLD_BRIGHT = "#e2c878"
    GOLD_DIM = "#7a6535"
    SILVER = "#a8a8a8"
    SILVER_LIGHT = "#d4d4d4"
    SILVER_DIM = "#6e6e6e"
    TEXT = "#ececec"
    LOG_BG = "#050505"
    LOG_FG = "#b8b8b8"

    TITLE_FONT = ("Georgia", 26, "bold")
    SUBTITLE_FONT = ("Segoe UI", 9)
    LABEL_FONT = ("Segoe UI", 9)
    SECTION_FONT = ("Georgia", 10, "bold")
    BUTTON_FONT = ("Segoe UI", 10, "bold")
    MONO_FONT = ("Consolas", 10)

    @classmethod
    def apply(cls, root: tk.Tk) -> ttk.Style:
        root.configure(bg=cls.BG)
        style = ttk.Style(root)
        style.theme_use("clam")

        style.configure(".", background=cls.BG, foreground=cls.SILVER_LIGHT, font=cls.LABEL_FONT)
        style.configure("TFrame", background=cls.BG)
        style.configure("Panel.TFrame", background=cls.PANEL)

        style.configure(
            "Title.TLabel",
            background=cls.BG,
            foreground=cls.GOLD_BRIGHT,
            font=cls.TITLE_FONT,
        )
        style.configure(
            "Subtitle.TLabel",
            background=cls.BG,
            foreground=cls.SILVER,
            font=cls.SUBTITLE_FONT,
        )
        style.configure(
            "Field.TLabel",
            background=cls.PANEL,
            foreground=cls.GOLD,
            font=cls.SECTION_FONT,
        )
        style.configure(
            "Hint.TLabel",
            background=cls.PANEL,
            foreground=cls.SILVER_DIM,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Status.TLabel",
            background=cls.BG,
            foreground=cls.SILVER,
            font=("Segoe UI", 9, "italic"),
        )
        style.configure(
            "StatusRun.TLabel",
            background=cls.BG,
            foreground=cls.GOLD_BRIGHT,
            font=("Segoe UI", 9, "bold"),
        )

        style.configure(
            "Panel.TLabelframe",
            background=cls.PANEL,
            bordercolor=cls.GOLD_DIM,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Panel.TLabelframe.Label",
            background=cls.PANEL,
            foreground=cls.GOLD_BRIGHT,
            font=cls.SECTION_FONT,
        )

        style.configure(
            "TEntry",
            fieldbackground=cls.INSET,
            foreground=cls.SILVER_LIGHT,
            bordercolor=cls.GOLD_DIM,
            lightcolor=cls.GOLD_DIM,
            darkcolor=cls.GOLD_DIM,
            insertcolor=cls.GOLD_BRIGHT,
            padding=6,
        )

        style.configure(
            "Gold.TButton",
            background=cls.GOLD_DIM,
            foreground=cls.BG,
            bordercolor=cls.GOLD,
            focusthickness=0,
            font=cls.BUTTON_FONT,
            padding=(22, 10),
        )
        style.map(
            "Gold.TButton",
            background=[("active", cls.GOLD), ("disabled", "#2a2a2a")],
            foreground=[("active", cls.BG), ("disabled", cls.SILVER_DIM)],
            bordercolor=[("active", cls.GOLD_BRIGHT)],
        )

        style.configure(
            "Silver.TButton",
            background=cls.INSET,
            foreground=cls.SILVER_LIGHT,
            bordercolor=cls.SILVER_DIM,
            font=("Segoe UI", 9),
            padding=(14, 8),
        )
        style.map(
            "Silver.TButton",
            background=[("active", "#222222")],
            foreground=[("active", cls.TEXT)],
            bordercolor=[("active", cls.SILVER)],
        )

        style.configure(
            "TCheckbutton",
            background=cls.PANEL,
            foreground=cls.SILVER,
            font=("Segoe UI", 9),
        )
        style.map(
            "TCheckbutton",
            background=[("active", cls.PANEL)],
            foreground=[("active", cls.SILVER_LIGHT)],
        )

        return style


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return app_dir().parent


def react_http_script() -> Path:
    return resource_root() / "react_http.py"


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, WORKER_FLAG]
    return [sys.executable, str(Path(__file__).resolve()), WORKER_FLAG]


def run_worker_mode() -> None:
    sys.path.insert(0, str(resource_root()))
    import react_http

    react_http.configure_stdio()
    sys.argv = ["react_http.py", *sys.argv[2:]]
    react_http.main()


class GoyquestGUI:
    def __init__(self, root: tk.Tk, theme: ArtDecoTheme) -> None:
        self.root = root
        self.theme = theme
        self.root.title(APP_NAME)
        self.root.minsize(760, 700)
        self.root.geometry("860x760")

        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str | None] = queue.Queue()

        self._build_ui()
        self._poll_log()

    def _deco_rule(self, parent: tk.Widget) -> tk.Canvas:
        theme = self.theme
        canvas = tk.Canvas(parent, height=18, bg=theme.BG, highlightthickness=0, bd=0)

        def redraw(event: tk.Event | None = None) -> None:
            canvas.delete("all")
            w = canvas.winfo_width()
            if w < 40:
                return
            y = 9
            mid = w // 2
            canvas.create_line(0, y, mid - 28, y, fill=theme.GOLD_DIM, width=1)
            canvas.create_line(mid + 28, y, w, y, fill=theme.GOLD_DIM, width=1)
            canvas.create_line(mid - 10, y, mid + 10, y, fill=theme.GOLD, width=2)
            canvas.create_polygon(
                mid,
                y - 5,
                mid + 5,
                y,
                mid,
                y + 5,
                mid - 5,
                y,
                fill=theme.GOLD_BRIGHT,
                outline=theme.GOLD,
                width=1,
            )

        canvas.bind("<Configure>", redraw)
        canvas.pack(fill=tk.X, pady=(14, 18))
        return canvas

    def _build_ui(self) -> None:
        theme = self.theme
        outer = ttk.Frame(self.root, padding=(28, 22, 28, 18))
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X)
        ttk.Label(header, text=APP_NAME.upper(), style="Title.TLabel").pack(anchor=tk.CENTER)
        ttk.Label(
            header,
            text="an Israeli flag for every post",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.CENTER, pady=(4, 0))

        self._deco_rule(outer)

        required = ttk.LabelFrame(outer, text="  REQUIRED  ", style="Panel.TLabelframe", padding=16)
        required.pack(fill=tk.X, pady=(0, 14))

        self.token_var = tk.StringVar()
        self.server_var = tk.StringVar()
        self.channel_var = tk.StringVar()

        self._row(required, "TOKEN", self.token_var, show="\u2022", help_url=HELP_TOKEN_URL)
        self._row(required, "SERVER", self.server_var, help_url=HELP_IDS_URL)
        self._row(
            required,
            "CHANNEL",
            self.channel_var,
            hint="id  \u00b7  ids  \u00b7  all",
            help_url=HELP_IDS_URL,
        )

        options = ttk.LabelFrame(outer, text="  OPTIONS  ", style="Panel.TLabelframe", padding=16)
        options.pack(fill=tk.X, pady=(0, 14))

        self.minutes_var = tk.StringVar(value="0")
        self.last_var = tk.StringVar(value="0")
        self.delay_var = tk.StringVar(value="0.35")
        self.timer_var = tk.StringVar(value="0")
        self.skip_bots_var = tk.BooleanVar(value=False)
        self.skip_self_var = tk.BooleanVar(value=False)
        self.backfill_only_var = tk.BooleanVar(value=False)

        grid = ttk.Frame(options, style="Panel.TFrame")
        grid.pack(fill=tk.X)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(3, weight=1)
        self._grid(
            grid,
            0,
            0,
            "Backfill min",
            self.minutes_var,
            hint="0 = live only \u00b7 N = past N minutes",
        )
        self._grid(
            grid,
            0,
            2,
            "Backfill last",
            self.last_var,
            hint="0 = off \u00b7 N = last N msgs per channel",
        )
        self._grid(grid, 2, 0, "Delay (sec)", self.delay_var)
        self._grid(grid, 2, 2, "Run Timer (min)", self.timer_var)

        checks = ttk.Frame(options, style="Panel.TFrame")
        checks.pack(fill=tk.X, pady=(14, 0))
        ttk.Checkbutton(checks, text="Skip bots", variable=self.skip_bots_var).pack(
            side=tk.LEFT, padx=(0, 18)
        )
        ttk.Checkbutton(checks, text="Skip own messages", variable=self.skip_self_var).pack(
            side=tk.LEFT, padx=(0, 18)
        )
        ttk.Checkbutton(checks, text="Backfill only", variable=self.backfill_only_var).pack(
            side=tk.LEFT
        )

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=(0, 12))
        self.go_btn = ttk.Button(controls, text="GO", style="Gold.TButton", command=self.start)
        self.go_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(
            controls, text="STOP", style="Silver.TButton", command=self.stop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(controls, text="Clear log", style="Silver.TButton", command=self.clear_log).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        self.status_var = tk.StringVar(value="Idle")
        self.status_label = ttk.Label(controls, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side=tk.RIGHT)

        log_outer = ttk.LabelFrame(outer, text="  LIVE LOG  ", style="Panel.TLabelframe", padding=10)
        log_outer.pack(fill=tk.BOTH, expand=True)

        self.log = scrolledtext.ScrolledText(
            log_outer,
            height=14,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=theme.MONO_FONT,
            bg=theme.LOG_BG,
            fg=theme.LOG_FG,
            insertbackground=theme.GOLD,
            selectbackground=theme.GOLD_DIM,
            selectforeground=theme.TEXT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=theme.GOLD_DIM,
            highlightcolor=theme.GOLD_DIM,
            bd=0,
            padx=10,
            pady=8,
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.tag_configure("reacted", foreground=theme.GOLD_BRIGHT)

        if getattr(sys, "frozen", False):
            self.append_log(f"Running from {app_dir()}\n")
        elif not react_http_script().exists():
            self.append_log(f"Warning: missing {react_http_script()}\n")

    def _help_link(self, parent: tk.Widget, url: str) -> tk.Label:
        theme = self.theme
        link = tk.Label(
            parent,
            text="?",
            fg=theme.SILVER,
            bg=theme.PANEL,
            font=("Georgia", 12, "bold"),
            cursor="hand2",
        )

        def open_help(_event: tk.Event | None = None) -> None:
            webbrowser.open(url)

        def on_enter(_event: tk.Event) -> None:
            link.configure(fg=theme.GOLD_BRIGHT)

        def on_leave(_event: tk.Event) -> None:
            link.configure(fg=theme.SILVER)

        link.bind("<Button-1>", open_help)
        link.bind("<Enter>", on_enter)
        link.bind("<Leave>", on_leave)
        return link

    def _row(
        self,
        parent: ttk.LabelFrame,
        label: str,
        variable: tk.StringVar,
        *,
        show: str | None = None,
        hint: str | None = None,
        help_url: str | None = None,
    ) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=6)
        ttk.Label(row, text=label, style="Field.TLabel", width=10).pack(side=tk.LEFT)
        entry = ttk.Entry(row, textvariable=variable, show=show)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        if help_url:
            self._help_link(row, help_url).pack(side=tk.LEFT, padx=(8, 0))
        if hint:
            ttk.Label(row, text=hint, style="Hint.TLabel").pack(side=tk.LEFT, padx=(10, 0))

    def _grid(
        self,
        parent: ttk.Frame,
        row: int,
        col: int,
        label: str,
        variable: tk.StringVar,
        *,
        hint: str | None = None,
    ) -> None:
        ttk.Label(parent, text=label, style="Field.TLabel").grid(
            row=row, column=col, sticky=tk.W, padx=(0, 10), pady=(6, 0)
        )
        ttk.Entry(parent, textvariable=variable, width=16).grid(
            row=row, column=col + 1, sticky=tk.EW, pady=(6, 0)
        )
        if hint:
            ttk.Label(parent, text=hint, style="Hint.TLabel", wraplength=240).grid(
                row=row + 1,
                column=col,
                columnspan=2,
                sticky=tk.W,
                padx=(0, 10),
                pady=(0, 6),
            )

    def append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        start = self.log.index(tk.END)
        self.log.insert(tk.END, text)
        if "+ reacted" in text:
            self.log.tag_add("reacted", start, tk.END)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def clear_log(self) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def set_running(self, running: bool) -> None:
        self.go_btn.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL if running else tk.DISABLED)
        self.status_var.set("Running" if running else "Idle")
        self.status_label.configure(style="StatusRun.TLabel" if running else "Status.TLabel")

    def _build_args(self) -> list[str] | None:
        token = self.token_var.get().strip()
        server = self.server_var.get().strip()
        channel = self.channel_var.get().strip()

        if not token:
            messagebox.showerror(APP_NAME, "Token is required.")
            return None
        if not server:
            messagebox.showerror(APP_NAME, "Server ID is required.")
            return None
        if not channel:
            messagebox.showerror(APP_NAME, "Channel is required.")
            return None
        if not server.isdigit():
            messagebox.showerror(APP_NAME, "Server ID must be a number.")
            return None

        if channel.lower() != "all":
            for part in channel.split(","):
                part = part.strip()
                if part and not part.isdigit():
                    messagebox.showerror(APP_NAME, "Channel must be 'all' or numeric IDs.")
                    return None

        try:
            minutes = float(self.minutes_var.get().strip() or "0")
            last = int(self.last_var.get().strip() or "0")
            delay = float(self.delay_var.get().strip() or "0.35")
            timer = float(self.timer_var.get().strip() or "0")
        except ValueError:
            messagebox.showerror(APP_NAME, "Minutes, last, delay, and timer must be numbers.")
            return None

        if minutes < 0 or last < 0 or delay < 0 or timer < 0:
            messagebox.showerror(APP_NAME, "Numeric options cannot be negative.")
            return None
        if minutes > 0 and last > 0:
            messagebox.showerror(APP_NAME, "Use backfill minutes or last N messages, not both.")
            return None

        args = [
            "--token",
            token,
            "--server",
            server,
            "--channel",
            channel,
            "--delay",
            str(delay),
        ]
        if minutes > 0:
            args.extend(["--minutes", str(minutes)])
        if last > 0:
            args.extend(["--last", str(last)])
        if timer > 0:
            args.extend(["--timer", str(timer)])
        if self.skip_bots_var.get():
            args.append("--skip-bots")
        if self.skip_self_var.get():
            args.append("--skip-self")
        if self.backfill_only_var.get():
            args.append("--backfill-only")
        return args

    def start(self) -> None:
        if self.process is not None:
            return

        cli_args = self._build_args()
        if cli_args is None:
            return

        if getattr(sys, "frozen", False):
            cmd = worker_command() + cli_args
            cwd = str(app_dir())
        else:
            if not react_http_script().exists():
                messagebox.showerror(APP_NAME, f"Missing react_http.py:\n{react_http_script()}")
                return
            cmd = worker_command() + cli_args
            cwd = str(resource_root())

        self.append_log(f"\n> {self._redact(cmd)}\n")
        self.set_running(True)

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8:replace"
        env["PYTHONUNBUFFERED"] = "1"
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=creationflags,
            )
        except OSError as exc:
            self.process = None
            self.set_running(False)
            messagebox.showerror(APP_NAME, f"Failed to start:\n{exc}")
            return

        threading.Thread(target=self._read_output, daemon=True).start()

    def _redact(self, cmd: list[str]) -> str:
        parts = cmd.copy()
        if "--token" in parts:
            idx = parts.index("--token")
            if idx + 1 < len(parts):
                parts[idx + 1] = "***"
        return " ".join(parts)

    def _read_output(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            self.log_queue.put(line)
        self.log_queue.put(None)

    def _poll_log(self) -> None:
        while True:
            try:
                item = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                self._on_exit()
            else:
                self.append_log(item)
        self.root.after(100, self._poll_log)

    def _on_exit(self) -> None:
        code: int | None = None
        if self.process is not None:
            code = self.process.wait()
            self.process = None
        self.set_running(False)
        self.append_log(f"\nFinished (exit code {code}).\n")

    def stop(self) -> None:
        if self.process is None:
            return
        self.append_log("\nStopping...\n")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)


def launch_gui() -> None:
    root = tk.Tk()
    theme = ArtDecoTheme()
    ArtDecoTheme.apply(root)
    GoyquestGUI(root, theme)
    root.mainloop()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == WORKER_FLAG:
        run_worker_mode()
        return
    launch_gui()


if __name__ == "__main__":
    main()