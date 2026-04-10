#!/usr/bin/env python3
"""Wiper — Discord Message Deleter (polished desktop app)"""

import tkinter as tk
import threading, time, random, re, json, math
import urllib.request, urllib.error
from datetime import datetime

C = dict(
    bg="#0d0d0f", sidebar="#111115", panel="#18181d", card="#1e1e25",
    border="#2a2a35", accent="#5865f2", accent2="#eb459e",
    green="#23d18b", yellow="#faa61a", red="#ed4245",
    text="#f2f3f5", muted="#72767d", dim="#40444b",
)

# ── Discord API ──────────────────────────────────────────────────────────────
class RateLimitError(Exception):
    def __init__(self, s): self.retry_after = s

def parse_fetch(text, manual_token=""):
    """Parse any Discord fetch command — search or messages endpoint."""
    result = {"headers": {}, "mode": None, "guild_id": None,
               "channel_id": None, "author_id": None, "url": None}

    # Extract headers
    for k, v in re.findall(r'"([\w-]+)":\s*"([^"]*)"', text):
        result["headers"][k] = v
    for k, v in re.findall(r"'([\w-]+)':\s*'([^']*)'", text):
        result["headers"].setdefault(k, v)

    if manual_token.strip():
        result["headers"]["authorization"] = manual_token.strip()

    # Must have auth
    auth = next((v for k, v in result["headers"].items() if k.lower() == "authorization"), None)
    if not auth:
        return None
    result["auth"] = auth.strip()
    result["headers"] = {k: v for k, v in result["headers"].items()}

    # Detect mode: guild search
    gm = re.search(r'discord\.com/api/v\d+/guilds/(\d+)/messages/search', text)
    if gm:
        result["mode"] = "guild_search"
        result["guild_id"] = gm.group(1)
        am = re.search(r'author_id=(\d+)', text)
        if am:
            result["author_id"] = am.group(1)
        return result

    # Detect mode: channel messages
    cm = re.search(r'discord\.com/api/v\d+/channels/(\d+)/messages', text)
    if cm:
        result["mode"] = "channel"
        result["channel_id"] = cm.group(1)
        return result

    return None

def make_headers(parsed):
    """Build clean headers dict for urllib."""
    hdrs = {}
    for k, v in parsed["headers"].items():
        # Capitalise properly
        if k.lower() == "authorization":
            hdrs["Authorization"] = parsed["auth"]
        elif k.lower() == "x-super-properties":
            hdrs["x-super-properties"] = v
        elif k.lower() == "x-discord-locale":
            hdrs["x-discord-locale"] = v
        elif k.lower() == "x-discord-timezone":
            hdrs["x-discord-timezone"] = v
        elif k.lower() == "x-debug-options":
            hdrs["x-debug-options"] = v
    hdrs["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    )
    return hdrs

def search_messages(guild_id, author_id, hdrs, offset=0):
    """Search a guild for messages by author. Returns (messages, total)."""
    url = (f"https://discord.com/api/v9/guilds/{guild_id}/messages/search"
           f"?author_id={author_id}&sort_by=timestamp&sort_order=desc"
           f"&offset={offset}&limit=25")
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            # Each item in messages is a list; the first element is the matching message
            msgs = [m[0] for m in data.get("messages", []) if m]
            total = data.get("total_results", 0)
            return msgs, total
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimitError(int(e.headers.get("Retry-After", "5")) + 1)
        raise

def fetch_channel_messages(channel_id, hdrs, before=None):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=100"
    if before:
        url += f"&before={before}"
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimitError(int(e.headers.get("Retry-After", "5")) + 1)
        raise

def delete_message(channel_id, msg_id, hdrs):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages/{msg_id}"
    req = urllib.request.Request(url, headers=hdrs, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 204
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimitError(int(e.headers.get("Retry-After", "5")) + 1)
        if e.code == 404:
            return True  # already gone
        raise

def get_user(hdrs):
    try:
        req = urllib.request.Request("https://discord.com/api/v9/users/@me", headers=hdrs)
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
            return d.get("id"), d.get("username", "?")
    except:
        return None, None

# ── Animated dot ─────────────────────────────────────────────────────────────
class AnimDot(tk.Canvas):
    def __init__(self, parent, color=C["green"], size=10, **kw):
        super().__init__(parent, width=size, height=size, bg=parent.cget("bg"),
                         highlightthickness=0, **kw)
        self._c = color; self._s = size; self._active = False; self._ph = 0
        self._draw(1.0)
    def _draw(self, scale):
        self.delete("all")
        s = self._s; r = (s/2)*scale
        self.create_oval(s/2-r, s/2-r, s/2+r, s/2+r,
                         fill=self._c if self._active else C["dim"], outline="")
    def start(self): self._active = True; self._animate()
    def stop(self): self._active = False; self._draw(1.0)
    def _animate(self):
        if not self._active: return
        self._ph = (self._ph + 0.15) % (2 * math.pi)
        self._draw(0.6 + 0.4 * abs(math.sin(self._ph)))
        self.after(60, self._animate)

# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wiper — Discord Message Deleter")
        self.geometry("860x640"); self.minsize(720, 520)
        self.configure(bg=C["bg"])
        self._stop = threading.Event()
        self._deleted = 0; self._skipped = 0
        self._log_store = []
        self._active_view = tk.StringVar(value="setup")
        self._running = False
        self._pb_phase = 0
        self._build()

    def _build(self):
        self._sidebar = tk.Frame(self, bg=C["sidebar"], width=210)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._content = tk.Frame(self, bg=C["bg"])
        self._content.pack(side="left", fill="both", expand=True)
        self._build_sidebar()
        self._build_main("setup")

    def _build_sidebar(self):
        s = self._sidebar
        logo = tk.Frame(s, bg=C["sidebar"], height=62)
        logo.pack(fill="x"); logo.pack_propagate(False)
        tk.Frame(logo, bg=C["accent"], width=3).pack(side="left", fill="y")
        tk.Label(logo, text="⌫", bg=C["sidebar"], fg=C["accent"],
                 font=("Segoe UI", 22)).pack(side="left", padx=(14, 6))
        tk.Label(logo, text="Wiper", bg=C["sidebar"], fg=C["text"],
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(s, text="discord message deleter", bg=C["sidebar"],
                 fg=C["dim"], font=("Segoe UI", 7)).pack(anchor="w", padx=18, pady=(0, 12))
        tk.Frame(s, bg=C["border"], height=1).pack(fill="x", padx=16)

        nav = [("⌖  Setup", "setup"), ("◎  Log", "log"), ("?  How to use", "help")]
        self._nav_btns = {}
        for label, view in nav:
            b = tk.Button(s, text=label, anchor="w", bg=C["sidebar"], fg=C["muted"],
                          font=("Segoe UI", 10), relief="flat", cursor="hand2",
                          activebackground=C["card"], activeforeground=C["text"],
                          padx=20, pady=10, bd=0,
                          command=lambda v=view: self._switch(v))
            b.pack(fill="x"); self._nav_btns[view] = b
        self._set_nav("setup")

        tk.Frame(s, bg=C["sidebar"]).pack(fill="both", expand=True)
        tk.Frame(s, bg=C["border"], height=1).pack(fill="x", padx=16)
        sf = tk.Frame(s, bg=C["sidebar"], pady=14); sf.pack(fill="x")
        dr = tk.Frame(sf, bg=C["sidebar"]); dr.pack(fill="x", padx=16)
        self._dot = AnimDot(dr, size=10); self._dot.pack(side="left", padx=(0, 8))
        self._status_lbl = tk.Label(dr, text="Idle", bg=C["sidebar"],
                                    fg=C["muted"], font=("Segoe UI", 9))
        self._status_lbl.pack(side="left")
        self._user_lbl = tk.Label(sf, text="Not connected", bg=C["sidebar"],
                                  fg=C["dim"], font=("Segoe UI", 8))
        self._user_lbl.pack(anchor="w", padx=16, pady=(4, 0))

    def _set_nav(self, active):
        for name, btn in self._nav_btns.items():
            btn.config(bg=C["card"] if name == active else C["sidebar"],
                       fg=C["text"] if name == active else C["muted"])

    def _switch(self, view):
        self._set_nav(view); self._active_view.set(view)
        for w in self._content.winfo_children(): w.destroy()
        self._build_main(view)

    def _build_main(self, view):
        if view == "setup": self._build_setup()
        elif view == "log": self._build_log_view()
        elif view == "help": self._build_help()

    # ── Setup ─────────────────────────────────────────────────────────────────
    def _build_setup(self):
        f = tk.Frame(self._content, bg=C["bg"], padx=28, pady=24)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="Setup", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 6))
        tk.Label(f, text="Paste the fetch() command from your browser's Network tab.",
                 bg=C["bg"], fg=C["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 16))

        self._mk_card(f, "FETCH COMMAND", self._input_card).pack(fill="x", pady=(0, 12))
        self._mk_card(f, "AUTH TOKEN  (optional — only if not in fetch command above)", self._token_card).pack(fill="x", pady=(0, 16))

        br = tk.Frame(f, bg=C["bg"]); br.pack(fill="x")
        self._start_btn = tk.Button(br, text="  ▶  Start Cleaning  ",
            bg=C["accent"], fg="white", font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", padx=10, pady=10,
            activebackground="#4752c4", activeforeground="white",
            command=self._start)
        self._start_btn.pack(side="left")
        self._stop_btn = tk.Button(br, text="  ■  Stop  ",
            bg=C["card"], fg=C["muted"], font=("Segoe UI", 11),
            relief="flat", cursor="hand2", padx=10, pady=10,
            activebackground=C["border"], activeforeground=C["text"],
            state="disabled", command=self._do_stop)
        self._stop_btn.pack(side="left", padx=(10, 0))

        sr = tk.Frame(f, bg=C["bg"]); sr.pack(fill="x", pady=(20, 0))
        for col, (lbl, attr, color) in enumerate([
            ("DELETED", "_del_var", C["green"]),
            ("SKIPPED", "_skip_var", C["yellow"]),
        ]):
            setattr(self, attr, tk.StringVar(value="0"))
            sc = tk.Frame(sr, bg=C["card"], padx=20, pady=14)
            sc.grid(row=0, column=col, padx=(0, 12), sticky="nsew")
            sr.columnconfigure(col, weight=1)
            tk.Label(sc, text=lbl, bg=C["card"], fg=C["muted"],
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(sc, textvariable=getattr(self, attr), bg=C["card"],
                     fg=color, font=("Segoe UI", 26, "bold")).pack(anchor="w")

        pb = tk.Frame(f, bg=C["bg"]); pb.pack(fill="x", pady=(14, 0))
        self._pb_bg = tk.Frame(pb, bg=C["card"], height=4); self._pb_bg.pack(fill="x")
        self._pb = tk.Frame(self._pb_bg, bg=C["accent"], height=4)
        self._pb.place(x=0, y=0, relheight=1, relwidth=0)

    def _mk_card(self, parent, title, content_fn):
        outer = tk.Frame(parent, bg=C["card"])
        tk.Label(outer, text=title, bg=C["card"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold"), padx=16, pady=10).pack(anchor="w")
        tk.Frame(outer, bg=C["border"], height=1).pack(fill="x")
        inner = tk.Frame(outer, bg=C["card"], padx=16, pady=12); inner.pack(fill="x")
        content_fn(inner); return outer

    def _input_card(self, p):
        self._fetch_input = tk.Text(p, height=7, bg=C["panel"], fg=C["text"],
            insertbackground=C["accent"], font=("Consolas", 9),
            relief="flat", bd=0, padx=10, pady=8, wrap="word",
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent"])
        self._fetch_input.pack(fill="x")

    def _token_card(self, p):
        row = tk.Frame(p, bg=C["card"]); row.pack(fill="x")
        self._token_var = tk.StringVar()
        self._tok_e = tk.Entry(row, textvariable=self._token_var,
            bg=C["panel"], fg=C["text"], insertbackground=C["accent"],
            font=("Consolas", 9), relief="flat", bd=0,
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent"], show="•")
        self._tok_e.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self._rev = tk.Button(row, text="Show", bg=C["card"], fg=C["muted"],
            font=("Segoe UI", 8), relief="flat", cursor="hand2",
            command=lambda: [
                self._tok_e.config(show="" if self._tok_e.cget("show") == "•" else "•"),
                self._rev.config(text="Hide" if self._tok_e.cget("show") == "" else "Show")
            ])
        self._rev.pack(side="left")

    # ── Log view ──────────────────────────────────────────────────────────────
    def _build_log_view(self):
        f = tk.Frame(self._content, bg=C["bg"], padx=28, pady=24)
        f.pack(fill="both", expand=True)
        hr = tk.Frame(f, bg=C["bg"]); hr.pack(fill="x", pady=(0, 14))
        tk.Label(hr, text="Log", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Button(hr, text="Clear", bg=C["card"], fg=C["muted"],
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._clear_log).pack(side="right")
        wrap = tk.Frame(f, bg=C["panel"], highlightthickness=1,
                        highlightbackground=C["border"])
        wrap.pack(fill="both", expand=True)
        self._lcanvas = tk.Canvas(wrap, bg=C["panel"], highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self._lcanvas.yview)
        self._lcanvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._lcanvas.pack(side="left", fill="both", expand=True)
        self._linner = tk.Frame(self._lcanvas, bg=C["panel"])
        self._lwin = self._lcanvas.create_window((0, 0), window=self._linner, anchor="nw")
        self._linner.bind("<Configure>", lambda e: self._lcanvas.configure(
            scrollregion=self._lcanvas.bbox("all")))
        self._lcanvas.bind("<Configure>", lambda e: self._lcanvas.itemconfig(
            self._lwin, width=e.width))
        ICONS = {"ok": "✓", "warn": "⚠", "error": "✕", "info": "·"}
        COLS = {"ok": C["green"], "warn": C["yellow"], "error": C["red"], "info": C["muted"]}
        for ts, msg, kind in self._log_store:
            self._render_row(ts, msg, kind)

    def _render_row(self, ts, msg, kind):
        if not hasattr(self, "_linner") or not self._linner.winfo_exists(): return
        ICONS = {"ok": "✓", "warn": "⚠", "error": "✕", "info": "·"}
        COLS = {"ok": C["green"], "warn": C["yellow"], "error": C["red"], "info": C["muted"]}
        color = COLS.get(kind, C["muted"])
        row = tk.Frame(self._linner, bg=C["panel"]); row.pack(fill="x", pady=1)
        tk.Label(row, text=ICONS.get(kind, "·"), fg=color, bg=C["panel"],
                 font=("Consolas", 10, "bold"), width=2).pack(side="left", padx=(8, 4))
        tk.Label(row, text=ts, fg=C["dim"], bg=C["panel"],
                 font=("Consolas", 9)).pack(side="left", padx=(0, 8))
        tk.Label(row, text=msg, fg=color if kind != "info" else C["text"],
                 bg=C["panel"], font=("Segoe UI", 9), anchor="w",
                 justify="left", wraplength=500).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._lcanvas.update_idletasks()
        self._lcanvas.yview_moveto(1.0)

    # ── Help ──────────────────────────────────────────────────────────────────
    def _build_help(self):
        f = tk.Frame(self._content, bg=C["bg"], padx=28, pady=24)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="How to use", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 18))
        steps = [
            ("METHOD A — Guild search fetch (what you have!)",
             "1. Open Discord in Chrome and go to any channel in the server.\n"
             "2. Press F12 → Network tab.\n"
             "3. Use Discord's search bar (top right) → filter by 'From: You'.\n"
             "4. In Network tab, find the request:  guilds/.../messages/search?author_id=...\n"
             "5. Right-click → Copy → Copy as fetch → paste into the input box.\n"
             "   The app will search all your messages in that server and delete them."),
            ("METHOD B — Channel messages fetch",
             "1. Open Discord in browser, go to the channel.\n"
             "2. F12 → Network tab → scroll up in chat.\n"
             "3. Find  messages?limit=50  → right-click → Copy as fetch → paste."),
            ("⚠  Safety notes",
             "• Never share your auth token — it gives full account access.\n"
             "• Automating your account may violate Discord ToS.\n"
             "• 5–8 second delays between deletes reduce ban risk.\n"
             "• Everything runs locally — nothing is sent anywhere else."),
        ]
        for title, body in steps:
            c = tk.Frame(f, bg=C["card"], padx=18, pady=14); c.pack(fill="x", pady=(0, 10))
            tk.Label(c, text=title, bg=C["card"], fg=C["accent"],
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(c, text=body, bg=C["card"], fg=C["text"],
                     font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(6, 0))

    # ── Logging ───────────────────────────────────────────────────────────────
    def _log(self, msg, kind="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_store.append((ts, msg, kind))
        if self._active_view.get() == "log":
            self._render_row(ts, msg, kind)

    def _clear_log(self):
        self._log_store = []
        if hasattr(self, "_linner") and self._linner.winfo_exists():
            for w in self._linner.winfo_children(): w.destroy()

    def _update_stats(self):
        if hasattr(self, "_del_var"): self._del_var.set(str(self._deleted))
        if hasattr(self, "_skip_var"): self._skip_var.set(str(self._skipped))

    def _set_status(self, text, color=C["muted"], running=False):
        self._status_lbl.config(text=text, fg=color)
        self._dot.start() if running else self._dot.stop()

    def _animate_pb(self):
        if not hasattr(self, "_pb") or not self._pb.winfo_exists(): return
        if not self._running: self._pb.place(relwidth=0); return
        self._pb_phase += 0.04
        self._pb.place(relwidth=(math.sin(self._pb_phase) + 1) / 2, relheight=1)
        self.after(40, self._animate_pb)

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _start(self):
        text = self._fetch_input.get("1.0", "end").strip()
        if not text:
            self._log("Paste a fetch command first.", "error")
            self._switch("log"); return
        parsed = parse_fetch(text, self._token_var.get())
        if not parsed:
            self._log("Couldn't parse — make sure it's a Discord fetch command with a valid URL.", "error")
            self._switch("log"); return

        self._stop.clear(); self._deleted = 0; self._skipped = 0
        self._update_stats()
        if hasattr(self, "_start_btn"):
            self._start_btn.config(state="disabled")
            self._stop_btn.config(state="normal")
        self._running = True
        self._set_status("Running…", C["green"], running=True)
        self._pb_phase = 0; self._animate_pb()
        self._switch("log")
        threading.Thread(target=self._run, args=(parsed,), daemon=True).start()

    def _do_stop(self):
        self._stop.set(); self._log("Stop requested…", "warn")

    def _finish(self):
        self._running = False
        self._set_status("Done", C["green"])
        if hasattr(self, "_start_btn"):
            self._start_btn.config(state="normal")
            self._stop_btn.config(state="disabled")

    # ── Worker ────────────────────────────────────────────────────────────────
    def _run(self, parsed):
        hdrs = make_headers(parsed)
        mode = parsed["mode"]

        self.after(0, self._log, "Identifying account…", "info")
        uid, uname = get_user(hdrs)
        if uid:
            self.after(0, lambda: self._user_lbl.config(text=f"@{uname}"))
            self.after(0, self._log, f"Logged in as @{uname}", "ok")
        else:
            self.after(0, self._log, "Couldn't verify account — proceeding.", "warn")

        if mode == "guild_search":
            self._run_guild_search(parsed, hdrs, uid)
        elif mode == "channel":
            self._run_channel(parsed, hdrs, uid)
        else:
            self.after(0, self._log, "Unknown mode.", "error")

        self.after(0, self._log,
                   f"Session ended — deleted {self._deleted}, skipped {self._skipped}", "ok")
        self.after(0, self._finish)

    def _run_guild_search(self, parsed, hdrs, uid):
        guild_id = parsed["guild_id"]
        author_id = parsed.get("author_id") or uid
        if not author_id:
            self.after(0, self._log, "Couldn't determine author_id.", "error"); return

        self.after(0, self._log, f"Searching guild {guild_id} for your messages…", "info")
        offset = 0

        while not self._stop.is_set():
            # Small delay before each search (Discord rate-limits search heavily)
            self._stop.wait(random.uniform(1.5, 2.5))
            if self._stop.is_set(): break

            try:
                msgs, total = search_messages(guild_id, author_id, hdrs, offset)
            except RateLimitError as e:
                self.after(0, self._log, f"Rate limited — waiting {e.retry_after}s", "warn")
                self._stop.wait(e.retry_after); continue
            except Exception as ex:
                self.after(0, self._log, f"Search error: {ex}", "error"); break

            if not msgs:
                self.after(0, self._log, "No more messages found. All done! 🎉", "ok"); break

            self.after(0, self._log, f"Found {len(msgs)} messages (total ~{total})…", "info")

            for msg in msgs:
                if self._stop.is_set(): break
                channel_id = msg.get("channel_id")
                msg_id = msg.get("id")
                preview = (msg.get("content", "")[:55] or "[media/embed]")
                if not channel_id or not msg_id: continue

                try:
                    delete_message(channel_id, msg_id, hdrs)
                    self._deleted += 1
                    self.after(0, self._log, f"Deleted: {preview}", "ok")
                    self.after(0, self._update_stats)
                except RateLimitError as e:
                    self.after(0, self._log, f"Rate limited — waiting {e.retry_after}s", "warn")
                    self._stop.wait(e.retry_after)
                    try:
                        delete_message(channel_id, msg_id, hdrs)
                        self._deleted += 1; self.after(0, self._update_stats)
                    except Exception as ex2:
                        self.after(0, self._log, f"Failed: {ex2}", "error")
                except Exception as ex:
                    self.after(0, self._log, f"Error: {ex}", "error")

                self._stop.wait(random.uniform(5, 8))

            # Don't increment offset — after deleting, search from offset=0 again
            # because the results shift as messages are removed

    def _run_channel(self, parsed, hdrs, uid):
        channel_id = parsed["channel_id"]
        self.after(0, self._log, f"Scanning channel {channel_id}…", "info")
        before = None; empty = 0

        while not self._stop.is_set():
            try:
                msgs = fetch_channel_messages(channel_id, hdrs, before)
            except RateLimitError as e:
                self.after(0, self._log, f"Rate limited — waiting {e.retry_after}s", "warn")
                self._stop.wait(e.retry_after); continue
            except Exception as ex:
                self.after(0, self._log, f"Fetch error: {ex}", "error"); break

            if not msgs:
                empty += 1
                if empty >= 2: self.after(0, self._log, "All done! 🎉", "ok"); break
                self._stop.wait(2); continue

            empty = 0
            mine = [m for m in msgs if uid is None or m.get("author", {}).get("id") == uid]
            other = len(msgs) - len(mine)
            if other: self._skipped += other; self.after(0, self._update_stats)
            before = msgs[-1]["id"]
            if not mine: self._stop.wait(random.uniform(1, 2)); continue

            for msg in mine:
                if self._stop.is_set(): break
                mid = msg["id"]; preview = (msg.get("content", "")[:55] or "[media/embed]")
                try:
                    delete_message(channel_id, mid, hdrs)
                    self._deleted += 1
                    self.after(0, self._log, f"Deleted: {preview}", "ok")
                    self.after(0, self._update_stats)
                except RateLimitError as e:
                    self.after(0, self._log, f"Rate limited — waiting {e.retry_after}s", "warn")
                    self._stop.wait(e.retry_after)
                    try:
                        delete_message(channel_id, mid, hdrs); self._deleted += 1
                        self.after(0, self._update_stats)
                    except Exception as ex2:
                        self.after(0, self._log, f"Failed: {ex2}", "error")
                except Exception as ex:
                    self.after(0, self._log, f"Error: {ex}", "error")
                self._stop.wait(random.uniform(5, 8))

if __name__ == "__main__":
    app = App(); app.mainloop()
