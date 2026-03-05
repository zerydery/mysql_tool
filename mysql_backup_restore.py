"""
MySQL Backup & Restore Tool
===========================
Requirements:
    pip install mysql-connector-python
    mysqldump and mysql executables must be in PATH (comes with MySQL Server installation)

Usage:
    python mysql_backup_restore.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import threading
import os
import json
import datetime
import shutil
import sys

# ─────────────────────────────────────────────────────────
# Configuration file (saved next to this script)
# ─────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mysql_backup_config.json")

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": "3306",
    "user": "root",
    "password": "",
    "last_backup_dir": os.path.expanduser("~\\Documents"),
    "history": []
}

# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            # merge missing keys
            for k, v in DEFAULT_CONFIG.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def find_mysql_exe(name):
    """Try to locate mysqldump / mysql executable across all common locations and drives."""
    # 1. Check if already in PATH
    found = shutil.which(name)
    if found:
        return found

    # 2. Dynamically scan all drive letters for XAMPP, Laragon, MySQL Server
    drives = [f"{d}:\\" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ"
              if os.path.exists(f"{d}:\\")]

    candidates = []
    for drv in drives:
        candidates += [
            os.path.join(drv, "xampp", "mysql", "bin", f"{name}.exe"),
            os.path.join(drv, "xampp64", "mysql", "bin", f"{name}.exe"),
            os.path.join(drv, "laragon", "bin", "mysql", "mysql-8.0.30-winx64", "bin", f"{name}.exe"),
            os.path.join(drv, "laragon", "bin", "mysql", "mysql-5.7.33-winx64", "bin", f"{name}.exe"),
        ]
        # MySQL Server versions 5.5 – 9.x
        for ver in ["5.5", "5.6", "5.7", "8.0", "8.1", "8.2", "8.3", "8.4", "9.0"]:
            candidates.append(
                os.path.join(drv, "Program Files", "MySQL",
                             f"MySQL Server {ver}", "bin", f"{name}.exe"))
            candidates.append(
                os.path.join(drv, "Program Files (x86)", "MySQL",
                             f"MySQL Server {ver}", "bin", f"{name}.exe"))

    for c in candidates:
        if os.path.exists(c):
            return c

    return name  # fallback – let subprocess raise a clear error

# ─────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────
class MySQLBackupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MySQL Backup & Restore Tool")
        self.geometry("860x640")
        self.resizable(True, True)
        self.config = load_config()

        self._apply_theme()
        self._build_ui()
        self._load_config_to_ui()

    # ── Theme ─────────────────────────────────────────────
    def _apply_theme(self):
        self.configure(bg="#1e1e2e")
        style = ttk.Style(self)
        style.theme_use("clam")

        bg   = "#1e1e2e"
        fg   = "#cdd6f4"
        acc  = "#89b4fa"
        acc2 = "#313244"
        entry_bg = "#181825"
        red  = "#f38ba8"
        grn  = "#a6e3a1"

        style.configure(".",           background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("TFrame",      background=bg)
        style.configure("TLabel",      background=bg, foreground=fg)
        style.configure("TLabelframe", background=bg, foreground=acc, bordercolor=acc2)
        style.configure("TLabelframe.Label", background=bg, foreground=acc, font=("Segoe UI", 10, "bold"))
        style.configure("TButton",     background=acc2, foreground=fg, relief="flat", padding=(10, 5))
        style.map("TButton",
                  background=[("active", acc), ("pressed", "#7aa2f7")],
                  foreground=[("active", "#1e1e2e")])
        style.configure("Accent.TButton", background=acc, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=(12, 6))
        style.map("Accent.TButton", background=[("active", "#7aa2f7")])
        style.configure("Red.TButton",    background=red, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=(12, 6))
        style.map("Red.TButton",    background=[("active", "#eb83a0")])
        style.configure("Green.TButton",  background=grn, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=(12, 6))
        style.map("Green.TButton",  background=[("active", "#90d48e")])
        style.configure("TEntry",      fieldbackground=entry_bg, foreground=fg, insertcolor=fg, relief="flat")
        style.configure("TCombobox",   fieldbackground=entry_bg, foreground=fg, selectbackground=acc2, selectforeground=fg)
        style.map("TCombobox", fieldbackground=[("readonly", entry_bg)])
        style.configure("TNotebook",           background=bg, borderwidth=0)
        style.configure("TNotebook.Tab",       background=acc2, foreground=fg, padding=(14, 6))
        style.map("TNotebook.Tab",             background=[("selected", acc)], foreground=[("selected", "#1e1e2e")])
        style.configure("TScrollbar",          background=acc2, troughcolor=bg, arrowcolor=fg)
        style.configure("Treeview",            background="#181825", foreground=fg, fieldbackground="#181825", rowheight=24)
        style.configure("Treeview.Heading",    background=acc2, foreground=acc, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", acc)], foreground=[("selected", "#1e1e2e")])
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("TProgressbar", troughcolor=acc2, background=acc)

        self.colors = {"bg": bg, "fg": fg, "acc": acc, "acc2": acc2,
                       "entry": entry_bg, "red": red, "grn": grn}

    # ── UI Builder ────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#89b4fa", height=56)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🗄️  MySQL Backup & Restore Tool",
                 font=("Segoe UI", 16, "bold"),
                 bg="#89b4fa", fg="#1e1e2e", pady=10).pack(side="left", padx=20)

        # Notebook
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=10)

        self.tab_backup  = ttk.Frame(nb)
        self.tab_restore = ttk.Frame(nb)
        self.tab_history = ttk.Frame(nb)
        self.tab_settings = ttk.Frame(nb)

        nb.add(self.tab_backup,  text="  💾 Backup  ")
        nb.add(self.tab_restore, text="  🔄 Restore  ")
        nb.add(self.tab_history, text="  📋 History  ")
        nb.add(self.tab_settings, text="  ⚙️  Settings  ")

        self._build_backup_tab()
        self._build_restore_tab()
        self._build_history_tab()
        self._build_settings_tab()

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        sb = tk.Label(self, textvariable=self.status_var, anchor="w",
                      bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9), pady=4)
        sb.pack(fill="x", side="bottom", padx=0)

    # ── Backup Tab ────────────────────────────────────────
    def _build_backup_tab(self):
        p = ttk.Frame(self.tab_backup, padding=16)
        p.pack(fill="both", expand=True)

        # Connection group
        cg = ttk.LabelFrame(p, text=" 🔌 MySQL Connection ", padding=12)
        cg.pack(fill="x", pady=(0, 12))

        self._conn_fields_backup = self._make_conn_fields(cg)
        btn_con = ttk.Button(cg, text="🔗  Connect & List Databases",
                             command=self._backup_connect, style="Accent.TButton")
        btn_con.grid(row=4, column=0, columnspan=4, pady=(12, 0), sticky="w")

        # Database selection
        dg = ttk.LabelFrame(p, text=" 🗃️  Select Database ", padding=12)
        dg.pack(fill="x", pady=(0, 12))

        self.backup_db_var = tk.StringVar()
        self.backup_db_combo = ttk.Combobox(dg, textvariable=self.backup_db_var,
                                            state="readonly", width=40, font=("Segoe UI", 10))
        self.backup_db_combo.pack(side="left", padx=(0, 12))
        ttk.Button(dg, text="⟳ Refresh", command=self._backup_connect).pack(side="left")

        chk_frame = ttk.Frame(dg)
        chk_frame.pack(side="right")
        self.all_db_var = tk.BooleanVar()
        ttk.Checkbutton(chk_frame, text="Backup ALL databases", variable=self.all_db_var,
                        command=self._toggle_all_db).pack()

        # Destination
        destg = ttk.LabelFrame(p, text=" 📁 Backup Destination ", padding=12)
        destg.pack(fill="x", pady=(0, 12))

        self.backup_path_var = tk.StringVar(value=self.config["last_backup_dir"])
        ttk.Entry(destg, textvariable=self.backup_path_var, width=60,
                  font=("Segoe UI", 10)).pack(side="left", padx=(0, 8), fill="x", expand=True)
        ttk.Button(destg, text="Browse…", command=self._browse_backup_dir).pack(side="left")

        # Options
        og = ttk.LabelFrame(p, text=" 🛠️  Options ", padding=12)
        og.pack(fill="x", pady=(0, 12))

        self.compress_var     = tk.BooleanVar(value=False)
        self.include_rout_var = tk.BooleanVar(value=False)
        self.no_data_var      = tk.BooleanVar(value=False)
        ttk.Checkbutton(og, text="Compress (.zip) – saves space",
                        variable=self.compress_var).grid(row=0, column=0, sticky="w", padx=8)
        ttk.Checkbutton(og, text="Include Routines & Triggers",
                        variable=self.include_rout_var).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Checkbutton(og, text="Schema only (no data)",
                        variable=self.no_data_var).grid(row=0, column=2, sticky="w", padx=8)

        # Action
        ttk.Button(p, text="💾  Start Backup", command=self._do_backup,
                   style="Accent.TButton").pack(pady=8, anchor="w")

        # Log
        lg = ttk.LabelFrame(p, text=" 📝 Log ", padding=8)
        lg.pack(fill="both", expand=True)
        self.backup_log = self._make_log(lg)

    # ── Restore Tab ───────────────────────────────────────
    def _build_restore_tab(self):
        p = ttk.Frame(self.tab_restore, padding=16)
        p.pack(fill="both", expand=True)

        cg = ttk.LabelFrame(p, text=" 🔌 MySQL Connection ", padding=12)
        cg.pack(fill="x", pady=(0, 12))
        self._conn_fields_restore = self._make_conn_fields(cg)
        ttk.Button(cg, text="🔗  Connect & List Databases",
                   command=self._restore_connect, style="Accent.TButton").grid(
                   row=4, column=0, columnspan=4, pady=(12, 0), sticky="w")

        # Source file
        sg = ttk.LabelFrame(p, text=" 📂 Backup File (.sql)", padding=12)
        sg.pack(fill="x", pady=(0, 12))
        self.restore_file_var = tk.StringVar()
        ttk.Entry(sg, textvariable=self.restore_file_var, width=60,
                  font=("Segoe UI", 10)).pack(side="left", padx=(0, 8), fill="x", expand=True)
        ttk.Button(sg, text="Browse…", command=self._browse_restore_file).pack(side="left")

        # Target database
        tg = ttk.LabelFrame(p, text=" 🗃️  Target Database ", padding=12)
        tg.pack(fill="x", pady=(0, 12))

        tk.Label(tg, text="Restore into:", bg=self.colors["bg"],
                 fg=self.colors["fg"]).pack(side="left", padx=(0, 8))
        self.restore_db_var = tk.StringVar()
        self.restore_db_combo = ttk.Combobox(tg, textvariable=self.restore_db_var,
                                             state="normal", width=35, font=("Segoe UI", 10))
        self.restore_db_combo.pack(side="left", padx=(0, 12))

        self.create_db_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(tg, text="Create database if not exists",
                        variable=self.create_db_var).pack(side="left")

        # Action
        ttk.Button(p, text="🔄  Start Restore", command=self._do_restore,
                   style="Red.TButton").pack(pady=8, anchor="w")

        lg = ttk.LabelFrame(p, text=" 📝 Log ", padding=8)
        lg.pack(fill="both", expand=True)
        self.restore_log = self._make_log(lg)

    # ── History Tab ───────────────────────────────────────
    def _build_history_tab(self):
        p = ttk.Frame(self.tab_history, padding=16)
        p.pack(fill="both", expand=True)

        cols = ("timestamp", "action", "database", "file", "status")
        self.hist_tree = ttk.Treeview(p, columns=cols, show="headings", height=18)
        for col, w, lbl in zip(cols, [155, 70, 160, 280, 80],
                               ["Timestamp", "Action", "Database", "File", "Status"]):
            self.hist_tree.heading(col, text=lbl)
            self.hist_tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(p, orient="vertical", command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=vsb.set)
        self.hist_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        btn_frame = ttk.Frame(self.tab_history)
        btn_frame.pack(fill="x", padx=16, pady=(0, 10))
        ttk.Button(btn_frame, text="⟳ Refresh", command=self._refresh_history).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🗑️  Clear History",
                   command=self._clear_history, style="Red.TButton").pack(side="left", padx=4)

        self._refresh_history()

    # ── Settings Tab ─────────────────────────────────────
    def _build_settings_tab(self):
        p = ttk.Frame(self.tab_settings, padding=24)
        p.pack(fill="both", expand=True)

        ttk.Label(p, text="Default MySQL Connection Settings",
                  font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=3,
                                                       sticky="w", pady=(0, 16))
        fields = [("Host:", "s_host"), ("Port:", "s_port"),
                  ("User:", "s_user"), ("Password:", "s_pass")]
        self._settings_vars = {}
        for i, (lbl, key) in enumerate(fields):
            ttk.Label(p, text=lbl).grid(row=i+1, column=0, sticky="w", pady=6, padx=(0, 12))
            var = tk.StringVar()
            self._settings_vars[key] = var
            show = "*" if key == "s_pass" else ""
            ttk.Entry(p, textvariable=var, width=32, show=show).grid(row=i+1, column=1, sticky="w")

        ttk.Label(p, text="Default Backup Directory:").grid(row=6, column=0, sticky="w", pady=6)
        self.s_backup_dir = tk.StringVar()
        ttk.Entry(p, textvariable=self.s_backup_dir, width=45).grid(row=6, column=1, sticky="w")
        ttk.Button(p, text="Browse…", command=self._browse_settings_dir).grid(row=6, column=2, padx=8)

        ttk.Button(p, text="💾  Save Settings", command=self._save_settings,
                   style="Green.TButton").grid(row=8, column=0, columnspan=2, sticky="w", pady=20)

        # mysqldump path info
        ttk.Separator(p, orient="horizontal").grid(row=9, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(p, text="mysqldump detected at:").grid(row=10, column=0, sticky="w")
        dump_exe = find_mysql_exe("mysqldump")
        ttk.Label(p, text=dump_exe, foreground=self.colors["acc"]).grid(row=10, column=1, sticky="w")
        ttk.Label(p, text="mysql detected at:").grid(row=11, column=0, sticky="w", pady=4)
        mysql_exe = find_mysql_exe("mysql")
        ttk.Label(p, text=mysql_exe, foreground=self.colors["acc"]).grid(row=11, column=1, sticky="w")

    # ── Shared widgets ────────────────────────────────────
    def _make_conn_fields(self, parent):
        """Renders host/port/user/pass fields and returns their StringVars."""
        labels  = ["Host:", "Port:", "User:", "Password:"]
        keys    = ["host",  "port",  "user",  "password"]
        widths  = [22, 8, 18, 22]
        vars_   = {}
        for col, (lbl, key, w) in enumerate(zip(labels, keys, widths)):
            ttk.Label(parent, text=lbl).grid(row=0, column=col*2, sticky="w", padx=(8 if col else 0, 4))
            var = tk.StringVar(value=self.config.get(key, ""))
            vars_[key] = var
            show = "*" if key == "password" else ""
            ttk.Entry(parent, textvariable=var, width=w, show=show).grid(row=0, column=col*2+1, sticky="w", padx=(0, 12))
        return vars_

    def _make_log(self, parent):
        txt = scrolledtext.ScrolledText(parent, height=8, bg="#181825", fg="#cdd6f4",
                                        font=("Consolas", 9), insertbackground="#cdd6f4",
                                        relief="flat", wrap="word")
        txt.pack(fill="both", expand=True)
        txt.configure(state="disabled")
        return txt

    def _set_status(self, msg):
        self.after(0, lambda: self.status_var.set(msg))

    def _log(self, widget, msg, color=None):
        def _do_log():
            widget.configure(state="normal")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            widget.insert("end", f"[{ts}] {msg}\n")
            if color:
                # tag last line
                last = float(widget.index("end")) - 1
                widget.tag_add(color, f"{last:.1f} linestart", f"{last:.1f} lineend")
                widget.tag_config(color, foreground=color)
            widget.see("end")
            widget.configure(state="disabled")
        self.after(0, _do_log)

    # ── Config load ───────────────────────────────────────
    def _load_config_to_ui(self):
        cfg = self.config
        sv = self._settings_vars
        sv["s_host"].set(cfg.get("host", "127.0.0.1"))
        sv["s_port"].set(cfg.get("port", "3306"))
        sv["s_user"].set(cfg.get("user", "root"))
        sv["s_pass"].set(cfg.get("password", ""))
        self.s_backup_dir.set(cfg.get("last_backup_dir", os.path.expanduser("~")))

    # ── Save settings ─────────────────────────────────────
    def _save_settings(self):
        sv = self._settings_vars
        self.config["host"]            = sv["s_host"].get()
        self.config["port"]            = sv["s_port"].get()
        self.config["user"]            = sv["s_user"].get()
        self.config["password"]        = sv["s_pass"].get()
        self.config["last_backup_dir"] = self.s_backup_dir.get()
        save_config(self.config)
        # sync to both conn panels
        for key in ("host", "port", "user", "password"):
            for fields in (self._conn_fields_backup, self._conn_fields_restore):
                fields[key].set(self.config[key])
        self.backup_path_var.set(self.config["last_backup_dir"])
        messagebox.showinfo("Settings Saved", "Connection settings saved successfully.")

    def _browse_settings_dir(self):
        d = filedialog.askdirectory(title="Select Default Backup Directory")
        if d:
            self.s_backup_dir.set(d)

    # ── Backup helpers ────────────────────────────────────
    def _get_conn_args(self, fields):
        return {k: fields[k].get().strip() for k in ("host", "port", "user", "password")}

    def _list_databases(self, host, port, user, password):
        """Return list of database names, excluding system schemas."""
        cmd = [find_mysql_exe("mysql"),
               f"--host={host}", f"--port={port}",
               f"--user={user}"]
        if password:
            cmd.append(f"--password={password}")
        cmd += ["--batch", "--skip-column-names",
                "-e", "SHOW DATABASES;"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Connection failed")
        system_dbs = {"information_schema", "performance_schema", "mysql", "sys"}
        dbs = [line.strip() for line in result.stdout.strip().splitlines()
               if line.strip() and line.strip().lower() not in system_dbs]
        return dbs

    def _backup_connect(self):
        cf = self._get_conn_args(self._conn_fields_backup)
        try:
            self.status_var.set("Connecting…")
            dbs = self._list_databases(**cf)
            self.backup_db_combo["values"] = dbs
            if dbs:
                self.backup_db_combo.current(0)
            self.status_var.set(f"Connected. {len(dbs)} database(s) found.")
            self._log(self.backup_log, f"Connected to {cf['host']}:{cf['port']}. Found: {', '.join(dbs)}", "#a6e3a1")
        except Exception as e:
            self.status_var.set("Connection failed.")
            self._log(self.backup_log, f"ERROR: {e}", "#f38ba8")
            messagebox.showerror("Connection Error", str(e))

    def _restore_connect(self):
        cf = self._get_conn_args(self._conn_fields_restore)
        try:
            self.status_var.set("Connecting…")
            dbs = self._list_databases(**cf)
            self.restore_db_combo["values"] = dbs
            self.status_var.set(f"Connected. {len(dbs)} database(s) found.")
            self._log(self.restore_log, f"Connected to {cf['host']}:{cf['port']}", "#a6e3a1")
        except Exception as e:
            self.status_var.set("Connection failed.")
            self._log(self.restore_log, f"ERROR: {e}", "#f38ba8")
            messagebox.showerror("Connection Error", str(e))

    def _toggle_all_db(self):
        state = "disabled" if self.all_db_var.get() else "normal"
        self.backup_db_combo.configure(state=state)

    def _browse_backup_dir(self):
        d = filedialog.askdirectory(title="Select Backup Directory",
                                    initialdir=self.backup_path_var.get())
        if d:
            self.backup_path_var.set(d)
            self.config["last_backup_dir"] = d
            save_config(self.config)

    def _browse_restore_file(self):
        f = filedialog.askopenfilename(
            title="Select SQL Backup File",
            initialdir=self.config.get("last_backup_dir", "~"),
            filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")])
        if f:
            self.restore_file_var.set(f)
            # Auto-detect db name from filename
            base = os.path.splitext(os.path.basename(f))[0]
            # strip timestamp suffix if present e.g. mydb_2024-01-01_12-00-00
            parts = base.rsplit("_", 3)
            guess = parts[0] if len(parts) >= 2 else base
            if not self.restore_db_var.get():
                self.restore_db_var.set(guess)

    # ── Backup execution ──────────────────────────────────
    def _do_backup(self):
        cf   = self._get_conn_args(self._conn_fields_backup)
        dest = self.backup_path_var.get().strip()
        all_db = self.all_db_var.get()
        db_name = self.backup_db_var.get().strip()

        if not dest:
            messagebox.showwarning("Missing", "Please select a backup destination folder.")
            return
        if not all_db and not db_name:
            messagebox.showwarning("Missing", "Please select a database or check 'Backup ALL databases'.")
            return

        os.makedirs(dest, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if all_db:
            filename = f"ALL_DATABASES_{ts}.sql"
        else:
            filename = f"{db_name}_{ts}.sql"
        filepath = os.path.join(dest, filename)

        self._log(self.backup_log, f"Starting backup → {filepath}")
        threading.Thread(target=self._run_backup,
                         args=(cf, db_name, all_db, filepath),
                         daemon=True).start()

    def _run_backup(self, cf, db_name, all_db, filepath):
        try:
            self._set_status("Backing up…")
            cmd = [find_mysql_exe("mysqldump"),
                   f"--host={cf['host']}", f"--port={cf['port']}",
                   f"--user={cf['user']}"]
            if cf["password"]:
                cmd.append(f"--password={cf['password']}")

            cmd += ["--single-transaction", "--quick", "--lock-tables=false"]

            if self.include_rout_var.get():
                cmd += ["--routines", "--triggers"]
            if self.no_data_var.get():
                cmd.append("--no-data")

            if all_db:
                cmd.append("--all-databases")
                label = "ALL DATABASES"
            else:
                cmd.append(db_name)
                label = db_name

            with open(filepath, "w", encoding="utf-8") as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE,
                                        text=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            if result.returncode == 0:
                final_path = filepath
                
                # Compress if requested
                if self.compress_var.get():
                    self._set_status("Compressing backup…")
                    import zipfile
                    zip_path = filepath + ".zip"
                    try:
                        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                            zf.write(filepath, os.path.basename(filepath))
                        os.remove(filepath) # Remove the uncompressed sql file
                        final_path = zip_path
                        self._log(self.backup_log, f"📦 Compressed successfully to {os.path.basename(final_path)}", "#a6e3a1")
                    except Exception as ze:
                        self._log(self.backup_log, f"⚠️ Compression failed: {ze}, keeping original .sql", "#fab387")
                
                size = os.path.getsize(final_path)
                size_str = f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.2f} MB"
                msg = f"✅ Backup SUCCESS — {label} → {final_path} ({size_str})"
                self._log(self.backup_log, msg, "#a6e3a1")
                self._set_status("Backup complete.")
                self._add_history("BACKUP", label, final_path, "OK")
            else:
                err = result.stderr.strip()
                self._log(self.backup_log, f"❌ FAILED: {err}", "#f38ba8")
                self._set_status("Backup failed.")
                self._add_history("BACKUP", label, filepath, "FAILED")
                if os.path.exists(filepath):
                    os.remove(filepath)
        except Exception as e:
            self._log(self.backup_log, f"❌ Exception: {e}", "#f38ba8")
            self._set_status("Backup error.")

    # ── Restore execution ─────────────────────────────────
    def _do_restore(self):
        cf       = self._get_conn_args(self._conn_fields_restore)
        src_file = self.restore_file_var.get().strip()
        db_name  = self.restore_db_var.get().strip()

        if not src_file or not os.path.exists(src_file):
            messagebox.showwarning("Missing", "Please select a valid .sql backup file.")
            return
        if not db_name:
            messagebox.showwarning("Missing", "Please enter or select the target database name.")
            return

        confirm = messagebox.askyesno(
            "Confirm Restore",
            f"⚠️  This will restore into database:\n\n  '{db_name}'\n\nAll existing data in that database will be OVERWRITTEN.\n\nContinue?")
        if not confirm:
            return

        self._log(self.restore_log, f"Starting restore: {src_file} → {db_name}")
        threading.Thread(target=self._run_restore,
                         args=(cf, db_name, src_file),
                         daemon=True).start()

    def _run_restore(self, cf, db_name, src_file):
        try:
            self._set_status("Restoring…")
            base_cmd = [find_mysql_exe("mysql"),
                        f"--host={cf['host']}", f"--port={cf['port']}",
                        f"--user={cf['user']}"]
            if cf["password"]:
                base_cmd.append(f"--password={cf['password']}")

            # Create database if needed
            if self.create_db_var.get():
                create_cmd = base_cmd + ["-e", f"CREATE DATABASE IF NOT EXISTS `{db_name}`;"]
                r = subprocess.run(create_cmd, capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if r.returncode != 0 and r.stderr:
                    self._log(self.restore_log, f"Warning (create db): {r.stderr.strip()}", "#fab387")

            import_cmd = base_cmd + [db_name]

            # Handle .zip extraction natively
            extract_dir = None
            sql_file_to_import = src_file
            
            if src_file.lower().endswith('.zip'):
                self._set_status("Extracting backup archive…")
                import zipfile
                import tempfile
                extract_dir = tempfile.mkdtemp()
                try:
                    with zipfile.ZipFile(src_file, 'r') as zf:
                        # Find the first .sql file in zip
                        sql_files = [f for f in zf.namelist() if f.lower().endswith('.sql')]
                        if not sql_files:
                            raise Exception("No .sql file found inside the ZIP archive.")
                        extracted_path = zf.extract(sql_files[0], extract_dir)
                        sql_file_to_import = extracted_path
                except Exception as ze:
                    self._log(self.restore_log, f"❌ ZIP extraction failed: {ze}", "#f38ba8")
                    self._set_status("Restore failed.")
                    if extract_dir and os.path.exists(extract_dir):
                        shutil.rmtree(extract_dir, ignore_errors=True)
                    return

            self._set_status("Importing SQL data…")
            with open(sql_file_to_import, "r", encoding="utf-8", errors="replace") as f:
                result = subprocess.run(import_cmd, stdin=f, capture_output=True,
                                        text=True, timeout=3600, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            # Cleanup temp zip extraction
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)

            if result.returncode == 0:
                msg = f"✅ Restore SUCCESS — {src_file} → {db_name}"
                self._log(self.restore_log, msg, "#a6e3a1")
                self._set_status("Restore complete.")
                self._add_history("RESTORE", db_name, src_file, "OK")
            else:
                err = result.stderr.strip()
                self._log(self.restore_log, f"❌ FAILED: {err}", "#f38ba8")
                self._set_status("Restore failed.")
                self._add_history("RESTORE", db_name, src_file, "FAILED")

        except Exception as e:
            self._log(self.restore_log, f"❌ Exception: {e}", "#f38ba8")
            self._set_status("Restore error.")

    # ── History ───────────────────────────────────────────
    def _add_history(self, action, database, filepath, status):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {"timestamp": ts, "action": action,
                 "database": database, "file": filepath, "status": status}
        self.config.setdefault("history", []).insert(0, entry)
        # keep last 200
        self.config["history"] = self.config["history"][:200]
        save_config(self.config)
        self.after(0, self._refresh_history)

    def _refresh_history(self):
        for row in self.hist_tree.get_children():
            self.hist_tree.delete(row)
        for entry in self.config.get("history", []):
            tag = "ok" if entry.get("status") == "OK" else "fail"
            self.hist_tree.insert("", "end", values=(
                entry.get("timestamp", ""),
                entry.get("action", ""),
                entry.get("database", ""),
                entry.get("file", ""),
                entry.get("status", ""),
            ), tags=(tag,))
        self.hist_tree.tag_configure("ok",   foreground="#a6e3a1")
        self.hist_tree.tag_configure("fail", foreground="#f38ba8")

    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Clear all backup/restore history?"):
            self.config["history"] = []
            save_config(self.config)
            self._refresh_history()


# ─────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = MySQLBackupApp()
    app.mainloop()
