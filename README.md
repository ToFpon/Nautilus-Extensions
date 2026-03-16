# 🐚 Nautilus Python Extensions

> A collection of productivity-focused Python extensions for **Nautilus (GNOME Files)**, adding powerful tools directly into the right-click context menu.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![GTK](https://img.shields.io/badge/GTK-4.0-4A86CF?style=flat-square&logo=gtk&logoColor=white)
![Libadwaita](https://img.shields.io/badge/Libadwaita-1.x-78ACD8?style=flat-square)
![GNOME](https://img.shields.io/badge/Nautilus-46+-4A86CF?style=flat-square&logo=gnome&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-green?style=flat-square)

---

## 📦 Extensions

| Extension | File | Description |
|---|---|---|
| 🎨 Annotate Image | `annotate-image.py` | Full-featured PNG annotation editor |
| 🗜️ Compress PDF | `compress-pdf.py` | PDF compression via Ghostscript |
| ⏱️ Media Duration | `duration-column.py` | Duration column for audio/video files |
| 👁️ Hidden Files Dimmer | `hidden-dim-*.py` | Visual dimming of hidden files |
| 🔗 Merge PDF | `merge-pdf.py` | Merge multiple PDFs into one |
| ✏️ Quick Edit | `nautilus_edit_ext.py` | Open text files directly in an editor |
| 🔏 Watermark PDF | `watermark-pdf.py` | Secure watermarking with flattening |
| 📁 Folder Color Revival | `folder-color-revival.py` | Color & emblem tagging for folders |
| 🗂️ Dual Panel | `dual-panel.py` | Double-pane file manager inside Nautilus |

---

## ⚙️ Installation

### Prerequisites

```bash
sudo apt install \
  python3-nautilus \
  python3-gi \
  gir1.2-gtk-4.0 \
  gir1.2-adw-1 \
  ghostscript \
  ffmpeg \
  python3-pypdf \
  python3-cairo
```

### Installing an extension

```bash
# Create the directory if needed
mkdir -p ~/.local/share/nautilus-python/extensions/

# Copy the extension
cp extension-name.py ~/.local/share/nautilus-python/extensions/

# Restart Nautilus
nautilus -q
```

> ⚠️ Always clear the cache after installing or updating an extension:
> ```bash
> rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
> ```

---

## 🔍 Extensions in detail

### 🎨 Annotate Image — `annotate-image.py`

Opens a full annotation editor directly from a right-click on any PNG file.

**Available tools:**
- Rectangle, ellipse, arrow (with arrowhead)
- Free-form text, click-to-place
- Color picker, stroke thickness (1→20) and opacity (10%→100%)
- Unlimited undo / redo
- Professional crosshair cursor
- Native full-resolution export

**Dependencies:** `python3-nautilus` `python3-gi` `gir1.2-adw-1` `python3-cairo`

---

### 🗜️ Compress PDF — `compress-pdf.py`

Reduces PDF file size using Ghostscript's built-in optimization presets.

**Available levels:**
| Level | Use case |
|---|---|
| Default | Balanced optimization |
| Screen | Low resolution, screen reading |
| Low Quality | Maximum compression |
| High Quality | Laser printer output |
| High Quality (Color) | Prepress / color-accurate printing |

**Dependencies:** `python3-nautilus` `ghostscript` `python3-gi` `gir1.2-gtk-4.0`

---

### ⏱️ Media Duration Column — `duration-column.py`

Adds a **Duration** column in Nautilus list view for audio and video files. Uses a local cache for fast, lightweight performance.

**Dependencies:** `python3-nautilus` `ffmpeg` `python3-gi`

---

### 👁️ Hidden Files Dimmer — `hidden-dim-all.py` / `hidden-dim-icon.py`

Visually distinguishes hidden files (dot-prefixed) by reducing their opacity, making the filesystem easier to navigate at a glance.

- `hidden-dim-all.py` — dims both icons **and** labels
- `hidden-dim-icon.py` — dims icons and thumbnails only

**Dependencies:** `python3-nautilus` `python3-gi` `gir1.2-gtk-4.0`

---

### 🔗 Merge PDF — `merge-pdf.py`

Merges multiple PDF files into a single document. The option appears only when **2 or more PDF files** are selected.

**Features:**
- Reorder dialog with ↑ ↓ buttons
- Auto-suggested output filename (`merged.pdf`)
- Progress bar with cancel support

**Dependencies:** `python3-nautilus` `ghostscript` `python3-gi` `gir1.2-adw-1`

---

### ✏️ Quick Edit — `nautilus_edit_ext.py`

Adds a context menu entry to open text-based files (`.py`, `.sh`, `.txt`, `.md`, etc.) directly in a text editor.

**Dependencies:** `python3-nautilus` `python3-gi` `gedit` *(or your preferred editor)*

---

### 🔏 Watermark PDF — `watermark-pdf.py`

Adds a customizable text watermark to PDF files, designed to **protect sensitive documents** against identity theft and fraud.

**Options:**
- Custom text, font size, angle (-90°→+90°)
- Adjustable opacity and color
- **Centered** or **diagonal repeat** layout
- ✅ **Flatten** — rasterizes the entire page into an unforgeable image, with configurable resolution (72→300 DPI)

> 💡 **Security tip:** Use flatten at 200 DPI, then run the result through *Compress PDF* for a document that is both tamper-proof and lightweight.

**Dependencies:** `python3-nautilus` `ghostscript` `python3-pypdf` `python3-gi` `gir1.2-adw-1`

---

### 📁 Folder Color Revival — `folder-color-revival.py`

A debugged and modernized revival of the popular [Folder Color](https://github.com/costales/folder-color) extension, rewritten for **Nautilus 43+ / GTK4 / python3-nautilus 4.0**.

The original extension was plagued with startup crashes and freezes due to several incompatibilities with modern Nautilus. This version fixes all known issues.

**Features:**
- Color tagging for folders (14 colors: black, blue, brown, cyan, green, grey, magenta, orange, pink, purple, red, violet, white, yellow)
- Emblem tagging (Important, In Progress, Favorite, Finished, New)
- Automatic detection of available colors in the current icon theme
- Support for special user directories (Desktop, Documents, Downloads, etc.)
- One-click restore to default icon
- Built-in debug logging (see below)

**Bugs fixed vs original:**
| # | Issue | Fix |
|---|---|---|
| 1 | Crash on load — `@GETTEXT_PACKAGE@` placeholder never replaced | Replaced with standard `gettext` fallback |
| 2 | Freeze on startup — `USER_DIRS` built at module level before GLib ready | Moved to lazy `_get_user_dirs()` function |
| 3 | Crash if GSettings schema missing | Wrapped in `try/except` |
| 4 | Nautilus freeze — icon lookups blocking main thread in `__init__` | Deferred via `GLib.idle_add()` |
| 5 | GLib type conflicts with other extensions | Added explicit `__gtype_name__` |

**Debug mode:**
```bash
DEBUG=1 nautilus --no-desktop 2>&1 | grep "folder-color"
```

**Dependencies:** `python3-nautilus` `python3-gi` `gir1.2-gtk-4.0`


---

### 🗂️ Dual Panel — `dual-panel.py`

Opens a fully-featured **double-pane file manager** directly from Nautilus, similar to Nemo or Thunar's split view — a feature Nautilus once had and many users still miss.

Available from right-clicking any folder **or** from the background context menu.

**Features:**
- Side-by-side dual panel with independent navigation
- Editable address bar in each panel
- Resizable divider between panels
- Sortable columns: Name, Size, Date modified, Permissions
- Sort order matches Nautilus: normal folders → hidden folders → normal files → hidden files
- Folder and file icons by MIME type

**File operations:**
| Action | Button | Keyboard |
|---|---|---|
| Copy to other panel | Copy → / ← Copy | `Ctrl+C` |
| Move to other panel | Move → / ← Move | `Ctrl+X` |
| New folder | 📁 | `Ctrl+N` |
| New file | 📄 | — |
| Rename | ✏️ | `F2` |
| Move to trash | 🗑️ | `Delete` |
| Delete permanently | 🗑️ *(red)* | `Shift+Delete` |
| Parent folder | ↑ | `Backspace` |
| Refresh both panels | — | `F5` |
| Open Dual Panel from Nautilus | — | `F3` |
| Open terminal here | >_ | — |

**Right-click context menu** — Open, Copy/Move to other panel, Rename, Move to trash, Delete permanently, New folder, New file, Terminal here

**Drag & drop** — drag files between panels to copy them instantly

**Dependencies:** `python3-nautilus` `python3-gi` `gir1.2-adw-1`


---

## 🌍 Internationalization

All extensions automatically detect the system language and are fully available in both **English** and **French**.

---

## 🖥️ Compatibility

| Component | Required version |
|---|---|
| Nautilus | 43+ (API 4.0) |
| Python | 3.10+ |
| GTK | 4.0 |
| Libadwaita | 1.x |
| Ubuntu / Debian | 23.04+ |

---

## 📄 License

This project is released under the **GNU GPL v3** license.  
Based on the original *Compress PDF* bash script by Ricardo Ferreira.
