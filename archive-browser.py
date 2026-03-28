#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Dual Panel — Nautilus Python Extension
# DESC: Full-featured dual-panel file manager launched from Nautilus
# AUTHOR: Tof
# VERSION: 1.0
# LICENSE: GNU General Public License v3.0
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# NAME: Archive Browser – Nautilus Python Extension
# REQUIRES: python3-nautilus, python3-gi, p7zip-full, unrar
# INSTALL:
#   cp archive-browser.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import re
import shutil
import subprocess
import tempfile
import threading
import locale
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gdk, Gio, GLib, Nautilus, Pango

try:
    import libarchive
    HAS_LIBARCHIVE = True
except ImportError:
    HAS_LIBARCHIVE = False

SZ_BIN    = shutil.which("7z")    or "/usr/bin/7z"
UNRAR_BIN = shutil.which("unrar") or "/usr/bin/unrar"
RAR_BIN   = shutil.which("rar")   or "/usr/bin/rar"

ARCHIVE_EXTS = {".zip", ".7z", ".tar", ".gz", ".bz2", ".xz",
                ".rar", ".tgz", ".tbz2", ".cab", ".iso"}

_lang = locale.getlocale()[0] or ""
if _lang.startswith("fr"):
    T = {
        # Navigation
        "menu_label":          "Parcourir l'archive",
        "title":               "Navigateur d'archives",
        "filter":              "Filtrer…",
        "go_up":               "Dossier parent",
        "refresh":             "Actualiser",
        "home":                "Accueil",
        # Extraction
        "extract_all":         "Tout extraire",
        "extract_sel":         "Extraire la sélection",
        # Mot de passe
        "pwd_title":           "Archive protégée",
        "pwd_body":            "Cette archive est chiffrée. Entrez le mot de passe :",
        "pwd_placeholder":     "Mot de passe",
        "pwd_cancel":          "Annuler",
        "pwd_ok":              "Ouvrir",
        "pwd_wrong":           "Mot de passe incorrect",
        # Créateur
        "create_label":        "Créer une archive",
        "create_title":        "Créer une archive",
        "create_name":         "Nom de l'archive",
        "create_format":       "Format",
        "create_level":        "Compression",
        "create_pwd":          "Mot de passe (optionnel)",
        "create_split":        "Diviser en volumes (Mo, 0=non)",
        "create_btn":          "Créer",
        "creating":            "Création en cours…",
        "create_done":         "Archive créée",
        "create_err":          "Erreur de création",
        # Dossiers XDG
        "user_dir_DESKTOP":    "Bureau",
        "user_dir_DOWNLOAD":   "Téléchargements",
        "user_dir_TEMPLATES":  "Modèles",
        "user_dir_PUBLICSHARE":"Public",
        "user_dir_DOCUMENTS":  "Documents",
        "user_dir_MUSIC":      "Musique",
        "user_dir_PICTURES":   "Images",
        "user_dir_VIDEOS":     "Vidéos",
    }
elif _lang.startswith("de"):
    T = {
        # Navigation
        "menu_label":          "Archiv durchsuchen",
        "title":               "Archiv-Browser",
        "filter":              "Filtern…",
        "go_up":               "Übergeordneter Ordner",
        "refresh":             "Aktualisieren",
        "home":                "Persönlicher Ordner",
        # Extraction
        "extract_all":         "Alles entpacken",
        "extract_sel":         "Auswahl entpacken",
        # Mot de passe
        "pwd_title":           "Geschütztes Archiv",
        "pwd_body":            "Dieses Archiv ist verschlüsselt. Passwort eingeben:",
        "pwd_placeholder":     "Passwort",
        "pwd_cancel":          "Abbrechen",
        "pwd_ok":              "Öffnen",
        "pwd_wrong":           "Falsches Passwort",
        # Créateur
        "create_label":        "Archiv erstellen",
        "create_title":        "Archiv erstellen",
        "create_name":         "Archivname",
        "create_format":       "Format",
        "create_level":        "Komprimierung",
        "create_pwd":          "Passwort (optional)",
        "create_split":        "In Volumes aufteilen (MB, 0=nein)",
        "create_btn":          "Erstellen",
        "creating":            "Wird erstellt…",
        "create_done":         "Archiv erstellt",
        "create_err":          "Fehler beim Erstellen",
        # Dossiers XDG
        "user_dir_DESKTOP":    "Schreibtisch",
        "user_dir_DOWNLOAD":   "Downloads",
        "user_dir_TEMPLATES":  "Vorlagen",
        "user_dir_PUBLICSHARE":"Öffentlich",
        "user_dir_DOCUMENTS":  "Dokumente",
        "user_dir_MUSIC":      "Musik",
        "user_dir_PICTURES":   "Bilder",
        "user_dir_VIDEOS":     "Videos",
    }
else:
    T = {
        # Navigation
        "menu_label":          "Browse archive",
        "title":               "Archive Browser",
        "filter":              "Filter…",
        "go_up":               "Parent folder",
        "refresh":             "Refresh",
        "home":                "Home",
        # Extraction
        "extract_all":         "Extract all",
        "extract_sel":         "Extract selection",
        # Password
        "pwd_title":           "Protected archive",
        "pwd_body":            "This archive is encrypted. Enter the password:",
        "pwd_placeholder":     "Password",
        "pwd_cancel":          "Cancel",
        "pwd_ok":              "Open",
        "pwd_wrong":           "Wrong password",
        # Creator
        "create_label":        "Create archive",
        "create_title":        "Create archive",
        "create_name":         "Archive name",
        "create_format":       "Format",
        "create_level":        "Compression",
        "create_pwd":          "Password (optional)",
        "create_split":        "Split into volumes (MB, 0=no)",
        "create_btn":          "Create",
        "creating":            "Creating…",
        "create_done":         "Archive created",
        "create_err":          "Creation error",
        # XDG folders
        "user_dir_DESKTOP":    "Desktop",
        "user_dir_DOWNLOAD":   "Downloads",
        "user_dir_TEMPLATES":  "Templates",
        "user_dir_PUBLICSHARE":"Public",
        "user_dir_DOCUMENTS":  "Documents",
        "user_dir_MUSIC":      "Music",
        "user_dir_PICTURES":   "Pictures",
        "user_dir_VIDEOS":     "Videos",
    }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_rar(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in (".rar", ".r00", ".r01") or \
           bool(re.search(r"\.part\d+\.rar$", path, re.I))

def _is_encrypted(path):
    """Détecte si l'archive est protégée par mot de passe."""
    try:
        if _is_rar(path):
            r = subprocess.run([UNRAR_BIN, "v", path],
                               capture_output=True, text=True, timeout=5)
            out = r.stdout + r.stderr
            return "password" in out.lower() or "encrypted" in out.lower()
        else:
            r = subprocess.run([SZ_BIN, "l", "-p", path],
                               capture_output=True, text=True, timeout=5)
            out = r.stdout + r.stderr
            return ("encrypted" in out.lower() or
                    "wrong password" in out.lower() or
                    "cannot open encrypted" in out.lower())
    except Exception:
        return False


def _list_archive(path, password=""):
    """Retourne une liste de (name, size, is_dir) via libarchive ou fallback."""
    entries = []
    if HAS_LIBARCHIVE and not password:
        # libarchive ne supporte pas les archives chiffrées facilement
        # on l'utilise seulement sans mot de passe
        try:
            script = """
import sys, libarchive
entries = []
with libarchive.file_reader(sys.argv[1]) as a:
    for e in a:
        name   = e.pathname.rstrip("/")
        is_dir = e.isdir or e.pathname.endswith("/")
        size   = str(e.size)
        if name:
            print(f"{1 if is_dir else 0}\t{size}\t{name}")
"""
            r = subprocess.run(
                ["python3", "-c", script, path],
                capture_output=True, text=True, timeout=15)
            for line in r.stdout.splitlines():
                parts = line.split("\t", 2)
                if len(parts) == 3:
                    is_dir = parts[0] == "1"
                    size   = parts[1]
                    name   = parts[2]
                    entries.append((name, size, is_dir))
            if entries:
                return entries
        except Exception:
            pass

    # Fallback 7z/unrar (supporte les mots de passe)
    if _is_rar(path):
        try:
            cmd = [UNRAR_BIN, "v"]
            cmd += ["-p" + password] if password else ["-p-"]
            cmd += [path]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            in_list = False
            for line in r.stdout.splitlines():
                if line.strip().startswith("---"):
                    in_list = not in_list
                    continue
                if not in_list or not line.strip():
                    continue
                parts = line.strip().split(None, 7)
                if len(parts) < 8:
                    continue
                attr   = parts[0]
                size   = parts[1]
                name   = parts[7].strip()
                is_dir = "D" in attr.upper()
                if name:
                    entries.append((name, size, is_dir))
        except Exception:
            pass
    else:
        try:
            cmd = [SZ_BIN, "l"]
            if password:
                cmd.append("-p" + password)
            cmd.append(path)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            in_list = False
            for line in r.stdout.splitlines():
                if re.match(r"^-{10,}", line.strip()):
                    if in_list: break
                    in_list = True
                    continue
                if not in_list or len(line) < 53:
                    continue
                attr   = line[20:25].strip()
                size   = line[25:53].split()[0] if line[25:53].split() else "0"
                name   = line[53:].strip()
                is_dir = "D" in attr
                if name:
                    entries.append((name, size, is_dir))
        except Exception:
            pass
    return entries

def _extract(archive, names, dst, progress_cb=None, password=""):
    """Extraction via 7z/unrar avec progression optionnelle."""
    os.makedirs(dst, exist_ok=True)
    if _is_rar(archive):
        pwd_arg = "-p" + password if password else "-p-"
        cmd = [UNRAR_BIN, "x", "-y", pwd_arg, archive] + names + [dst + "/"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            if progress_cb:
                line = line.strip()
                # unrar affiche des % comme "  3%"
                m = re.search("([0-9]+)%", line)
                if m:
                    progress_cb(int(m.group(1)) / 100.0)
        proc.wait()
    else:
        # 7z avec -bsp1 affiche "xx%" sur stdout
        pwd_args = ["-p" + password] if password else []
        cmd = [SZ_BIN, "x", archive, f"-o{dst}", "-y",
               "-bsp1", "-bso0"] + pwd_args + names
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        BS = bytes([8])  # backspace — séparateur 7z
        buf = b""
        while True:
            ch = proc.stdout.read(1)
            if not ch:
                break
            if ch == BS:
                seg = buf.decode("utf-8", errors="replace").strip()
                buf = b""
                if seg:
                    m = re.search("([0-9]{1,3}) *%", seg)
                    if m and progress_cb:
                        progress_cb(int(m.group(1)) / 100.0)
            else:
                buf += ch
        proc.wait()

def _fmt_size(s):
    try:
        n = int(s)
        for u in ["B","KB","MB","GB"]:
            if n < 1024: return f"{n:.0f} {u}" if u=="B" else f"{n:.1f} {u}"
            n //= 1024
    except Exception:
        pass
    return s

import stat as _stat
import time as _time

# ---------------------------------------------------------------------------
# Entry models
# ---------------------------------------------------------------------------

class Entry(GObject.Object):
    __gtype_name__ = "ABEntry"
    def __init__(self, name, size, is_dir, depth=0):
        super().__init__()
        self.name   = name
        self.size   = size
        self.is_dir = is_dir
        self.depth  = depth
        # Chemin complet dans l'archive (pour collapse)
        self.full_path = name

class FSEntry(GObject.Object):
    __gtype_name__ = "ABFSEntry"
    def __init__(self, path):
        super().__init__()
        self.path   = path
        self.name   = os.path.basename(path)
        try:
            s = os.stat(path)
            self.is_dir = _stat.S_ISDIR(s.st_mode)
            self.size   = s.st_size
            self.mtime  = s.st_mtime
        except Exception:
            self.is_dir = os.path.isdir(path)
            self.size   = 0
            self.mtime  = 0

# ---------------------------------------------------------------------------
# File Panel (destination)
# ---------------------------------------------------------------------------

def _icon_for(path, is_dir):
    try:
        info = Gio.File.new_for_path(path).query_info("standard::icon", 0, None)
        g    = info.get_icon()
        if g and hasattr(g, "get_names"):
            n = g.get_names()
            if n: return n[0]
    except Exception:
        pass
    return "folder" if is_dir else "text-x-generic"

def _icon_paintable(name):
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    if theme.has_icon(name):
        return theme.lookup_icon(name, None, 16, 1,
            Gtk.TextDirection.LTR, Gtk.IconLookupFlags.FORCE_REGULAR)
    return None

_ICON_FLAGS_REG = Gtk.IconLookupFlags.FORCE_REGULAR

def _paintable_for_archive_entry(name, is_dir, collapsed, pixel_size=16):
    """MIME-typed + full-color icons for archive tree rows (not symbolic)."""
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    if is_dir:
        icon_name = "folder" if collapsed else "folder-open"
        p = theme.lookup_icon(icon_name, None, pixel_size, 1,
                              Gtk.TextDirection.LTR, _ICON_FLAGS_REG)
        if p:
            return p
        gicon = Gio.content_type_get_icon("inode/directory")
        return theme.lookup_by_gicon(gicon, pixel_size, 1,
                                     Gtk.TextDirection.LTR, _ICON_FLAGS_REG)
    basename = os.path.basename(name.rstrip("/"))
    mime, _ = Gio.content_type_guess(basename, None)
    if not mime:
        mime = "application/octet-stream"
    gicon = Gio.content_type_get_icon(mime)
    p = theme.lookup_by_gicon(gicon, pixel_size, 1,
                              Gtk.TextDirection.LTR, _ICON_FLAGS_REG)
    if p:
        return p
    if isinstance(gicon, Gio.ThemedIcon):
        for n in gicon.get_names():
            p = theme.lookup_icon(n, None, pixel_size, 1,
                                  Gtk.TextDirection.LTR, _ICON_FLAGS_REG)
            if p:
                return p
    return None

class FilePanel(Gtk.Box):
    __gtype_name__ = "ABFilePanel"

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._path = os.path.expanduser("~")
        # navigate() sera appelé après init si besoin

        # Header
        hbar = Gtk.Box(spacing=4)
        hbar.set_margin_start(4); hbar.set_margin_end(4)
        hbar.set_margin_top(4);   hbar.set_margin_bottom(4)

        up_btn = Gtk.Button(icon_name="go-up-symbolic")
        up_btn.set_has_frame(False)
        up_btn.connect("clicked", lambda _: self.navigate(os.path.dirname(self._path)))

        self._path_entry = Gtk.Entry()
        self._path_entry.set_hexpand(True)
        self._path_entry.connect("activate", self._on_path_activate)

        self._user_dirs_btn = Gtk.MenuButton(icon_name="user-home-symbolic")
        self._user_dirs_btn.set_has_frame(False)
        self._user_dirs_pop = Gtk.Popover()
        self._user_dirs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._user_dirs_box.set_margin_start(6); self._user_dirs_box.set_margin_end(6)
        self._user_dirs_box.set_margin_top(6);   self._user_dirs_box.set_margin_bottom(6)
        self._user_dirs_pop.set_child(self._user_dirs_box)
        self._user_dirs_btn.set_popover(self._user_dirs_pop)
        self._refresh_user_dirs()

        ref_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        ref_btn.set_has_frame(False)
        ref_btn.connect("clicked", lambda _: self.refresh())

        hbar.append(up_btn)
        hbar.append(self._path_entry)
        hbar.append(self._user_dirs_btn)
        hbar.append(ref_btn)
        self.append(hbar)
        self.append(Gtk.Separator())

        # Store + ListView
        self._store = Gio.ListStore(item_type=FSEntry)
        self._sel   = Gtk.MultiSelection.new(self._store)

        fct = Gtk.SignalListItemFactory()
        fct.connect("setup", self._setup)
        fct.connect("bind",  self._bind)

        self._lv = Gtk.ListView(model=self._sel, factory=fct)
        self._lv.set_vexpand(True)
        self._lv.add_css_class("navigation-sidebar")
        self._lv.connect("activate", self._on_activate)


        # Drop target
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self._lv.add_controller(drop)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_overlay_scrolling(False)
        scroll.set_child(self._lv)
        self.append(scroll)

        self.navigate(self._path)

    @property
    def path(self):
        return self._path

    def navigate(self, path):
        if not path or not os.path.isdir(path):
            return
        self._path = path
        self._path_entry.set_text(path)
        self.refresh()

    def _on_path_activate(self, entry):
        new_path = os.path.expanduser(entry.get_text().strip())
        if os.path.isdir(new_path):
            self.navigate(new_path)
        else:
            entry.set_text(self._path)

    def _read_user_dirs(self):
        user_dirs = [(T["home"], os.path.expanduser("~"))]
        cfg = os.path.expanduser("~/.config/user-dirs.dirs")
        if not os.path.isfile(cfg):
            return user_dirs
        try:
            with open(cfg, "r", encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    m = re.match(r'XDG_(\w+)_DIR="?(.+?)"?$', line)
                    if not m:
                        continue
                    key = m.group(1)
                    raw_path = m.group(2)
                    path = raw_path.replace("$HOME", os.path.expanduser("~"))
                    path = os.path.expandvars(path)
                    if not os.path.isabs(path):
                        continue
                    label = T.get(f"user_dir_{key}", key.replace("_", " ").title())
                    user_dirs.append((label, path))
        except Exception:
            return [(T["home"], os.path.expanduser("~"))]
        return user_dirs

    def _refresh_user_dirs(self):
        child = self._user_dirs_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._user_dirs_box.remove(child)
            child = nxt
        for label, path in self._read_user_dirs():
            btn = Gtk.Button(label=label)
            btn.set_halign(Gtk.Align.FILL)
            btn.connect("clicked", self._on_user_dir_clicked, path)
            self._user_dirs_box.append(btn)

    def _on_user_dir_clicked(self, btn, path):
        if os.path.isdir(path):
            self.navigate(path)
        self._user_dirs_pop.popdown()

    def refresh(self):
        self._store.remove_all()
        try:
            items = sorted(os.scandir(self._path), key=lambda e: (
                not e.is_dir(follow_symlinks=False),
                e.name.startswith("."),
                e.name.lower()))
            for it in items:
                self._store.append(FSEntry(it.path))
        except Exception:
            pass

    def _setup(self, fct, item):
        box  = Gtk.Box(spacing=6)
        box.set_margin_start(4); box.set_margin_end(4)
        box.set_margin_top(2);   box.set_margin_bottom(2)
        icon = Gtk.Image(); icon.set_pixel_size(16)
        lbl  = Gtk.Label(); lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True); lbl.set_ellipsize(Pango.EllipsizeMode.END)
        size = Gtk.Label(); size.set_halign(Gtk.Align.END)
        size.set_width_chars(9); size.add_css_class("dim-label")
        box.append(icon); box.append(lbl); box.append(size)
        item.set_child(box)

    def _bind(self, fct, item):
        e    = item.get_item()
        box  = item.get_child()
        icon = box.get_first_child()
        lbl  = icon.get_next_sibling()
        size = lbl.get_next_sibling()
        paint = _icon_paintable(_icon_for(e.path, e.is_dir))
        if paint: icon.set_from_paintable(paint)
        else:     icon.set_from_icon_name(_icon_for(e.path, e.is_dir))
        lbl.set_text(e.name)
        if e.is_dir: lbl.add_css_class("bold")
        else:        lbl.remove_css_class("bold")
        size.set_text("—" if e.is_dir else _fmt_size(e.size))

    def _on_activate(self, lv, pos):
        e = self._store.get_item(pos)
        if e.is_dir:
            self.navigate(e.path)
        else:
            try:
                Gio.AppInfo.launch_default_for_uri(
                    Gio.File.new_for_path(e.path).get_uri(), None)
            except Exception:
                pass

    def _on_drop(self, target, value, x, y):
        """Reçoit les fichiers droppés — les copie dans ce dossier."""
        if isinstance(value, Gdk.FileList):
            for gfile in value.get_files():
                src  = gfile.get_path()
                if not src: continue
                dst  = os.path.join(self._path, os.path.basename(src))
                try:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                except Exception:
                    pass
            self.refresh()
        return True

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

class ArchiveBrowserWindow(Adw.Window):
    __gtype_name__ = "ArchiveBrowserWindow"

    def __init__(self, archive_path):
        super().__init__()
        self.set_default_size(1000, 650)
        self.set_resizable(True)
        self._archive       = archive_path
        self._password      = ""
        self._cache_dir     = None
        self._cache_files   = {}
        self._prefetch_lock = threading.Lock()
        self._all      = []
        self._tmp      = None
        self._tmp_ready = False

        self.set_title(f"{T['title']} — {os.path.basename(archive_path)}")

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_decoration_layout(":close")
        hdr.set_title_widget(Gtk.Label(label=os.path.basename(archive_path)))
        tv.add_top_bar(hdr)

        # Recherche
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(T["filter"])
        self._search.set_margin_start(8); self._search.set_margin_end(8)
        self._search.set_margin_top(6);   self._search.set_margin_bottom(6)
        self._search.connect("search-changed", self._on_search)

        # Store + ListView
        self._store = Gio.ListStore(item_type=Entry)
        self._sel   = Gtk.MultiSelection.new(self._store)

        fct = Gtk.SignalListItemFactory()
        fct.connect("setup", self._setup)
        fct.connect("bind",  self._bind)

        self._lv = Gtk.ListView(model=self._sel, factory=fct)
        self._lv.set_vexpand(True)
        self._lv.add_css_class("navigation-sidebar")
        self._lv.connect("activate", self._on_activate)

        # On évite un GestureClick global avec calcul d'index via "y":
        # ça peut créer des zones de clic imprécises (scroll, marges, hauteurs
        # variables). On laisse GTK gérer la zone cliquable et on utilise le
        # signal natif "activate" pour ouvrir/fermer les dossiers.



        # DnD source
        drag = Gtk.DragSource()
        drag.set_actions(Gdk.DragAction.COPY)
        drag.connect("prepare",    self._dnd_prepare)
        drag.connect("drag-begin", self._dnd_begin)
        drag.connect("drag-end",   self._dnd_end)
        self._lv.add_controller(drag)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_overlay_scrolling(False)
        scroll.set_child(self._lv)

        # Boutons bas
        bar = Gtk.Box(spacing=6)
        bar.set_margin_start(8); bar.set_margin_end(8)
        bar.set_margin_top(6);   bar.set_margin_bottom(6)

        btn_all = Gtk.Button(label=T["extract_all"])
        btn_all.add_css_class("suggested-action")
        btn_all.connect("clicked", self._extract_all)

        btn_sel = Gtk.Button(label=T["extract_sel"])
        btn_sel.connect("clicked", self._extract_sel)

        bar.append(btn_all)
        bar.append(btn_sel)

        # Layout panneau gauche
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.append(self._search)
        content.append(Gtk.Separator())
        content.append(scroll)
        content.append(Gtk.Separator())
        content.append(bar)

        # Panel droit filesystem
        self._fs_panel = FilePanel()
        self._fs_panel.navigate(os.path.dirname(archive_path))

        # Paned
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(420)
        paned.set_wide_handle(True)
        paned.set_start_child(content)
        paned.set_end_child(self._fs_panel)

        # Barre de progression — toute la largeur en bas
        self._prog = Gtk.ProgressBar()
        self._prog.set_visible(False)
        self._prog.set_margin_start(8)
        self._prog.set_margin_end(8)
        self._prog.set_margin_top(4)
        self._prog.set_margin_bottom(4)

        # Layout principal
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.append(paned)
        main.append(self._prog)

        tv.set_content(main)
        self.set_content(tv)

        # CSS
        css = Gtk.CssProvider()
        css.load_from_data(b".bold { font-weight: bold; }")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Escape
        sc = Gtk.ShortcutController()
        sc.set_scope(Gtk.ShortcutScope.MANAGED)
        sc.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("Escape"),
            Gtk.CallbackAction.new(lambda *_: self.close() or True)))
        self.add_controller(sc)

        # Charger
        self.connect("map",          lambda *_: self._load())
        self.connect("close-request", lambda *_: self._cleanup_cache() or False)

    # -- Chargement ----------------------------------------------------------

    def _load(self):
        threading.Thread(target=self._do_load, daemon=True).start()

    def _do_load(self):
        entries = _list_archive(self._archive, self._password)
        if not entries and not self._password:
            # Vérifier si l'archive est chiffrée
            if _is_encrypted(self._archive):
                GLib.idle_add(self._ask_password)
                return
        GLib.idle_add(self._apply, entries)

    def _ask_password(self):
        """Dialog mot de passe Adw."""
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading=T["pwd_title"],
            body=T["pwd_body"])
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        entry.set_placeholder_text(T["pwd_placeholder"])
        entry.set_margin_top(8)
        entry.connect("activate", lambda e: dlg.response("ok"))
        dlg.set_extra_child(entry)
        dlg.add_response("cancel", T["pwd_cancel"])
        dlg.add_response("ok",     T["pwd_ok"])
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("ok")
        dlg.connect("response", lambda d, r: self._on_password_response(
            d, r, entry.get_text()))
        dlg.present()
        return False

    def _on_password_response(self, dlg, response, password):
        dlg.close()
        if response == "ok" and password:
            self._password = password
            self._load()
        return False

    def _apply(self, entries):
        # Construire l'arbre depuis la liste plate
        self._collapsed = set()
        self._tree      = self._build_tree(entries)

        # Collapser tous les sous-dossiers par défaut
        for e in self._tree:
            if e.is_dir and e.depth > 0:
                self._collapsed.add(e.full_path)
        self._refresh_store()
        return False

    def _build_tree(self, entries):
        """Construit l'arbre trié — dossiers d'abord, contenu sous son parent."""
        from collections import defaultdict
        children = defaultdict(list)
        all_paths = set()

        for name, size, is_dir in entries:
            parent = os.path.dirname(name.rstrip("/"))
            depth  = name.rstrip("/").count("/")
            e      = Entry(name, size, is_dir, depth)
            children[parent].append(e)
            all_paths.add(name.rstrip("/"))

        # Trier chaque niveau : dossiers d'abord
        for key in children:
            children[key].sort(key=lambda e: (not e.is_dir, e.name.lower()))

        # Parcours en profondeur
        result = []
        def _walk(parent):
            for e in children.get(parent, []):
                result.append(e)
                if e.is_dir:
                    _walk(e.full_path.rstrip("/"))

        # Racines = parents qui ne sont pas dans all_paths
        roots = sorted(p for p in children.keys() if p not in all_paths)

        # Si pas de racine trouvée — cas ZIP sans dossier racine explicite
        if not roots:
            roots = sorted(children.keys())

        for r in roots:
            _walk(r)

        # Si toujours vide — listing plat sans arbre
        if not result:
            for name, size, is_dir in entries:
                depth = name.count("/")
                result.append(Entry(name, size, is_dir, depth))

        return result

    def _refresh_store(self):
        self._store.remove_all()
        for e in self._tree:
            if self._is_visible(e):
                self._store.append(e)

    def _is_visible(self, entry):
        """Vrai si aucun ancêtre n'est collapsed — O(depth) grâce au set."""
        path  = entry.full_path.rstrip("/")
        parts = path.split("/")
        for i in range(len(parts) - 1):
            ancestor = "/".join(parts[:i+1])
            if ancestor in self._collapsed:
                return False
        return True

    # -- Factory -------------------------------------------------------------

    def _setup(self, fct, item):
        box  = Gtk.Box(spacing=6)
        box.set_margin_start(4); box.set_margin_end(4)
        box.set_margin_top(2);   box.set_margin_bottom(2)
        icon = Gtk.Image(); icon.set_pixel_size(16)
        name = Gtk.Label(); name.set_halign(Gtk.Align.START)
        name.set_hexpand(True); name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        size = Gtk.Label(); size.set_halign(Gtk.Align.END)
        size.set_width_chars(10); size.add_css_class("dim-label")
        box.append(icon); box.append(name); box.append(size)
        item.set_child(box)

        # Clic simple sur une ligne dossier => toggle expand/collapse.
        # On évite le calcul manuel via "y" pour que les click zones soient
        # cohérentes partout.
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect(
            "pressed",
            lambda g, n_press, x, y, li=item: self._on_row_single_click(g, n_press, x, y, li),
        )
        box.add_controller(click)

    def _bind(self, fct, item):
        e    = item.get_item()
        box  = item.get_child()
        icon = box.get_first_child()
        name = icon.get_next_sibling()
        size = name.get_next_sibling()

        # Indentation selon profondeur
        box.set_margin_start(4 + e.depth * 16)

        if e.is_dir:
            collapsed = e.full_path in self._collapsed
            paint = _paintable_for_archive_entry(e.name, True, collapsed)
            if paint:
                icon.set_from_paintable(paint)
            else:
                icon.set_from_icon_name(
                    "folder" if collapsed else "folder-open")
            name.add_css_class("bold")
            size.set_text("▶" if collapsed else "▼")
        else:
            paint = _paintable_for_archive_entry(e.name, False, False)
            if paint:
                icon.set_from_paintable(paint)
            else:
                icon.set_from_icon_name("text-x-generic")
            name.remove_css_class("bold")
            size.set_text(_fmt_size(e.size))
        # Afficher seulement le nom (pas le chemin complet)
        name.set_text(os.path.basename(e.name.rstrip("/")))

    def _on_row_single_click(self, gesture, n_press, x, y, list_item):
        """Toggle expand/collapse sur clic simple de la ligne dossier."""
        if n_press != 1:
            return
        e = list_item.get_item()
        if not e or not e.is_dir:
            return
        saved = self._selection_path_set()
        saved.add(e.full_path.rstrip("/"))
        if e.full_path in self._collapsed:
            self._collapsed.discard(e.full_path)
        else:
            self._collapsed.add(e.full_path)
        self._refresh_store()
        self._apply_selection_paths(saved)

    # -- Recherche -----------------------------------------------------------

    def _on_search(self, entry):
        text = entry.get_text().lower().strip()
        self._store.remove_all()
        if not text:
            self._refresh_store()
        else:
            for e in self._tree:
                if text in e.name.lower():
                    self._store.append(e)

    # -- Activation ----------------------------------------------------------

    def _ensure_extracted(self, name):
        """Extrait si nécessaire et retourne le chemin local."""
        with self._prefetch_lock:
            if name in self._cache_files:
                p = self._cache_files[name]
                if os.path.exists(p):
                    return p
            # Créer le cache dir si nécessaire
            if not self._cache_dir or not os.path.isdir(self._cache_dir):
                self._cache_dir = tempfile.mkdtemp(prefix="ab_cache_")
        # Extraire (hors lock pour ne pas bloquer)
        _extract(self._archive, [name], self._cache_dir, password=self._password)
        # Chercher le fichier extrait
        base = os.path.basename(name)
        for root, dirs, files in os.walk(self._cache_dir):
            if base in files:
                path = os.path.join(root, base)
                with self._prefetch_lock:
                    self._cache_files[name] = path
                return path
        return None

    def _list_row_index_at_y(self, widget, y):
        row = widget.get_first_child()
        idx, cumul = 0, 0
        while row:
            h = row.get_height()
            if cumul <= y < cumul + h:
                return idx
            cumul += h
            idx += 1
            row = row.get_next_sibling()
        return None

    def _selection_path_set(self):
        sel = self._sel.get_selection()
        paths = set()
        for i in range(self._store.get_n_items()):
            if sel.contains(i):
                paths.add(self._store.get_item(i).full_path.rstrip("/"))
        return paths

    def _apply_selection_paths(self, paths):
        if not paths:
            return
        first = True
        for i in range(self._store.get_n_items()):
            key = self._store.get_item(i).full_path.rstrip("/")
            if key in paths:
                self._sel.select_item(i, first)
                first = False

    def _on_archive_row_click(self, gesture, n_press, x, y):
        """Simple clic sur dossier = ouvrir/fermer l'arbre."""
        if n_press != 1:
            return
        widget = gesture.get_widget()
        idx = self._list_row_index_at_y(widget, y)
        if idx is None or idx >= self._store.get_n_items():
            return
        e = self._store.get_item(idx)
        if not e or not e.is_dir:
            return
        saved = self._selection_path_set()
        saved.add(e.full_path.rstrip("/"))
        if e.full_path in self._collapsed:
            self._collapsed.discard(e.full_path)
        else:
            self._collapsed.add(e.full_path)
        self._refresh_store()
        self._apply_selection_paths(saved)

    def _on_activate(self, lv, pos):
        """Double-clic : extrait et ouvre."""
        e = self._store.get_item(pos)
        if e.is_dir:
            return
        tmp = tempfile.mkdtemp(prefix="ab_open_")
        def _work():
            _extract(self._archive, [e.name], tmp, password=self._password)
            # Chercher le fichier extrait
            for root, dirs, files in os.walk(tmp):
                for f in files:
                    if f == os.path.basename(e.name):
                        path = os.path.join(root, f)
                        GLib.idle_add(lambda p=path: Gio.AppInfo.launch_default_for_uri(
                            Gio.File.new_for_path(p).get_uri(), None))
                        return
        threading.Thread(target=_work, daemon=True).start()

    # -- Extraction ----------------------------------------------------------

    def _get_selected_names(self):
        sel  = self._sel.get_selection()
        names = []
        for i in range(self._store.get_n_items()):
            if sel.contains(i):
                names.append(self._store.get_item(i).name)
        return names

    def _prog_start(self):
        """Pulse pour le DnD — on ne connaît pas le % d'avance."""
        self._prog.set_visible(True)
        self._prog.pulse()
        if not hasattr(self, "_pulse_active") or not self._pulse_active:
            self._pulse_active = True
            GLib.timeout_add(80, self._pulse_tick)
        return False

    def _pulse_tick(self):
        if self._prog.get_visible():
            self._prog.pulse()
            return True
        self._pulse_active = False
        return False

    def _prog_stop(self):
        self._prog.set_visible(False)
        return False

    def _extract_all(self, _):
        self._do_extract([])

    def _extract_sel(self, _):
        names = self._get_selected_names()
        if names:
            self._do_extract(names, flat=True)

    def _do_extract(self, names, flat=False):
        dst = self._fs_panel.path
        self._prog.set_visible(True)
        self._prog.set_fraction(0.0)

        def _on_progress(fraction):
            GLib.idle_add(self._prog.set_fraction, fraction)

        def _work():
            if flat and names:
                # Séparer fichiers et dossiers
                selected_entries = {e.full_path: e for e in self._tree
                                    if e.full_path in names or e.name in names}
                dirs_selected  = [n for n in names
                                  if any(e.is_dir and e.full_path == n
                                         for e in self._tree)]
                files_selected = [n for n in names if n not in dirs_selected]

                tmp = tempfile.mkdtemp(prefix="ab_flat_")
                try:
                    _extract(self._archive, names, tmp, progress_cb=_on_progress)
                    # Fichiers → extraction plate (sans arborescence)
                    for root, dirs, files in os.walk(tmp):
                        # Ignorer les sous-dossiers des dossiers sélectionnés
                        rel = os.path.relpath(root, tmp)
                        is_in_selected_dir = any(
                            rel == d.rstrip("/") or rel.startswith(d.rstrip("/") + os.sep)
                            for d in dirs_selected)
                        if is_in_selected_dir:
                            continue  # traité séparément
                        for fname in files:
                            src = os.path.join(root, fname)
                            out = os.path.join(dst, fname)
                            base, ext = os.path.splitext(fname)
                            n = 1
                            while os.path.exists(out):
                                out = os.path.join(dst, f"{base} ({n}){ext}")
                                n += 1
                            shutil.move(src, out)
                    # Dossiers → garder la structure
                    for d in dirs_selected:
                        folder_name = os.path.basename(d.rstrip("/"))
                        src_dir = os.path.join(tmp, d.rstrip("/"))
                        if os.path.isdir(src_dir):
                            out_dir = os.path.join(dst, folder_name)
                            if os.path.exists(out_dir):
                                shutil.copytree(src_dir, out_dir,
                                                dirs_exist_ok=True)
                            else:
                                shutil.move(src_dir, out_dir)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            else:
                _extract(self._archive, names, dst, password=self._password, progress_cb=_on_progress)
            GLib.idle_add(self._extract_done, dst)
        threading.Thread(target=_work, daemon=True).start()

    def _extract_done(self, dst):
        self._prog_stop()
        self._fs_panel.refresh()
        return False

    # -- DnD -----------------------------------------------------------------
    # prepare() est appelé AVANT begin() dans GTK4.
    # On utilise le cache — si le fichier a été pré-extrait au survol
    # le DnD est instantané, sinon on extrait synchrone (cas rare).

    def _dnd_prepare(self, drag_src, x, y):
        """Retourne les fichiers depuis le cache ou extrait si nécessaire."""
        names = self._get_selected_names()
        if not names:
            return None
        # Vérifier si déjà en cache
        all_cached = all(
            n in self._cache_files and os.path.exists(self._cache_files[n])
            for n in names)
        if not all_cached:
            GLib.idle_add(self._prog_start)
        files = []
        for name in names:
            path = self._ensure_extracted(name)
            if path and os.path.exists(path):
                files.append(Gio.File.new_for_path(path))
        GLib.idle_add(self._prog_stop)
        if not files:
            return None
        return Gdk.ContentProvider.new_for_value(
            Gdk.FileList.new_from_list(files))

    def _dnd_begin(self, drag_src, drag):
        icon = Gtk.DragIcon.get_for_drag(drag)
        mime, _ = Gio.content_type_guess(os.path.basename(self._archive), None)
        if not mime:
            mime = "application/octet-stream"
        gicon = Gio.content_type_get_icon(mime)
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        paint = theme.lookup_by_gicon(gicon, 32, 1, Gtk.TextDirection.LTR,
                                      _ICON_FLAGS_REG)
        img = Gtk.Image()
        img.set_pixel_size(32)
        if paint:
            img.set_from_paintable(paint)
        else:
            img.set_from_icon_name("package-x-generic")
        icon.set_child(img)

    def _dnd_end(self, drag_src, drag, delete_data):
        pass  # Cache conservé pour réutilisation

    def _cleanup_cache(self):
        """Nettoyage à la fermeture de la fenêtre."""
        with self._prefetch_lock:
            if self._cache_dir and os.path.exists(self._cache_dir):
                shutil.rmtree(self._cache_dir, ignore_errors=True)
            self._cache_dir   = None
            self._cache_files = {}
        return False

# ---------------------------------------------------------------------------
# Nautilus extension
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Archive Creator Window
# ---------------------------------------------------------------------------

class ArchiveCreatorWindow(Adw.Window):
    __gtype_name__ = "ArchiveCreatorWindow"

    FORMATS = ["rar", "zip", "7z", "tar.gz", "tar.bz2", "tar.xz"]
    LEVELS  = ["0 - Store", "1 - Fastest", "3 - Fast", "5 - Normal",
                "7 - Maximum", "9 - Ultra"]

    def __init__(self, source_paths):
        super().__init__()
        self._sources = source_paths
        self._dest_dir = os.path.dirname(source_paths[0])

        # Nom par défaut = premier élément
        default_name = os.path.basename(source_paths[0])
        if len(source_paths) > 1:
            default_name = os.path.basename(self._dest_dir)

        app = Gtk.Application.get_default()
        parent = app.get_active_window() if app else None
        self.set_transient_for(parent)
        self.set_default_size(440, -1)
        self.set_resizable(False)
        self.set_title(T["create_title"])

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_decoration_layout(":close")
        hdr.set_title_widget(Gtk.Label(label=T["create_title"]))
        tv.add_top_bar(hdr)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(18); box.set_margin_end(18)
        box.set_margin_top(12);   box.set_margin_bottom(18)

        # Nom
        box.append(Gtk.Label(label=T["create_name"], halign=Gtk.Align.START))
        self._name_entry = Gtk.Entry()
        self._name_entry.set_text(default_name)
        box.append(self._name_entry)

        # Format
        box.append(Gtk.Label(label=T["create_format"], halign=Gtk.Align.START))
        self._fmt_combo = Gtk.DropDown.new_from_strings(self.FORMATS)
        self._fmt_combo.set_selected(0)  # RAR par défaut
        self._fmt_combo.connect("notify::selected", self._on_format_changed)
        box.append(self._fmt_combo)

        # Niveau de compression
        box.append(Gtk.Label(label=T["create_level"], halign=Gtk.Align.START))
        self._lvl_combo = Gtk.DropDown.new_from_strings(self.LEVELS)
        self._lvl_combo.set_selected(3)  # Normal
        box.append(self._lvl_combo)

        # Mot de passe
        box.append(Gtk.Label(label=T["create_pwd"], halign=Gtk.Align.START))
        self._pwd_entry = Gtk.Entry()
        self._pwd_entry.set_visibility(False)
        self._pwd_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        box.append(self._pwd_entry)

        # Split volumes (RAR/7z seulement)
        self._split_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._split_box.append(
            Gtk.Label(label=T["create_split"], halign=Gtk.Align.START))
        self._split_entry = Gtk.Entry()
        self._split_entry.set_text("0")
        self._split_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        self._split_box.append(self._split_entry)
        box.append(self._split_box)

        box.append(Gtk.Separator())

        # Bouton créer
        self._create_btn = Gtk.Button(label=T["create_btn"])
        self._create_btn.add_css_class("suggested-action")
        self._create_btn.connect("clicked", self._on_create)
        box.append(self._create_btn)

        # Progress
        self._prog = Gtk.ProgressBar()
        self._prog.set_visible(False)
        box.append(self._prog)

        tv.set_content(box)
        self.set_content(tv)

        # Escape
        sc = Gtk.ShortcutController()
        sc.set_scope(Gtk.ShortcutScope.MANAGED)
        sc.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("Escape"),
            Gtk.CallbackAction.new(lambda *_: self.close() or True)))
        self.add_controller(sc)

    def _on_format_changed(self, combo, _):
        fmt = self.FORMATS[combo.get_selected()]
        # Split uniquement pour rar et 7z
        self._split_box.set_visible(fmt in ("rar", "7z"))

    def _on_create(self, _):
        name    = self._name_entry.get_text().strip()
        fmt     = self.FORMATS[self._fmt_combo.get_selected()]
        level   = self._lvl_combo.get_selected()  # 0-5 → 0,1,3,5,7,9
        pwd     = self._pwd_entry.get_text().strip()
        split   = self._split_entry.get_text().strip()

        if not name:
            return

        # Ajouter l'extension si manquante
        ext = "." + fmt if not fmt.startswith("tar") else "." + fmt
        if not name.endswith(ext):
            name += ext

        out_path = os.path.join(self._dest_dir, name)

        # Niveaux : index 0-5 → valeurs réelles
        lvl_map = [0, 1, 3, 5, 7, 9]
        lvl_val = lvl_map[min(level, 5)]

        self._create_btn.set_sensitive(False)
        self._prog.set_visible(True)
        self._prog.pulse()

        def _pulse():
            if self._prog.get_visible():
                self._prog.pulse()
                return True
            return False
        GLib.timeout_add(80, _pulse)

        def _work():
            try:
                self._run_create(out_path, fmt, lvl_val, pwd, split)
                GLib.idle_add(self._on_done, out_path, None)
            except Exception as e:
                GLib.idle_add(self._on_done, out_path, str(e))

        threading.Thread(target=_work, daemon=True).start()

    def _run_create(self, out_path, fmt, level, pwd, split):
        """Lance la commande de création d'archive."""
        srcs = self._sources

        # Utiliser des chemins relatifs pour ne pas polluer l'archive avec
        # la structure de dossiers absolue (/home/user/…).
        # Si toutes les sources partagent le même parent (cas standard dans
        # Nautilus), on lance la commande depuis ce dossier.
        parents = {os.path.dirname(s) for s in srcs}
        if len(parents) == 1:
            cwd      = parents.pop()
            rel_srcs = [os.path.basename(s) for s in srcs]
        else:
            # Sources dans des dossiers différents — on garde les chemins absolus
            cwd      = None
            rel_srcs = srcs

        if fmt == "rar":
            cmd = [RAR_BIN, "a", f"-m{level}"]
            if pwd:   cmd.append(f"-hp{pwd}")
            if split and split != "0":
                cmd.append(f"-v{split}m")
            cmd += [out_path] + rel_srcs

        elif fmt == "7z":
            cmd = [SZ_BIN, "a", f"-mx={level}"]
            if pwd:   cmd += [f"-p{pwd}", "-mhe=on"]
            if split and split != "0":
                cmd.append(f"-v{split}m")
            cmd += [out_path] + rel_srcs

        elif fmt == "zip":
            cmd = [SZ_BIN, "a", "-tzip", f"-mx={level}"]
            if pwd:   cmd.append(f"-p{pwd}")
            cmd += [out_path] + rel_srcs

        elif fmt.startswith("tar"):
            # tar.gz / tar.bz2 / tar.xz — -C pour changer de dossier
            compress_map = {"tar.gz": "z", "tar.bz2": "j", "tar.xz": "J"}
            flag = compress_map.get(fmt, "z")
            if cwd:
                cmd = ["tar", f"-c{flag}f", out_path, "-C", cwd] + rel_srcs
            else:
                cmd = ["tar", f"-c{flag}f", out_path] + rel_srcs
            cwd = None  # tar gère lui-même le -C, pas besoin de cwd subprocess

        else:
            raise ValueError(f"Format inconnu: {fmt}")

        result = subprocess.run(cmd, capture_output=True, cwd=cwd)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace"))

    def _on_done(self, out_path, error):
        self._prog.set_visible(False)
        self._create_btn.set_sensitive(True)
        if error:
            dlg = Adw.MessageDialog(transient_for=self,
                heading=T["create_err"], body=error)
            dlg.add_response("ok", "OK")
            dlg.present()
        else:
            # Ouvrir le dossier de destination dans Nautilus
            try:
                Gio.AppInfo.launch_default_for_uri(
                    Gio.File.new_for_path(self._dest_dir).get_uri(), None)
            except Exception:
                pass
            self.close()
        return False


class ArchiveBrowserExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "ArchiveBrowserExtension"

    def __init__(self):
        super().__init__()
        self._hooked    = set()
        self._last_path = None
        GLib.timeout_add(600, self._hook_windows)

    def _hook_windows(self):
        app = Gtk.Application.get_default()
        if app:
            for win in app.get_windows():
                wid = id(win)
                if wid not in self._hooked and isinstance(win, Gtk.ApplicationWindow):
                    self._attach_f7(win)
                    self._hooked.add(wid)
        return True

    def _attach_f7(self, window):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        t = Gtk.ShortcutTrigger.parse_string("F7")
        a = Gtk.CallbackAction.new(lambda *_: self._open_last() or True)
        ctrl.add_shortcut(Gtk.Shortcut.new(t, a))
        window.add_controller(ctrl)

    def _open_last(self):
        if self._last_path:
            ArchiveBrowserWindow(self._last_path).present()

    def get_file_items(self, files):
        if not files:
            return []

        local = [f for f in files if f.get_uri_scheme() == "file"]
        if not local:
            return []

        archives = [f for f in local
                    if not f.is_directory()
                    and any(f.get_name().lower().endswith(ext)
                            for ext in ARCHIVE_EXTS)]

        # Cas 1 : une seule archive → Parcourir
        if len(archives) == 1 and len(local) == 1:
            self._last_path = archives[0].get_location().get_path()
            item = Nautilus.MenuItem(
                name="ArchiveBrowser::Open",
                label=T["menu_label"],
                tip="Browse archive contents",
                icon="package-x-generic",
            )
            item.connect("activate", lambda *_:
                ArchiveBrowserWindow(
                    archives[0].get_location().get_path()).present())
            return [item]

        # Cas 2 : fichiers/dossiers lambda → Créer une archive
        non_archives = [f for f in local
                        if f.is_directory() or
                        not any(f.get_name().lower().endswith(ext)
                                for ext in ARCHIVE_EXTS)]
        if non_archives or (local and not archives):
            paths = [f.get_location().get_path() for f in local
                     if f.get_location().get_path()]
            if not paths:
                return []
            item = Nautilus.MenuItem(
                name="ArchiveBrowser::Create",
                label=T["create_label"],
                tip="Create an archive from selected files",
                icon="package-x-generic",
            )
            item.connect("activate", lambda *_:
                ArchiveCreatorWindow(paths).present())
            return [item]

        return []

    def get_background_items(self, folder):
        return []
