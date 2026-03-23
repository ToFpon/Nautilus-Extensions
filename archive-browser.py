#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

ARCHIVE_EXTS = {".zip", ".7z", ".tar", ".gz", ".bz2", ".xz",
                ".rar", ".tgz", ".tbz2", ".cab", ".iso"}

_lang = locale.getlocale()[0] or ""
if _lang.startswith("fr"):
    T = {
        "menu_label":   "Parcourir l'archive",
        "title":        "Navigateur d'archives",
        "filter":       "Filtrer…",
        "extract_all":  "Tout extraire",
        "extract_sel":  "Extraire la sélection",
        "go_up":        "Dossier parent",
        "refresh":      "Actualiser",
    }
else:
    T = {
        "menu_label":   T["menu_label"],
        "title":        "Archive Browser",
        "filter":       "Filter…",
        "extract_all":  "Extract all",
        "extract_sel":  "Extract selection",
        "go_up":        "Parent folder",
        "refresh":      "Refresh",
    }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_rar(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in (".rar", ".r00", ".r01") or \
           bool(re.search(r"\.part\d+\.rar$", path, re.I))

def _list_archive(path):
    """Retourne une liste de (name, size, is_dir) via libarchive ou fallback."""
    entries = []
    if HAS_LIBARCHIVE:
        try:
            # Lancer dans un subprocess pour éviter les conflits de signaux
            # avec GTK/GLib dans le thread principal
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
            pass  # fallback ci-dessous

    # Fallback 7z/unrar
    if _is_rar(path):
        try:
            r = subprocess.run([UNRAR_BIN, "v", path],
                               capture_output=True, text=True, timeout=10)
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
            r = subprocess.run([SZ_BIN, "l", path],
                               capture_output=True, text=True, timeout=10)
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

def _extract(archive, names, dst, progress_cb=None):
    """Extraction via 7z/unrar avec progression optionnelle."""
    os.makedirs(dst, exist_ok=True)
    if _is_rar(archive):
        # unrar affiche "xx%" sur chaque ligne
        cmd = [UNRAR_BIN, "x", "-y", "-p-", archive] + names + [dst + "/"]
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
        cmd = [SZ_BIN, "x", archive, f"-o{dst}", "-y",
               "-bsp1", "-bso0"] + names
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

        self._path_lbl = Gtk.Label()
        self._path_lbl.set_halign(Gtk.Align.START)
        self._path_lbl.set_hexpand(True)
        self._path_lbl.set_ellipsize(Pango.EllipsizeMode.START)
        self._path_lbl.add_css_class("dim-label")

        ref_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        ref_btn.set_has_frame(False)
        ref_btn.connect("clicked", lambda _: self.refresh())

        hbar.append(up_btn)
        hbar.append(self._path_lbl)
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
        self._path_lbl.set_text(path)
        self.refresh()

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

        # Clic simple pour expand/collapse + prefetch DnD
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("pressed", self._on_click)
        self._lv.add_controller(click)



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
        entries = _list_archive(self._archive)
        GLib.idle_add(self._apply, entries)

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
            icon.set_from_icon_name(
                "folder-symbolic" if collapsed else "folder-open-symbolic")
            name.add_css_class("bold")
            size.set_text("▶" if collapsed else "▼")
        else:
            ext   = os.path.splitext(e.name)[1].lower()
            iname = "text-x-generic-symbolic"
            for exts, ico in [
                ({".jpg",".jpeg",".png",".gif",".webp",".svg"}, "image-x-generic-symbolic"),
                ({".mp4",".mkv",".avi",".mov",".webm"},          "video-x-generic-symbolic"),
                ({".mp3",".flac",".ogg",".wav"},                 "audio-x-generic-symbolic"),
                ({".pdf"},                                        "application-pdf-symbolic"),
                ({".zip",".7z",".rar",".tar"},                   "package-x-generic-symbolic"),
                ({".py",".js",".sh",".c",".cpp"},               "text-x-script-symbolic"),
            ]:
                if ext in exts: iname = ico; break
            icon.set_from_icon_name(iname)
            name.remove_css_class("bold")
            size.set_text(_fmt_size(e.size))
        # Afficher seulement le nom (pas le chemin complet)
        name.set_text(os.path.basename(e.name.rstrip("/")))

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
        _extract(self._archive, [name], self._cache_dir)
        # Chercher le fichier extrait
        base = os.path.basename(name)
        for root, dirs, files in os.walk(self._cache_dir):
            if base in files:
                path = os.path.join(root, base)
                with self._prefetch_lock:
                    self._cache_files[name] = path
                return path
        return None

    def _on_click(self, gesture, n, x, y):
        """Simple clic — toggle collapse pour les dossiers."""
        widget = gesture.get_widget()
        row    = widget.get_first_child()
        idx    = 0; cumul = 0
        while row:
            h = row.get_height()
            if cumul <= y < cumul + h:
                break
            cumul += h; idx += 1
            row = row.get_next_sibling()
        if idx >= self._store.get_n_items():
            return
        e = self._store.get_item(idx)
        if not e or not e.is_dir:
            return
        if e.full_path in self._collapsed:
            self._collapsed.discard(e.full_path)
        else:
            self._collapsed.add(e.full_path)
        self._refresh_store()

    def _on_activate(self, lv, pos):
        """Double-clic : extrait et ouvre."""
        e = self._store.get_item(pos)
        if e.is_dir:
            return
        tmp = tempfile.mkdtemp(prefix="ab_open_")
        def _work():
            _extract(self._archive, [e.name], tmp)
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
            self._do_extract(names)

    def _do_extract(self, names):
        dst = self._fs_panel.path
        self._prog.set_visible(True)
        self._prog.set_fraction(0.0)

        def _on_progress(fraction):
            GLib.idle_add(self._prog.set_fraction, fraction)

        def _work():
            _extract(self._archive, names, dst,
                     progress_cb=_on_progress)
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
        icon.set_child(Gtk.Image.new_from_icon_name("package-x-generic-symbolic"))

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
        archives = [f for f in files
                    if f.get_uri_scheme() == "file"
                    and not f.is_directory()
                    and any(f.get_name().lower().endswith(ext)
                            for ext in ARCHIVE_EXTS)]
        if not archives:
            return []
        self._last_path = archives[0].get_location().get_path()
        item = Nautilus.MenuItem(
            name="ArchiveBrowser::Open",
            label=T["menu_label"],
            tip="Browse archive contents",
            icon="package-x-generic-symbolic",
        )
        item.connect("activate", lambda *_:
            ArchiveBrowserWindow(
                archives[0].get_location().get_path()).present())
        return [item]

    def get_background_items(self, folder):
        return []