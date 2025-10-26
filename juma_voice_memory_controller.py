#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JUMA Voice Memory Controller — Version 1.0.0

Cross-platform RS-232 controller for JUMA transceivers.
Provides a compact, intuitive CustomTkinter interface for controlling
voice memory functions such as MIC record, RX record, Play, Transmit, and Stop.

Developed by OH2DDG with technical assistance from OH7SV.

"""

import json
import platform
import re
from pathlib import Path

import customtkinter as ctk

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

APP_TITLE = "JUMA Voice Memory Controller"
CONFIG_PATH = Path.home() / ".juma_rs232_gui.json"
BAUD_RATES = [300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
DEFAULT_BAUD = 9600
TIMEOUT = 1.0

# Compact metrics
RADIUS = 6
BTN_H_FUNC = 24        # action buttons
BTN_H_NUM  = 24        # numeric keypad
PAD_X = 6
PAD_Y = 3
GAP   = 3

# Fonts (created after CTk root exists)
FONT_BTN_SIZE = 10
FONT_LBL_SIZE = 9




def palette(mode: str) -> dict:
    # Modern Dark (balanced & calm). Same across modes for consistency.
    return {
        "muted": ("#6b7280"),
        "rec":   ("#E74C3C", "#D64232"),   # MIC record
        "rxrec": ("#E67E22", "#CF711E"),   # RX record
        "play":  ("#27AE60", "#1F8F4F"),   # Play
        "stop":  ("#2980B9", "#2279A1"),   # Stop
        "tx_fg": ("#C0392B", "#A93226"),   # Transmit fill
        "tx_border": "#E74C3C",            # Transmit border accent
        "tx_text": "#ffffff",
        "num":   ("#2980B9", "#2279A1", "#1B5E85"),  # (normal, hover, active) — matches Stop   # numeric keypad stays blue
        "status_ok": "#27AE60",
        "status_idle": "#9CA3AF",
        "status_err": "#E74C3C",
    }




def load_cfg():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cfg(cfg: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


def find_default_port() -> str:
    ports = [p.device for p in (list_ports.comports() if list_ports else [])]
    sysname = platform.system()
    if sysname == "Darwin":
        prefer = [p for p in ports if "/dev/cu." in p]
        prefer.sort(key=lambda x: (not re.search(r"usb(serial|modem)", x, re.I), x))
        return (prefer or ports or ["/dev/cu.usbserial"])[0]
    if sysname == "Linux":
        pref = [p for p in ports if re.search(r"/dev/tty(USB|ACM)\d+", p)]
        pref.sort()
        return (pref or ports or ["/dev/ttyUSB0"])[0]
    win = [p for p in ports if re.match(r"^COM\d+$", p, re.I)]
    return (win or ports or ["COM3"])[0]


class CompactButton(ctk.CTkFrame):
    """Compact button with hover and active press effects."""
    def __init__(self, master, text, command, fg_color, hover_color, active_color=None,
                 width=78, height=24, radius=6, font=None, text_color="white"):
        super().__init__(master, fg_color=fg_color, corner_radius=radius)
        self._normal = fg_color
        self._hover = hover_color
        self._active = active_color or hover_color
        self._command = command
        self.configure(width=width, height=height)
        self.grid_propagate(False)
        self.label = ctk.CTkLabel(self, text=text, font=font, text_color=text_color)
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        for w in (self, self.label):
            w.bind("<Enter>", lambda e: self.configure(fg_color=self._hover))
            w.bind("<Leave>", lambda e: self.configure(fg_color=self._normal))
            w.bind("<Button-1>", self._on_press)
            w.bind("<ButtonRelease-1>", self._on_release)
    def _on_press(self, _):
        self.configure(fg_color=self._active)
    def _on_release(self, _):
        self.configure(fg_color=self._hover)
        if callable(self._command):
            self._command()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)

        # Fixed compact window
        self.geometry("412x226")
        self.resizable(False, False)

        self.cfg = load_cfg()
        self.appearance = self.cfg.get("theme", "Light")
        ctk.set_appearance_mode(self.appearance)
        ctk.set_default_color_theme("blue")
        self.colors = palette(self.appearance)

        self.FONT_BTN = ctk.CTkFont(size=FONT_BTN_SIZE, weight="bold")
        self.FONT_LBL = ctk.CTkFont(size=FONT_LBL_SIZE)

        self.ser = None
        self.port_var = ctk.StringVar(value="")
        self.baud_var = ctk.StringVar(value=str(self.cfg.get("baud", DEFAULT_BAUD)))
        self.status_var = ctk.StringVar(value="Idle")
        this = self  # for lambda capture friendliness (no-op)

        self.command_var = ctk.StringVar(value="")
        self._command_clear_after = None

        # Top header
        self._build_topbar()

        # Status row
        self._build_status_row()

        # Body (left actions, right keypad + hotkeys)
        self._build_body()

        self._bind_hotkeys()

        self.refresh_ports(select_default=(not self.cfg.get("port")))
        if self.cfg.get("port"):
            self.port_var.set(self.cfg["port"])

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- Top bar ----------
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, corner_radius=RADIUS)
        bar.pack(side="top", fill="x", padx=PAD_X, pady=(PAD_Y, GAP))

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(side="top", fill="x", padx=PAD_X, pady=(PAD_Y, PAD_Y))

        ctk.CTkLabel(inner, text="Port:", font=self.FONT_LBL).pack(side="left", padx=(0, 4))
        self.port_menu = ctk.CTkOptionMenu(inner, variable=self.port_var, values=[], width=160, height=20, font=self.FONT_BTN)
        self.port_menu.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(inner, text="Baud:", font=self.FONT_LBL).pack(side="left", padx=(0, 4))
        self.baud_menu = ctk.CTkOptionMenu(inner, variable=self.baud_var, values=[str(b) for b in BAUD_RATES], width=90, height=20, font=self.FONT_BTN)
        self.baud_menu.pack(side="left", padx=(0, 6))

        # Open/Close button as CompactButton to avoid text clipping
        self.open_btn = ctk.CTkButton(
            inner,
            text="Open",
            width=112,
            height=22,
            corner_radius=6,
            command=self.toggle_port,
            font=self.FONT_BTN,
        )
        self.open_btn.pack(side="left", padx=(0, 4))

    # ---------- Status row (Status • Command • Theme) ----------
    def _build_status_row(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="top", fill="x", padx=PAD_X, pady=(0, GAP))

        # Left group
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="Status:", font=ctk.CTkFont(weight="bold", size=10)).pack(side="left")
        bg = self._apply_appearance_mode(self.cget("fg_color"))
        self.dot = ctk.CTkCanvas(left, width=7, height=7, highlightthickness=0, bg=bg, bd=0)
        self.dot_id = self.dot.create_oval(1, 1, 6, 6, fill=self.colors["status_idle"], outline=bg)
        self.dot.pack(side="left", padx=5)
        self.status_lbl = ctk.CTkLabel(left, textvariable=self.status_var, font=self.FONT_LBL)
        self.status_lbl.pack(side="left")

        # Center group
        center = ctk.CTkFrame(row, fg_color="transparent")
        center.pack(side="left", fill="x", expand=True, padx=(10, 0))
        ctk.CTkLabel(center, text="Command:", text_color=self.colors["muted"], font=self.FONT_LBL).pack(side="left")
        self.command_lbl = ctk.CTkLabel(center, textvariable=self.command_var, font=self.FONT_LBL)
        self.command_lbl.pack(side="left", padx=(5, 0))

        # Theme next to Command — smaller and aligned
        self.theme_btn = ctk.CTkSegmentedButton(center, values=["Light", "Dark"], height=16, width=84, command=self._toggle_theme, font=self.FONT_BTN)
        self.theme_btn.set(self.appearance)
        self.theme_btn.pack(side="right", padx=(0, 0))

        self._update_status_dot("idle")

    # ---------- Body ----------
    def _build_body(self):
        body = ctk.CTkFrame(self, corner_radius=RADIUS, fg_color="transparent")
        body.pack(side="top", fill="x", expand=False, padx=PAD_X, pady=(0, 0))

        # Left actions
        left = ctk.CTkFrame(body, fg_color="transparent", width=135)
        left.pack(side="left", padx=(GAP, GAP), pady=(GAP, 0), fill="y")

        def _act_btn(parent, text, cmd, color_pair=None, **kw):
            style = dict(font=self.FONT_BTN, height=BTN_H_FUNC, corner_radius=RADIUS)
            if color_pair:
                style.update(dict(fg_color=color_pair[0], hover_color=color_pair[1]))
            style.update(kw)
            btn = ctk.CTkButton(parent, text=text, command=cmd, **style)
            btn.pack(fill="x", padx=GAP, pady=(GAP, 0))
            return btn

        _act_btn(left, "MIC record", lambda: self.send("M"), self.colors["rec"])
        _act_btn(left, "RX record",  lambda: self.send("R"), self.colors["rxrec"])
        _act_btn(left, "Play",       lambda: self.send("P"), self.colors["play"])
        self.tx_btn = _act_btn(left, "Transmit", lambda: self.send("T"),
                               (self.colors["tx_fg"][0], self.colors["tx_fg"][1]),
                               border_width=2, border_color=self.colors["tx_border"],
                               text_color=self.colors["tx_text"])
        _act_btn(left, "Stop",       lambda: self.send("S"), self.colors["stop"])

        # Right keypad
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", padx=(GAP, 0), pady=(GAP, 0))

        grid = ctk.CTkFrame(right, fg_color="transparent")
        grid.pack(side="top", padx=0, pady=(0, 0))

        numc = self.colors["num"]
        btn_w = 78  # tuned to align with right edge
        nums = [["1","2","3"],["4","5","6"],["7","8","9"]]
        for r, row in enumerate(nums):
            row_frame = ctk.CTkFrame(grid, fg_color="transparent")
            row_frame.pack(side="top", pady=(GAP, 0))  # same vertical rhythm as left buttons
            for c, label in enumerate(row):
                b = CompactButton(row_frame, text=label, command=lambda n=label: self.send(n),
                                  fg_color=numc[0], hover_color=numc[1],
                                  width=btn_w, height=BTN_H_NUM, radius=RADIUS, font=self.FONT_BTN)
                b.pack(side="left", padx=(0 if c == 0 else GAP, 0))

        # 0 centered
        row0 = ctk.CTkFrame(grid, fg_color="transparent")
        row0.pack(side="top", pady=(GAP, 0))
        spacer_w = btn_w
        ctk.CTkFrame(row0, width=spacer_w, height=BTN_H_NUM, fg_color="transparent").pack(side="left")
        b0 = CompactButton(row0, text="0", command=lambda: self.send("0"), fg_color=numc[0], hover_color=numc[1], width=btn_w, height=BTN_H_NUM, radius=RADIUS, font=self.FONT_BTN, active_color=self.colors["num"][2])
        b0.pack(side="left", padx=GAP)
        ctk.CTkFrame(row0, width=spacer_w, height=BTN_H_NUM, fg_color="transparent").pack(side="left")

        # Hotkeys centered
        self.hotkeys_lbl = ctk.CTkLabel(
            right,
            text="Hotkeys: M R P T S, digits 1–9",
            text_color=self.colors["muted"],
            font=self.FONT_LBL,
            anchor="center",
            justify="center"
        )
        self.hotkeys_lbl.pack(side="top", fill="x", padx=0, pady=(GAP, 0))

    # ---------- Theme ----------
    def _toggle_theme(self, mode: str):
        ctk.set_appearance_mode(mode)
        self.appearance = mode
        self.colors = palette(mode)
        self.cfg["theme"] = mode
        save_cfg(self.cfg)
        # simple rebuild (fixed layout)
        for w in self.winfo_children():
            w.destroy()
        self._build_topbar()
        self._build_status_row()
        self._build_body()
        self._bind_hotkeys()
        self.refresh_ports(select_default=False)

    # ---------- Hotkeys ----------
    def _bind_hotkeys(self):
        for key, ch in [("m","M"),("r","R"),("p","P"),("t","T"),("s","S")]:
            self.bind(f"<Key-{key}>", lambda e, c=ch: self.send(c))
            self.bind(f"<Key-{key.upper()}>", lambda e, c=ch: self.send(c))
        for d in "0123456789":
            self.bind(f"<Key-{d}>", lambda e, c=d: self.send(c))

    # ---------- Status helpers ----------
    def _update_status_dot(self, state: str):
        try:
            color = self.colors["status_idle"]
            if state == "ok":
                color = self.colors["status_ok"]
            elif state == "error":
                color = self.colors["status_err"]
            self.dot.itemconfig(self.dot_id, fill=color)
        except Exception:
            pass

    def _set_status(self, text: str, state: str | None = None):
        self.status_var.set(text)
        if state is None:
            t = (text or "").lower()
            if t.startswith("connected"):
                state = "ok"
            elif "failed" in t or "error" in t:
                state = "error"
            elif t == "idle":
                state = "idle"
            else:
                state = "ok"
        self._update_status_dot(state)

    # ---------- Serial ----------
    def refresh_ports(self, select_default=False):
        if not list_ports:
            self._set_status("pyserial not found. pip install pyserial", state="error")
            return
        ports = [p.device for p in list_ports.comports()]
        if select_default and ports:
            self.port_var.set(find_default_port())
        elif ports and not self.port_var.get():
            self.port_var.set(ports[0])
        try:
            self.port_menu.configure(values=ports or [""])
        except Exception:
            pass

    def toggle_port(self):
        if self.ser and self.ser.is_open:
            self.close_port()
        else:
            self.open_port()

    def open_port(self):
        if serial is None:
            self._set_status("pyserial not found. pip install pyserial", state="error")
            return
        port = (self.port_var.get() or "").strip()
        if not port:
            self.bell()
            self._set_status("Choose a serial port first.", state="error")
            return
        try:
            baud = int(self.baud_var.get() or DEFAULT_BAUD)
            self.ser = serial.Serial(port, baudrate=baud, timeout=TIMEOUT)
            self._set_status(f"Connected: {port} @ {baud}", state="ok")
            # change button label to Close
            self.open_btn.configure(text="Close")
            self.cfg["port"] = port
            self.cfg["baud"] = baud
            save_cfg(self.cfg)
        except Exception as e:
            self._set_status(f"Open failed: {e}", state="error")
            self.ser = None
            self.open_btn.configure(text="Open")

    def close_port(self):
        try:
            if self.ser:
                self.ser.close()
        finally:
            self.ser = None
            self._set_status("Idle", state="idle")
            # change button label back to Open
            self.open_btn.configure(text="Open")

    # ---------- Send ----------
    def _show_command(self, s: str):
        self.command_var.set(s)
        if self._command_clear_after is not None:
            try:
                self.after_cancel(self._command_clear_after)
            except Exception:
                pass
            self._command_clear_after = None
        self._command_clear_after = self.after(5000, lambda: self.command_var.set(""))

    def send(self, data: str):
        if not self.ser or not self.ser.is_open:
            self.bell()
            self._set_status("Port is not open!", state="error")
            return
        try:
            self.ser.write(data.encode("ascii"))
            self._show_command(data)
            if data in {"M", "R", "P", "T", "S"}:
                if data == "S":
                    self._set_status("Idle", state="idle")
                else:
                    label = {"M":"MIC record","R":"RX record","P":"Play","T":"Transmit"}[data]
                    self._set_status(label, state="ok")
        except Exception as e:
            self._set_status(f"Send failed: {e}", state="error")

    # ---------- Exit ----------
    def on_close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            save_cfg(self.cfg)
            self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
