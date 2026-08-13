#!/usr/bin/env python3
"""Dependency-free Tk desktop companion for the Web Sweeper interface."""

from __future__ import annotations

import json
import random
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import colorchooser, ttk
from typing import Optional


STATE_PATH = Path.home() / ".web_sweeper_developer_interface.json"
BACKGROUND = "#07110d"
PANEL = "#0d1d16"
GREEN = "#35d07f"
MUTED = "#83a891"


class Interface(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Sweeper Developer Interface")
        self.geometry("1120x760")
        self.minsize(390, 680)
        self.configure(bg=BACKGROUND)
        self.state_data = self._load_state()
        self.text_color = self.state_data.get("textColor", "#edf7ef")
        self.sequence: list[int] = []
        self.entered: list[int] = []
        self.score = 0
        self.high_score = int(self.state_data.get("highScore", 0))
        self.milestone = bool(self.state_data.get("milestone20", False))
        self.lit_pad = 0
        self.endpoint = tk.StringVar(value=self.state_data.get("endpoint", "http://127.0.0.1:8790"))
        self.token = tk.StringVar(value=self.state_data.get("token", ""))
        self.selected_lane = tk.StringVar(value="source-one")
        self.message = tk.StringVar(value="Controller not connected")
        self.game_message = tk.StringVar(value="Press Start, watch the pads, then repeat.")
        self.score_text = tk.StringVar(value=self._score_label())
        self._build()

    def _load_state(self) -> dict:
        try:
            value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_state(self) -> None:
        STATE_PATH.write_text(
            json.dumps(
                {
                    "endpoint": self.endpoint.get().strip(),
                    "token": self.token.get(),
                    "textColor": self.text_color,
                    "highScore": self.high_score,
                    "milestone20": self.milestone,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=8)
        shell = tk.Frame(self, bg=BACKGROUND)
        shell.pack(fill="both", expand=True, padx=16, pady=12)
        header = tk.Frame(shell, bg=PANEL, padx=12, pady=10)
        header.pack(fill="x")
        logo_path = Path(__file__).resolve().parents[3] / "assets" / "sweeper-logo.png"
        try:
            image = tk.PhotoImage(file=logo_path).subsample(16, 16)
            logo = tk.Label(header, image=image, bg=PANEL)
            logo.image = image
            logo.pack(side="left", padx=(0, 10))
        except tk.TclError:
            pass
        tk.Label(header, text="WEB SWEEPER\nDeveloper Interface", justify="left", bg=PANEL,
                 fg=self.text_color, font=("Helvetica", 15, "bold")).pack(side="left")
        ttk.Button(header, text="Text color", command=self._choose_color).pack(side="right")

        content = tk.Frame(shell, bg=BACKGROUND)
        content.pack(fill="both", expand=True, pady=(12, 0))
        left = tk.Frame(content, bg=BACKGROUND)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(content, bg=PANEL, padx=12, pady=12, width=300)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        self._connection(left)
        self.lanes = tk.Frame(left, bg=BACKGROUND)
        self.lanes.pack(fill="both", expand=True, pady=(12, 0))
        self._empty_lanes()
        self._game(right)

    def _connection(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=PANEL, padx=12, pady=12)
        panel.pack(fill="x")
        tk.Label(panel, text="CONTROLLER CONNECTION", bg=PANEL, fg=GREEN,
                 font=("Helvetica", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(panel, text="URL", bg=PANEL, fg=self.text_color).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(panel, textvariable=self.endpoint).grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))
        tk.Label(panel, text="Token", bg=PANEL, fg=self.text_color).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(panel, textvariable=self.token, show="•").grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(panel, text="Connect", command=self.refresh).grid(row=1, column=2, rowspan=2, padx=4, pady=(8, 0))
        ttk.Combobox(panel, textvariable=self.selected_lane, state="readonly",
                     values=("source-one", "source-two", "publisher"), width=14).grid(row=1, column=3, padx=4, pady=(8, 0))
        actions = tk.Frame(panel, bg=PANEL)
        actions.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
        for name in ("switch", "bridge", "reset", "upload"):
            ttk.Button(actions, text=name.title(), command=lambda action=name: self.action(action)).pack(side="left", padx=(0, 6))
        tk.Label(panel, textvariable=self.message, bg=PANEL, fg=MUTED, justify="left",
                 wraplength=650).grid(row=4, column=0, columnspan=4, sticky="w", pady=(9, 0))
        panel.columnconfigure(1, weight=1)

    def _empty_lanes(self) -> None:
        tk.Label(self.lanes, text="Connect to read live lane status.", bg=BACKGROUND,
                 fg=MUTED, font=("Helvetica", 13)).pack(anchor="w", pady=18)

    def _request(self, path: str, payload: Optional[dict] = None) -> dict:
        base = self.endpoint.get().strip().rstrip("/")
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{base}{path}",
            data=data,
            headers={"Authorization": f"Bearer {self.token.get()}", "Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        with urllib.request.urlopen(request, timeout=8) as reply:
            return json.loads(reply.read())

    def refresh(self) -> None:
        try:
            data = self._request("/api/status")
            self._save_state()
            self.message.set(f"Connected · Codex Live {data.get('codexLive', 0):,}")
            for child in self.lanes.winfo_children():
                child.destroy()
            for lane in data.get("lanes", []):
                self._lane_card(lane)
        except (urllib.error.URLError, ValueError, OSError) as error:
            self.message.set(f"Connection failed · {error}")

    def action(self, name: str) -> None:
        try:
            self._request("/api/action", {"action": name, "lane": self.selected_lane.get()})
            self.message.set(f"{name.title()} request accepted")
        except (urllib.error.URLError, ValueError, OSError) as error:
            self.message.set(f"Action not accepted · {error}")

    def _lane_card(self, lane: dict) -> None:
        colors = {"healthy": GREEN, "watch": "#f5d142", "stuck": "#ff8a3d", "failed": "#ff4e5b"}
        card = tk.Frame(self.lanes, bg=PANEL, padx=12, pady=11, highlightthickness=1,
                        highlightbackground="#1e4733")
        card.pack(fill="x", pady=(0, 8))
        color = colors.get(lane.get("health"), "#f5d142")
        tk.Label(card, text="●", bg=PANEL, fg=color).pack(side="left")
        body = tk.Frame(card, bg=PANEL)
        body.pack(side="left", fill="x", expand=True, padx=8)
        tk.Label(body, text=lane.get("name", "Lane"), bg=PANEL, fg=self.text_color,
                 font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(body, text=f"{lane.get('stage', 'unknown')} · {lane.get('accepted', 0):,} / {lane.get('target', 0):,} · {lane.get('uploaded', 0):,} uploaded",
                 bg=PANEL, fg=MUTED, justify="left", wraplength=650).pack(anchor="w")

    def _choose_color(self) -> None:
        selected = colorchooser.askcolor(self.text_color, title="Readable text color")[1]
        if selected:
            self.text_color = selected
            self._save_state()
            self.destroy()
            app = Interface()
            app.mainloop()

    def _game(self, parent: tk.Widget) -> None:
        tk.Label(parent, text="WAITING GAME", bg=PANEL, fg=GREEN,
                 font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(parent, text="Repeat the four-pad sequence", bg=PANEL, fg=MUTED).pack(anchor="w")
        tk.Label(parent, textvariable=self.score_text, bg=PANEL, fg=self.text_color,
                 font=("Helvetica", 11, "bold")).pack(pady=(8, 2))
        tk.Label(parent, textvariable=self.game_message, bg=PANEL, fg=self.text_color,
                 justify="center", wraplength=260).pack(pady=(0, 8))
        grid = tk.Frame(parent, bg=PANEL)
        grid.pack(fill="x")
        self.pads: dict[int, tk.Button] = {}
        for number in range(1, 5):
            button = tk.Button(grid, text=str(number), font=("Helvetica", 18, "bold"), bg="#173c2a",
                               fg=self.text_color, activebackground="#63f5a4", command=lambda n=number: self._tap(n))
            button.grid(row=(number - 1) // 2, column=(number - 1) % 2, sticky="nsew", padx=4, pady=4, ipady=12)
            self.pads[number] = button
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        ttk.Button(parent, text="Start / Restart", command=self._start_game).pack(fill="x", pady=(10, 0))

    def _score_label(self) -> str:
        return f"SCORE {self.score}  ·  BEST {self.high_score}"

    def _start_game(self) -> None:
        self.sequence = [random.randint(1, 4)]
        self.entered = []
        self.score = 0
        self.score_text.set(self._score_label())
        self._play(0)

    def _play(self, index: int) -> None:
        if index >= len(self.sequence):
            self.game_message.set("Your turn")
            return
        self.game_message.set("Watch…")
        number = self.sequence[index]
        self.pads[number].configure(bg="#63f5a4", fg="#052516")
        self.after(360, lambda: self._unlight(number, index))

    def _unlight(self, number: int, index: int) -> None:
        self.pads[number].configure(bg="#173c2a", fg=self.text_color)
        self.after(160, lambda: self._play(index + 1))

    def _tap(self, number: int) -> None:
        if not self.sequence or self.game_message.get() != "Your turn":
            return
        expected = self.sequence[len(self.entered)]
        self.entered.append(number)
        if number != expected:
            self.game_message.set("Not quite. Start again.")
            return
        if len(self.entered) < len(self.sequence):
            return
        self.score += 1
        self.high_score = max(self.high_score, self.score)
        if self.score >= 20 and not self.milestone:
            self.milestone = True
            self.message.set("Chris was innocent.")
        self._save_state()
        self.score_text.set(self._score_label())
        self.game_message.set("Correct!")
        self.sequence.append(random.randint(1, 4))
        self.entered = []
        self.after(500, lambda: self._play(0))


if __name__ == "__main__":
    Interface().mainloop()
