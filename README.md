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
| 📦 Extract Here | `extract-here.py` | Fast extraction (7z + unrar) with multi-volume & password support |
| 🔍 Preview Panel | `preview-panel.py` | Dynamic file preview panel anchored to Nautilus |
| ⚙️ Extensions Manager | `extensions-manager.py` | Enable/disable extensions on the fly from Nautilus |
| 🗜️ Archive Browser | `archive-browser.py` | Browse and extract archive contents (zip, 7z, rar) |

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
  python3-cairo \
  p7zip-full \
  unrar \
  ffmpegthumbnailer \
  poppler-utils \
  libreoffice \
  wmctrl \
  xdotool
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

A full-featured dual-panel file manager window launched from Nautilus, with a Nautilus-style sidebar for quick navigation.

**Triggers:**
- `F3` — open from any Nautilus window
- Right-click on a folder → **Open in Dual Panel**
- Right-click on background → **Open in Dual Panel**

**Layout:**
- **Left sidebar** — Nautilus-style: Favorites (XDG special folders), Bookmarks (from `~/.config/gtk-3.0/bookmarks`), Mounted volumes (GIO)
- **Left panel** — source panel
- **Right panel** — destination panel

**Columns:** Name (expandable) · Size · Modified · Permissions (fixed width)

**File operations:**
- Copy → / ← Copy between panels
- Move → / ← Move between panels
- New folder, New file
- Rename (F2)
- Delete to trash (Delete), Permanent delete (Shift+Delete)
- Open in terminal

**Keyboard shortcuts:**
| Key | Action |
|---|---|
| `F3` | Open Dual Panel |
| `F5` | Refresh both panels |
| `F2` | Rename selected |
| `Delete` | Move to trash |
| `Shift+Delete` | Delete permanently |
| `Ctrl+C` | Copy to other panel |
| `Ctrl+X` | Move to other panel |
| `Ctrl+N` | New folder |
| `BackSpace` | Go to parent folder |
| `Alt+←/→` | Navigate left/right panel |
| `Escape` | Close window |

**Languages:** French 🇫🇷 · English 🇬🇧 · German 🇩🇪

**Dependencies:** `python3-nautilus` `python3-gi` `gir1.2-adw-1`

---

### 📦 Extract Here — `extract-here.py`

Fast archive extraction directly from Nautilus via right-click.

**Trigger:**
- Right-click on an archive → **Extract here…**
- Right-click on a multi-volume archive → **Extract volume here…**

**Supported formats:**
`.7z` `.zip` `.tar.*` `.gz` `.bz2` `.xz` `.zst` `.cab` `.iso` `.deb` `.rpm` `.dmg` `.wim`
`.rar` `.r00` `.r01`… (via `unrar` — full RAR5 support)

**Multi-volume support:**
`.7z.001` `.part1.rar` `.001` `.z01` `.r00` — automatically detects and extracts the full set

**Features:**
- Password detection via `7z l -slt -p""` — dialog only shown when archive is actually encrypted
- Real-time progress bar (percentage for 7z, file count for RAR)
- RAR archives extracted via `unrar` (supports RAR5 compression method `m5`)
- All other formats extracted via `7z`
- Extraction destination in same folder as archive

**Dependencies:** `python3-nautilus` `p7zip-full` `unrar`

---

### 🔍 Preview Panel — `preview-panel.py`

Opens a dynamic preview panel that updates automatically as you select files in Nautilus. The panel anchors itself to the right of the Nautilus window (X11 only).

**Triggers:**
- `F4` — open the panel (from any Nautilus window)
- `Escape` — close the panel
- Right-click → **Preview** on any file

**Supported previews:**
| Type | Method | Notes |
|---|---|---|
| Images (JPEG, PNG, WebP, SVG…) | GdkPixbuf direct | Full resolution, instant |
| Video | `ffmpegthumbnailer` | Generated once, cached |
| PDF | `pdftoppm` (Poppler) | Generated once, cached, same engine as Papers |
| Office docs (docx, odt, xlsx, pptx…) | LibreOffice headless | Generated once, cached |
| Text / Code | First 100 lines inline | |

**File metadata (via Tracker3 — near-instant):**
- Size, MIME type, date modified, permissions
- Dimensions (images & video)
- Duration (video), page count (PDF)
- Full EXIF data if available (camera, ISO, focal length, shutter speed…)
- Title and subject (PDF, Office)

**Performance:**
- Images loaded directly from source — full quality, no decoding overhead
- GNOME thumbnail cache (`~/.cache/thumbnails/`) for PDF, Office and video — first load generates and caches, subsequent loads are instantaneous
- 250ms debounce — rapid navigation doesn't trigger unnecessary loads
- LRU cache of 15 entries — revisiting a file is instantaneous
- Tracker3 SPARQL for metadata — ~2ms per query

**Window anchoring (X11 only):**
Requires `xdotool` and `wmctrl`. The panel positions itself to the right of the Nautilus window automatically on open.

**Known limitation:**
GTK4 `4.14.5+ds-0ubuntu0.9` (Ubuntu 24.04) contains a bug that causes crashes with file properties and some image viewers. If you experience issues after a system update, downgrade to `4.14.5+ds-0ubuntu0.7` and hold the package:
```bash
sudo apt-mark hold libgtk-4-1 libgtk-4-common gir1.2-gtk-4.0 libgtk-4-bin libgtk-4-media-gstreamer
```
Similarly, `libexiv2-27 0.27.6-1ubuntu0.1` contains a memory corruption bug — hold `libexiv2-27` if you experience segfaults.

**Dependencies:** `python3-nautilus` `python3-gi` `gir1.2-adw-1`
`ffmpegthumbnailer` `poppler-utils` `libreoffice` `wmctrl` `xdotool`

---

### ⚙️ Extensions Manager — `extensions-manager.py`

Manage your Nautilus Python extensions directly from Nautilus — enable, disable, and restart without touching the terminal.

**Trigger:**
- Right-click on background → **Manage extensions**

**Features:**
- Lists all **active** extensions with Python file icon
- Lists all **disabled** extensions (greyed out)
- One-click **enable/disable** — moves files between `extensions/` and `extensions/disabled/`
- **Restart Nautilus** button to apply changes (launches new instance before killing the current one)
- Automatically excludes system extensions (`nautilus-gsconnect.py`) and itself

**Why this matters:**
Each loaded extension consumes memory and CPU. Extensions with background timers (`preview-panel.py`, `dual-panel.py`) are especially resource-intensive. Best practice:

| Extension | Load impact | Recommendation |
|---|---|---|
| `annotate-image.py` | ✅ Minimal | Keep active |
| `extract-here.py` | ✅ Minimal | Keep active |
| `folder-color-revival.py` | ✅ Minimal | Keep active |
| `compress-pdf.py` | ✅ Minimal | Keep active |
| `merge-pdf.py` | ✅ Minimal | Keep active |
| `watermark-pdf.py` | ✅ Minimal | Keep active |
| `dual-panel.py` | ⚠️ Background timer | Enable on demand |
| `preview-panel.py` | ⚠️ Background timer | Enable on demand |
| `archive-browser.py` | ✅ Minimal | Keep active |

**Disabled extensions** are stored in `~/.local/share/nautilus-python/extensions/disabled/` and can be re-enabled at any time.

**Dependencies:** `python3-nautilus` `python3-gi` `gir1.2-adw-1`

---

### 🗜️ Archive Browser — `archive-browser.py`

Browse and selectively extract archive contents directly from Nautilus — a file-roller like experience.

**Triggers:**
- Right-click on an archive → **Browse archive**
- `F7` — reopen last browsed archive

**Supported formats:**
- **zip, 7z, tar, gz, bz2, xz, cab, iso, deb, rpm** — via `7z`
- **rar, r00, part1.rar…** — via `unrar` (full RAR5 support)

**Features:**
- 📂 Tree with collapse/expand — folders first 
- 🖱️ Native DnD to filesystem 
- 📋 Selective or total extraction 
- 🔍 Live Filter 
- 📁 Right Panel — Full Navigation, opens in the archive folder ZIP, 7z, RAR (RAR5 included)

**Dependencies:**`python3-nautilus` `python3-gi` `gir1.2-adw-1` `p7zip-full` `unrar`

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
