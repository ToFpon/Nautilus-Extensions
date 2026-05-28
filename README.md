# 🐚 Nautilus Python Extensions

> A collection of productivity-focused Python extensions for **Nautilus (GNOME Files)**, adding powerful tools directly into the right-click context menu.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![GTK](https://img.shields.io/badge/GTK-4.0-4A86CF?style=flat-square&logo=gtk&logoColor=white)
![Libadwaita](https://img.shields.io/badge/Libadwaita-1.x-78ACD8?style=flat-square)
![GNOME](https://img.shields.io/badge/Nautilus-46+-4A86CF?style=flat-square&logo=gnome&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-green?style=flat-square)
![PPA](https://img.shields.io/badge/PPA-launchpad-E95420?style=flat-square&logo=ubuntu&logoColor=white)

---

## 🚀 Quick install via PPA (Ubuntu / Zorin OS / Mint)

The easiest way — packages are signed, auto-updated through `apt`, and properly handle dependencies.

```bash
sudo add-apt-repository ppa:nourpon/nautilus-extensions
sudo apt update

# Install everything at once
sudo apt install \
  nautilus-dual-panel \
  nautilus-extensions-manager \
  nautilus-archive-browser \
  nautilus-extract-here \
  nautilus-annotate-image \
  nautilus-compress-pdf \
  nautilus-merge-pdf \
  nautilus-watermark-pdf \
  nautilus-preview-panel \
  nautilus-deb-installer \
  nautilus-search-content \
  nautilus-video-to-audio \
  nautilus-duration-column \
  nautilus-cut-dim \
  nautilus-edit-gedit \
  nautilus-folder-color-revival \
  nautilus-hidden-dim-icon
  # (or nautilus-hidden-dim-all instead of -icon)

# You need to logout and login to activate extesions or run in terminal
nautilus-extensions-tof-link
# Restart Nautilus
nautilus -q
```

> 💡 You can also install individual packages — `apt` will pull only what each one needs.

---

## 📦 Extensions

| Extension | Package | Description |
|---|---|---|
| 🗂️ **Dual Panel** | `nautilus-dual-panel` | Double-pane file manager inside Nautilus |
| ⚙️ **Extensions Manager** | `nautilus-extensions-manager` | Enable/disable extensions on the fly |
| 🗜️ **Archive Browser** | `nautilus-archive-browser` | Browse, extract and **create** archives |
| 📦 **Extract Here** | `nautilus-extract-here` | Fast extraction (7z, rar, zip…) with multi-volume & password |
| 🎨 **Annotate Image** | `nautilus-annotate-image` | Full-featured PNG annotation editor |
| 🗜️ **Compress PDF** | `nautilus-compress-pdf` | PDF compression via Ghostscript |
| 🔗 **Merge PDF** | `nautilus-merge-pdf` | Merge multiple PDFs into one |
| 🔏 **Watermark PDF** | `nautilus-watermark-pdf` | Secure watermarking with flattening |
| 🔍 **Preview Panel** | `nautilus-preview-panel` | Dynamic file preview panel |
| 📦 **Deb Installer** | `nautilus-deb-installer` | Visual `.deb` installer with real-time output |
| 🔎 **Search Content** | `nautilus-search-content` | Real text search using grep/ripgrep |
| 🎵 **Video to Audio** | `nautilus-video-to-audio` | Extract audio from videos (MP3, M4A, OGG, OPUS, FLAC, WAV) |
| ⏱️ **Duration Column** | `nautilus-duration-column` | Duration column for audio/video files |
| ✂️ **Cut Item Dimmer** | `nautilus-cut-dim` | Visual dimming of cut (Ctrl+X) files |
| ✏️ **Edit with Gedit** | `nautilus-edit-gedit` | Open text files directly in Gedit |
| 📁 **Folder Color Revival** | `nautilus-folder-color-revival` | Color & emblem tagging for folders |
| 👁️ **Hidden Dim (icon)** | `nautilus-hidden-dim-icon` | Dim only the icon of hidden files |
| 👁️ **Hidden Dim (all)** | `nautilus-hidden-dim-all` | Dim icon + label of hidden files |
| 🔧 **Common** | `nautilus-extensions-tof-common` | Shared linker script (installed automatically) |

> 🌍 All extensions support **French 🇫🇷 · English 🇬🇧 · German 🇩🇪**.

---

## ⚙️ Manual installation (advanced)

If you prefer not to use the PPA, you can install extensions manually:

### Prerequisites

```bash
sudo apt install \
  python3-nautilus \
  python3-gi \
  gir1.2-gtk-4.0 \
  gir1.2-adw-1 \
  gir1.2-nautilus-4.0 \
  ghostscript \
  ffmpeg \
  python3-pypdf \
  python3-cairo \
  p7zip-full \
  unrar \
  poppler-utils
```

### Install

```bash
git clone https://github.com/ToFpon/Nautilus-Extensions.git
cd Nautilus-Extensions

mkdir -p ~/.local/share/nautilus-python/extensions/
cp *.py ~/.local/share/nautilus-python/extensions/
rm -rf ~/.local/share/nautilus-python/extensions/__pycache__

nautilus -q
```

---

## 🏗️ Architecture (PPA version)

All packages install scripts into a dedicated namespace:

```
/usr/share/nautilus-extensions-tof/          ← system install (PPA)
├── dual-panel.py
├── archive-browser.py
├── extract-here.py
└── ...

~/.local/share/nautilus-python/extensions/   ← per-user (auto symlinks)
├── dual-panel.py → /usr/share/nautilus-extensions-tof/dual-panel.py
└── ...
```

The shared **`nautilus-extensions-tof-common`** package handles symlink creation for every user at session start via `xdg-autostart`. This way the **Extensions Manager** can detect and toggle extensions per-user, while keeping system installation clean and shared.

If an extension is disabled (moved to `~/.local/share/nautilus-python/extensions/disabled/` by the manager), the link will **not** be recreated at next login — your preference is respected.

---

## 🌟 Featured: Dual Panel

A complete dual-pane file manager living inside Nautilus, launched with **F3** or via the right-click context menu.

**Views (independent per panel):**
- 📋 List view — Name · Size · Modified columns with sortable header
- ⊞ Grid view — Large icons (48px) with filename, toggle button in toolbar

**Smart integrations (auto-detected):**
- 📦 **Extract Here** button + context menu — appears only if `nautilus-extract-here` is installed AND all selected files are archives
- 🎵 **Video to Audio** button + context menu — appears only if `nautilus-video-to-audio` is installed AND all selected files are videos
- 👻 **Hidden file dimming** — auto-applied if `nautilus-hidden-dim-icon` or `nautilus-hidden-dim-all` is installed
- Buttons appear in the bottom bar (after Move →) to avoid layout shifts in the toolbar

**File operations:**
- Copy/Move between panels with **rsync progress bar**
- Drag & Drop support (intra and inter-panel)
- Native context menu (open, cut, copy, paste, rename, trash, delete, properties)
- F3 toggle to open/close the dual-panel window
- F7 to launch Archive Browser on selection

**Navigation:**
- Nautilus-style sidebar (favorites, bookmarks, mounted volumes)
- Native view mode sync with Nautilus preferences
- Cross-extension awareness (live re-detection of installed extensions)

---

## 🔍 Featured: Search Content

A reliable text content search — much more dependable than Nautilus' built-in search which relies on Tracker3 indexing.

- Uses **grep** (always available) or **ripgrep** for speed (if installed)
- Filterable by file extensions (`py,txt,md`, etc.)
- Recursive or current folder only
- Case sensitive / regex options
- Skips binary files and heavy folders (`.git`, `node_modules`, `__pycache__`)
- Threaded search — UI stays responsive
- Double-click to open file, right-click for context menu

```bash
# Optional: faster search with ripgrep
sudo apt install ripgrep
```

---

## 🎵 Featured: Video to Audio

Batch audio extraction from video files with ffmpeg.

- **6 output formats**: MP3, M4A, OGG, OPUS, FLAC, WAV
- **4 quality levels**: 320 / 192 / 128 kbps, or stream copy (no re-encoding)
- **Real-time progress bar** with percentage (parsed from ffmpeg output)
- **Per-file status indicator** ✓ / ✗
- **Destination folder selector**
- Cancel button kills the ffmpeg process group cleanly

---

## 📦 Featured: Deb Installer

Visual installer for `.deb` packages — perfect for users migrating from Windows.

- Right-click any `.deb` file → **Install package**
- Displays name, version, description
- **Automatic dependency check** — lists missing packages before install
- Real-time scrollable terminal output, color-coded
- Authentication via `pkexec` (graphical password prompt)

---

## 🗜️ Featured: Archive Browser

A complete archive manager replacing **file-roller** entirely.

- Supports ZIP, 7z, RAR, TAR, GZ, BZ2, XZ, CAB, ISO, and many more
- **Multi-volume 7z** (`.001`, `.002`...) and **multi-volume RAR**
- Password-protected archives with prompt
- Collapsible tree view, smart cache, selective extraction
- Native GTK4 drag & drop
- Create new archives from selected files

---

## 🛠️ Hidden gems

- **`nautilus-cut-dim`** — visually dims items cut with `Ctrl+X` so you don't forget what's in the clipboard
- **`nautilus-duration-column`** — adds a sortable Duration column (HH:MM:SS) for audio/video files via `ffprobe`
- **`nautilus-folder-color-revival`** — revive the classic folder colorizer; works on modern Nautilus 46+
- **`nautilus-edit-gedit`** — one-click open text files in Gedit (filtered by extension to avoid clutter)

---

## 🐛 Reporting issues

Issues and PRs welcome on [GitHub](https://github.com/ToFpon/Nautilus-Extensions/issues).

Tested on **Zorin OS 18** (Ubuntu 24.04 Noble base, GNOME 46, X11 session). Should work on any GNOME 46+ desktop.

---

## 📜 License

All extensions are distributed under the **GNU General Public License v3.0** (GPL-3.0).

See [LICENSE](LICENSE) or [https://www.gnu.org/licenses/](https://www.gnu.org/licenses/).

---

## 👤 Author

**Tof** ([@ToFpon](https://github.com/ToFpon)) — sysadmin with ~40 years of IT experience.

> 💝 *In memory of Lola — some scripts in this collection bear her name in tribute to a dear sysadmin friend.*

> A big thank to ([@Ponce-De-Leon](https://forum.zorin.com/u/Ponce-De-Leon)) for testing
---

<p align="center">
  <sub>Made with ❤️ on Zorin OS · X11 forever · No telemetry, no spyware, no nonsense</sub>
</p>
