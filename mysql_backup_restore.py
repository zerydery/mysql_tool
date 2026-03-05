"""
MySQL Backup & Restore Tool
===========================
Requirements:
    pip install mysql-connector-python
    mysqldump and mysql executables must be in PATH (comes with MySQL Server installation)

Usage:
    python mysql_backup_restore.py
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import subprocess
import threading
import os
import json
import datetime
import shutil
import sys

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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
class MySQLBackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MySQL Backup & Restore Tool")
        self.geometry("900x700")
        self.minsize(800, 600)
        self.config = load_config()

        self._build_ui()
        self._load_config_to_ui()

    # ── UI Builder ────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color="#1f538d", height=60)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="🗄️  MySQL Backup & Restore Tool",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)

        # Tabview
        self.tabview = ctk.CTkTabview(self, width=860)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=15)

        self.tab_backup = self.tabview.add("  💾 Backup  ")
        self.tab_restore = self.tabview.add("  🔄 Restore  ")
        self.tab_history = self.tabview.add("  📋 History  ")
        self.tab_settings = self.tabview.add("  ⚙️  Settings  ")

        self._build_backup_tab()
        self._build_restore_tab()
        self._build_history_tab()
        self._build_settings_tab()

        # Status bar
        self.status_var = ctk.StringVar(value="Ready.")
        sb = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w",
                          font=ctk.CTkFont(size=12), fg_color="#2b2b2b", text_color="#a9a9a9", corner_radius=0)
        sb.pack(fill="x", side="bottom", ipady=5, padx=10)

    # ── Backup Tab ────────────────────────────────────────
    def _build_backup_tab(self):
        p = ctk.CTkScrollableFrame(self.tab_backup, fg_color="transparent")
        p.pack(fill="both", expand=True)

        # Connection group
        cg = ctk.CTkFrame(p)
        cg.pack(fill="x", pady=(0, 15), padx=5)
        # title
        ctk.CTkLabel(cg, text="🔌 MySQL Connection", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        inner_cg = ctk.CTkFrame(cg, fg_color="transparent")
        inner_cg.pack(fill="x", padx=15, pady=5)
        self._conn_fields_backup = self._make_conn_fields(inner_cg)
        
        btn_con = ctk.CTkButton(cg, text="🔗 Connect & List Databases", command=self._backup_connect, font=ctk.CTkFont(weight="bold"))
        btn_con.pack(anchor="w", padx=15, pady=(10, 15))

        # Database selection
        dg = ctk.CTkFrame(p)
        dg.pack(fill="x", pady=(0, 15), padx=5)
        ctk.CTkLabel(dg, text="🗃️ Select Database", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        inner_dg = ctk.CTkFrame(dg, fg_color="transparent")
        inner_dg.pack(fill="x", padx=15, pady=5)

        self.backup_db_var = ctk.StringVar()
        self.backup_db_combo = ctk.CTkComboBox(inner_dg, variable=self.backup_db_var, state="readonly", width=300)
        self.backup_db_combo.pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(inner_dg, text="⟳ Refresh", command=self._backup_connect, width=100, fg_color="transparent", border_width=1).pack(side="left")

        self.all_db_var = ctk.BooleanVar()
        ctk.CTkCheckBox(inner_dg, text="Backup ALL databases", variable=self.all_db_var, command=self._toggle_all_db).pack(side="right")

        # Destination
        destg = ctk.CTkFrame(p)
        destg.pack(fill="x", pady=(0, 15), padx=5)
        ctk.CTkLabel(destg, text="📁 Backup Destination", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        inner_dest = ctk.CTkFrame(destg, fg_color="transparent")
        inner_dest.pack(fill="x", padx=15, pady=(5, 15))
        self.backup_path_var = ctk.StringVar(value=self.config["last_backup_dir"])
        ctk.CTkEntry(inner_dest, textvariable=self.backup_path_var).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(inner_dest, text="Browse…", width=100, command=self._browse_backup_dir).pack(side="right")

        # Options
        og = ctk.CTkFrame(p)
        og.pack(fill="x", pady=(0, 15), padx=5)
        ctk.CTkLabel(og, text="🛠️ Options", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        inner_og = ctk.CTkFrame(og, fg_color="transparent")
        inner_og.pack(fill="x", padx=15, pady=(5, 15))

        self.compress_var     = ctk.BooleanVar(value=False)
        self.include_rout_var = ctk.BooleanVar(value=False)
        self.no_data_var      = ctk.BooleanVar(value=False)
        
        ctk.CTkCheckBox(inner_og, text="Compress (.zip) – saves space", variable=self.compress_var).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(inner_og, text="Include Routines & Triggers", variable=self.include_rout_var).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(inner_og, text="Schema only (no data)", variable=self.no_data_var).pack(side="left")

        # Action
        ctk.CTkButton(p, text="💾 Start Backup", command=self._do_backup, font=ctk.CTkFont(size=15, weight="bold"), fg_color="#2b9348", hover_color="#007f5f", height=40).pack(pady=10, anchor="w", padx=5)

        # Log
        lg = ctk.CTkFrame(p)
        lg.pack(fill="both", expand=True, padx=5, pady=(10, 0))
        ctk.CTkLabel(lg, text="📝 Log", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 0))
        self.backup_log = self._make_log(lg)

    # ── Restore Tab ───────────────────────────────────────
    def _build_restore_tab(self):
        p = ctk.CTkScrollableFrame(self.tab_restore, fg_color="transparent")
        p.pack(fill="both", expand=True)

        cg = ctk.CTkFrame(p)
        cg.pack(fill="x", pady=(0, 15), padx=5)
        ctk.CTkLabel(cg, text="🔌 MySQL Connection", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))
        inner_cg = ctk.CTkFrame(cg, fg_color="transparent")
        inner_cg.pack(fill="x", padx=15, pady=5)
        self._conn_fields_restore = self._make_conn_fields(inner_cg)
        ctk.CTkButton(cg, text="🔗 Connect & List Databases", command=self._restore_connect, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(10, 15))

        # Source file
        sg = ctk.CTkFrame(p)
        sg.pack(fill="x", pady=(0, 15), padx=5)
        ctk.CTkLabel(sg, text="📂 Backup File (.sql / .zip)", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))
        inner_sg = ctk.CTkFrame(sg, fg_color="transparent")
        inner_sg.pack(fill="x", padx=15, pady=(5, 15))
        self.restore_file_var = ctk.StringVar()
        ctk.CTkEntry(inner_sg, textvariable=self.restore_file_var).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(inner_sg, text="Browse…", width=100, command=self._browse_restore_file).pack(side="right")

        # Target database
        tg = ctk.CTkFrame(p)
        tg.pack(fill="x", pady=(0, 15), padx=5)
        ctk.CTkLabel(tg, text="🗃️ Target Database", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))
        inner_tg = ctk.CTkFrame(tg, fg_color="transparent")
        inner_tg.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkLabel(inner_tg, text="Restore into:").pack(side="left", padx=(0, 10))
        self.restore_db_var = ctk.StringVar()
        self.restore_db_combo = ctk.CTkComboBox(inner_tg, variable=self.restore_db_var, width=250) # Standard state for typing
        self.restore_db_combo.pack(side="left", padx=(0, 20))

        self.create_db_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(inner_tg, text="Create database if not exists", variable=self.create_db_var).pack(side="left")

        # Action
        ctk.CTkButton(p, text="🔄 Start Restore", command=self._do_restore, font=ctk.CTkFont(size=15, weight="bold"), fg_color="#c1121f", hover_color="#780000", height=40).pack(pady=10, anchor="w", padx=5)

        lg = ctk.CTkFrame(p)
        lg.pack(fill="both", expand=True, padx=5, pady=(10, 0))
        ctk.CTkLabel(lg, text="📝 Log", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 0))
        self.restore_log = self._make_log(lg)

    # ── History Tab ───────────────────────────────────────
    def _build_history_tab(self):
        p = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        p.pack(fill="both", expand=True)

        # Fallback to standard tkinter Treeview for tables as CustomTkinter lacks tables
        import tkinter.ttk as ttk
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0, rowheight=30)
        style.configure("Treeview.Heading", background="#333333", foreground="white", font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", "#1f538d")])

        cols = ("timestamp", "action", "database", "file", "status")
        tree_frame = ctk.CTkFrame(p)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.hist_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
        widths = [140, 80, 150, 300, 80]
        labels = ["Timestamp", "Action", "Database", "File", "Status"]
        for col, w, lbl in zip(cols, widths, labels):
            self.hist_tree.heading(col, text=lbl)
            self.hist_tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=vsb.set)
        self.hist_tree.pack(side="left", fill="both", expand=True, padx=(1,0), pady=1)
        vsb.pack(side="right", fill="y", padx=(0,1), pady=1)

        btn_frame = ctk.CTkFrame(p, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=10)
        ctk.CTkButton(btn_frame, text="⟳ Refresh", command=self._refresh_history, width=120).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="🗑️ Clear History", command=self._clear_history, width=120, fg_color="#c1121f", hover_color="#780000").pack(side="left")

        self.after(200, self._refresh_history)

    # ── Settings Tab ─────────────────────────────────────
    def _build_settings_tab(self):
        p = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        p.pack(fill="both", expand=True)

        cg = ctk.CTkFrame(p)
        cg.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(cg, text="Default MySQL Connection Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(20, 10))

        inner_cg = ctk.CTkFrame(cg, fg_color="transparent")
        inner_cg.pack(fill="both", padx=20, pady=(0, 20))

        fields = [("Host:", "s_host"), ("Port:", "s_port"),
                  ("User:", "s_user"), ("Password:", "s_pass")]
        self._settings_vars = {}
        for i, (lbl, key) in enumerate(fields):
            row_f = ctk.CTkFrame(inner_cg, fg_color="transparent")
            row_f.pack(fill="x", pady=5)
            ctk.CTkLabel(row_f, text=lbl, width=100, anchor="w").pack(side="left")
            var = ctk.StringVar()
            self._settings_vars[key] = var
            show = "*" if key == "s_pass" else ""
            ctk.CTkEntry(row_f, textvariable=var, width=250, show=show).pack(side="left")

        row_f = ctk.CTkFrame(inner_cg, fg_color="transparent")
        row_f.pack(fill="x", pady=15)
        ctk.CTkLabel(row_f, text="Default Backup Directory:", width=180, anchor="w").pack(side="left")
        self.s_backup_dir = ctk.StringVar()
        ctk.CTkEntry(row_f, textvariable=self.s_backup_dir, width=350).pack(side="left", padx=(0, 10))
        ctk.CTkButton(row_f, text="Browse…", width=100, command=self._browse_settings_dir).pack(side="left")

        ctk.CTkButton(cg, text="💾 Save Settings", command=self._save_settings, font=ctk.CTkFont(weight="bold"), fg_color="#2b9348", hover_color="#007f5f").pack(anchor="w", padx=20, pady=(0, 20))

        # Paths
        pg = ctk.CTkFrame(p)
        pg.pack(fill="x", padx=5, pady=15)
        ctk.CTkLabel(pg, text="System Paths", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(15, 10))
        
        inner_pg = ctk.CTkFrame(pg, fg_color="transparent")
        inner_pg.pack(fill="x", padx=20, pady=(0, 20))
        
        row1 = ctk.CTkFrame(inner_pg, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkLabel(row1, text="mysqldump detected at:", width=180, anchor="w").pack(side="left")
        dump_exe = find_mysql_exe("mysqldump")
        ctk.CTkLabel(row1, text=dump_exe, text_color="#219ebc").pack(side="left")

        row2 = ctk.CTkFrame(inner_pg, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        ctk.CTkLabel(row2, text="mysql detected at:", width=180, anchor="w").pack(side="left")
        mysql_exe = find_mysql_exe("mysql")
        ctk.CTkLabel(row2, text=mysql_exe, text_color="#219ebc").pack(side="left")

    # ── Shared widgets ────────────────────────────────────
    def _make_conn_fields(self, parent):
        """Renders host/port/user/pass fields horizontally and returns their StringVars."""
        labels  = ["Host:", "Port:", "User:", "Password:"]
        keys    = ["host",  "port",  "user",  "password"]
        widths  = [140, 60, 120, 140]
        vars_   = {}
        for col, (lbl, key, w) in enumerate(zip(labels, keys, widths)):
            ctk.CTkLabel(parent, text=lbl).grid(row=0, column=col*2, sticky="w", padx=(10 if col else 0, 5))
            var = ctk.StringVar(value=self.config.get(key, ""))
            vars_[key] = var
            show = "*" if key == "password" else ""
            ctk.CTkEntry(parent, textvariable=var, width=w, show=show).grid(row=0, column=col*2+1, sticky="w")
        return vars_

    def _make_log(self, parent):
        txt = ctk.CTkTextbox(parent, height=150, fg_color="#181818", text_color="#cdd6f4", font=ctk.CTkFont(family="Consolas", size=12))
        txt.pack(fill="both", expand=True, padx=15, pady=15)
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
