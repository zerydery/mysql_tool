<div align="center">
  <h1>🗄️ MySQL Backup & Restore Tool</h1>
  <p>A simple, standalone GUI application to easily backup and restore MySQL databases across local or remote servers.</p>
</div>

<br />

## 🌟 Overview
**MySQL Backup & Restore Tool** is a lightweight Python-based graphical utility. It provides an intuitive Tkinter interface on top of standard MySQL command-line tools (`mysqldump` and `mysql`). 

It dynamically detects local installations of databases like **XAMPP**, **Laragon**, or standard **MySQL Server** without requiring manual configuration, and supports migrating databases between separate devices effortlessly using `.sql` backups.

## ✨ Features
- **💾 Easy Backups**: Pick a database from the dropdown and export it with a single click.
- **🔄 Seamless Restores**: Import `.sql` backups safely and even auto-create the target database if it doesn't exist.
- **⚡ Auto-Detection**: Dynamically locates `mysql` and `mysqldump` executables across all system drives (C:, D:, E: etc.) from common local web stacks.
- **📋 Live History Log**: View a built-in session history of all backup and restore actions.
- **⚙️ Saved Configurations**: Preserves your connection credentials and destination paths for faster repeat runs.
- **📦 Portable Executable**: Built to be compiled as a single standalone `.exe` file—no Python installation required on the target machine!

## 🚀 Prerequisites
To run from source, you need:
- **Python 3.8+**
- **MySQL Server** (XAMPP, Laragon, or standalone)
  > *Note: The tool requires `mysqldump` and `mysql` to be present on the system. It handles locating these automatically as long as they exist in standard paths or your system's PATH variable.*

*(No 3rd-party pip libraries are required. It solely uses Python standard libraries).*

## 💻 Usage

### Running from source
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/mysql-backup-tool.git
   cd mysql-backup-tool
   ```
2. Run the main script:
   ```bash
   python mysql_backup_restore.py
   ```

### Building the Standalone Executable (.exe)
If you want to move the tool to environments without Python, you can compile it using `PyInstaller`.
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=NONE --name="MySQL_Backup_Restore_Tool" mysql_backup_restore.py
```
*The compiled application will be located in the `dist/` directory.*

## 📖 How to Migrate Databases to a New Device

1. Open the tool on the **Source Device**.
2. Connect to the database and use the **Backup** tab to export your data to a `.sql` file.
3. Move the standalone `MySQL_Backup_Restore_Tool.exe` along with the `.sql` backup file to the **Target Device** via a USB flash drive or cloud storage.
4. On the Target Device, launch the `.exe`, switch to the **Restore** tab, point it to the `.sql` file, and hit Start Restore!

## 📝 License
This project is open-source and available under the [MIT License](LICENSE).
