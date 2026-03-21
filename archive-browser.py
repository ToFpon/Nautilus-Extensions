#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Archive Browser – Nautilus Python Extension
# DESC: Browse and extract archive contents with drag & drop
# REQUIRES: python3-nautilus, python3-gi, gir1.2-adw-1, p7zip-full, unrar
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

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "title":         "Navigateur d'archives",
        "menu_label":    "Parcourir l'archive",
        "col_name":      "Nom",
        "col_size":      "Taille",
        "col_date":      "Date",
        "col_type":      "Type",
        "extract_all":   "Tout extraire",
        "extract_sel":   "Extraire la sélection",
        "dest_label":    "Destination :",
        "browse":        "Parcourir…",
        "loading":       "Chargement de l'archive…",
        "extracting":    "Extraction…",
        "done":          "Extraction terminée",
        "err_title":     "Erreur",
        "err_open":      "Impossible d'ouvrir l'archive",
        "drop_hint":     "Glissez les fichiers vers le gestionnaire de fichiers",
        "no_selection":  "Aucun fichier sélectionné",
        "cancel":        "Annuler",
        "ok":            "OK",
        "folder":        "Dossier",
        "file":          "Fichier",
    }
else:
    T = {
        "title":         "Archive Browser",
        "menu_label":    "Browse archive",
        "col_name":      "Name",
        "col_size":      "Size",
        "col_date":      "Date",
        "col_type":      "Type",
        "extract_all":   "Extract all",
        "extract_sel":   "Extract selection",
        "dest_label":    "Destination:",
        "browse":        "Browse…",
        "loading":       "Loading archive…",
        "extracting":    "Extracting…",
        "done":          "Extraction complete",
        "err_title":     "Error",
        "err_open":      "Cannot open archive",
        "drop_hint":     "Drag files to your file manager",
        "no_selection":  "No file selected",
        "cancel":        "Cancel",
        "ok":            "OK",
        "folder":        "Folder",
        "file":          "File",
    }

SZ_BIN    = shutil.which("7z") or "/usr/bin/7z"
UNRAR_BIN = shutil.which("unrar") or "/usr/bin/unrar"

ARCHIVE_EXTS = {
    ".7z", ".zip", ".rar", ".tar", ".gz", ".bz2", ".xz",
    ".zst", ".cab", ".iso", ".deb", ".rpm", ".tar.gz",
    ".tar.bz2", ".tar.xz", ".tar.zst", ".tgz", ".tbz2",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    return app.get_active_window()

def _fmt_size(n):
    try:
        n = int(n)
        for u in ["B", "KB", "MB", "GB", "TB"]:
            if n < 1024:
                return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
            n /= 1024
    except Exception:
        pass
    return str(n)

def _is_rar(path):
    ext    = os.path.splitext(path)[1].lower()
    result = ext in (".rar", ".r00", ".r01", ".r02") or \
             bool(re.search(r"\.part\d+\.rar$", path, re.IGNORECASE))
    with open("/tmp/archive_debug.txt", "a") as f:
        f.write(f"_is_rar({path}) ext={ext} → {result}\n")
    return result

# ---------------------------------------------------------------------------
# Archive entry model
# ---------------------------------------------------------------------------

class ArchiveEntry(GObject.Object):
    __gtype_name__ = "ABArchiveEntry"

    def __init__(self, path, size, date, is_dir):
        super().__init__()
        self.path   = path          # chemin interne dans l'archive
        self.name   = os.path.basename(path.rstrip("/"))
        self.size   = size
        self.date   = date
        self.is_dir = is_dir
        self.depth  = path.rstrip("/").count("/")

# ---------------------------------------------------------------------------
# Archive listing
# ---------------------------------------------------------------------------

def _list_archive(archive_path):
    """Liste le contenu d'une archive. Retourne liste de ArchiveEntry."""
    entries = []

    if _is_rar(archive_path):
        # unrar v — Format: attr size packed ratio date time checksum name
        try:
            result = subprocess.run(
                [UNRAR_BIN, "v", archive_path],
                capture_output=True, text=True, timeout=10)
            in_list = False
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("---"):
                    in_list = not in_list
                    continue
                if not in_list or not stripped:
                    continue
                parts = stripped.split(None, 7)
                if len(parts) < 8:
                    continue
                attr   = parts[0]
                size   = parts[1]
                date   = parts[4] + " " + parts[5]
                name   = parts[7].strip()
                is_dir = "D" in attr.upper() or name.endswith("/")
                if name:
                    entries.append(ArchiveEntry(name, size, date, is_dir))
        except Exception as e:
            with open("/tmp/archive_debug.txt", "a") as f:
                f.write(f"unrar error: {e}\n")
    else:
        # 7z l — format tabulaire
        # Après la ligne "---...", chaque ligne est:
        # date  time  attr  size  compressed  name
        try:
            result = subprocess.run(
                [SZ_BIN, "l", archive_path],
                capture_output=True, text=True, timeout=10)
            in_list = False
            for line in result.stdout.splitlines():
                # Ligne séparatrice "---..."
                if re.match(r"^-{10,}", line.strip()):
                    if in_list:
                        break  # 2ème séparateur = fin de liste
                    in_list = True
                    continue
                if not in_list or len(line) < 53:
                    continue
                try:
                    date   = line[0:10] + " " + line[11:19]
                    attr   = line[20:25].strip()
                    size   = line[25:53].split()[0] if line[25:53].split() else "0"
                    name   = line[53:].strip()
                    is_dir = "D" in attr or name.endswith("/")
                    if name:
                        entries.append(ArchiveEntry(name, size, date, is_dir))
                except Exception:
                    continue
        except Exception as e:
            import sys; print(f"[archive] 7z error: {e}", file=sys.stderr)
    # Trier : dossiers d'abord, puis fichiers, ordre alphabétique
    entries.sort(key=lambda e: (not e.is_dir, e.path.lower()))
    return entries

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _extract_entries(archive_path, entries, dst_dir, password="", callback=None):
    """Extrait des entrées spécifiques (ou toutes si entries=[])."""
    os.makedirs(dst_dir, exist_ok=True)

    if _is_rar(archive_path):
        cmd = [UNRAR_BIN, "x", "-y"]
        if password:
            cmd.append(f"-p{password}")
        else:
            cmd.append("-p-")
        cmd.append(archive_path)
        if entries:
            for e in entries:
                cmd.append(e.path)
        cmd.append(dst_dir + "/")
    else:
        cmd = [SZ_BIN, "x", archive_path, f"-o{dst_dir}", "-y"]
        if password:
            cmd.append(f"-p{password}")
        if entries:
            for e in entries:
                cmd.append(e.path)

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
        ok   = proc.returncode == 0
    except Exception:
        ok = False

    if callback:
        GLib.idle_add(callback, ok)

# ---------------------------------------------------------------------------
# Archive Browser Window
# ---------------------------------------------------------------------------

class ArchiveBrowserWindow(Adw.Window):
    __gtype_name__ = "ArchiveBrowserWindow"

    def __init__(self, archive_path):
        super().__init__()
        self.set_default_size(1000, 700)
        self.set_resizable(True)
        self.set_transient_for(_nautilus_window())

        self._archive_path = archive_path
        self._entries      = []
        self._password     = ""

        self.set_title(f"{T['title']} — {os.path.basename(archive_path)}")

        tv = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_decoration_layout(":close")
        title = Gtk.Label()
        title.set_markup(f"<b>{GLib.markup_escape_text(os.path.basename(archive_path))}</b>")
        title.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        title.set_max_width_chars(50)
        header.set_title_widget(title)
        tv.add_top_bar(header)

        # Layout principal : liste archive | panneau destination
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(460)
        paned.set_wide_handle(True)

        # --- Panneau gauche : contenu archive ---
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Barre de recherche
        search = Gtk.SearchEntry()
        search.set_placeholder_text("Filtrer…")
        search.set_margin_start(8)
        search.set_margin_end(8)
        search.set_margin_top(6)
        search.set_margin_bottom(6)
        search.connect("search-changed", self._on_search)
        left.append(search)
        left.append(Gtk.Separator())

        # Liste des fichiers
        self._store     = Gio.ListStore(item_type=ArchiveEntry)
        self._sel_model = Gtk.MultiSelection.new(self._store)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._factory_setup)
        factory.connect("bind",  self._factory_bind)

        self._lv = Gtk.ListView(model=self._sel_model, factory=factory)
        self._lv.set_vexpand(True)
        self._lv.add_css_class("navigation-sidebar")
        self._lv.connect("activate", self._on_activate)

        # Simple clic pour expand/collapse dossiers
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("pressed", self._on_click)
        self._lv.add_controller(click)

        # Drag source — DnD vers Nautilus
        drag_src = Gtk.DragSource()
        drag_src.set_actions(Gdk.DragAction.COPY)
        drag_src.connect("prepare",  self._on_drag_prepare)
        drag_src.connect("drag-begin", self._on_drag_begin)
        self._lv.add_controller(drag_src)

        scroll_l = Gtk.ScrolledWindow()
        scroll_l.set_vexpand(True)
        scroll_l.set_overlay_scrolling(False)
        scroll_l.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_l.set_child(self._lv)
        left.append(scroll_l)

        # Boutons extraction bas gauche
        btn_box = Gtk.Box(spacing=6)
        btn_box.set_margin_start(8)
        btn_box.set_margin_end(8)
        btn_box.set_margin_top(6)
        btn_box.set_margin_bottom(6)

        self._extract_all_btn = Gtk.Button(label=T["extract_all"])
        self._extract_all_btn.add_css_class("suggested-action")
        self._extract_all_btn.connect("clicked", self._on_extract_all)
        self._extract_sel_btn = Gtk.Button(label=T["extract_sel"])
        self._extract_sel_btn.connect("clicked", self._on_extract_sel)

        btn_box.append(self._extract_all_btn)
        btn_box.append(self._extract_sel_btn)
        left.append(Gtk.Separator())
        left.append(btn_box)

        paned.set_start_child(left)

        # --- Panneau droit : destination ---
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header destination
        dest_hdr = Gtk.Box(spacing=6)
        dest_hdr.set_margin_start(8)
        dest_hdr.set_margin_end(8)
        dest_hdr.set_margin_top(6)
        dest_hdr.set_margin_bottom(6)

        dest_lbl = Gtk.Label(label=T["dest_label"])
        dest_lbl.add_css_class("dim-label")

        self._dest_path = os.path.dirname(archive_path)
        self._dest_lbl  = Gtk.Label(label=self._dest_path)
        self._dest_lbl.set_hexpand(True)
        self._dest_lbl.set_halign(Gtk.Align.START)
        self._dest_lbl.set_ellipsize(Pango.EllipsizeMode.START)
        self._dest_lbl.add_css_class("dim-label")

        browse_btn = Gtk.Button(label=T["browse"])
        browse_btn.connect("clicked", self._on_browse_dest)

        dest_hdr.append(dest_lbl)
        dest_hdr.append(self._dest_lbl)
        dest_hdr.append(browse_btn)
        right.append(dest_hdr)
        right.append(Gtk.Separator())

        # Zone drop
        self._drop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._drop_box.set_vexpand(True)
        self._drop_box.set_valign(Gtk.Align.CENTER)
        self._drop_box.set_halign(Gtk.Align.CENTER)

        drop_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        drop_icon.set_pixel_size(64)
        drop_icon.add_css_class("dim-label")
        drop_hint = Gtk.Label(label=T["drop_hint"])
        drop_hint.add_css_class("dim-label")
        drop_hint.set_wrap(True)
        drop_hint.set_max_width_chars(30)
        drop_hint.set_justify(Gtk.Justification.CENTER)

        self._drop_box.append(drop_icon)
        self._drop_box.append(drop_hint)

        # Drop target
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", lambda *_: Gdk.DragAction.COPY)
        right.add_controller(drop_target)
        right.append(self._drop_box)

        # Barre de progression
        self._progress = Gtk.ProgressBar()
        self._progress.set_visible(False)
        self._progress.set_margin_start(12)
        self._progress.set_margin_end(12)
        self._progress.set_margin_bottom(8)
        right.append(self._progress)

        paned.set_end_child(right)

        tv.set_content(paned)
        self.set_content(tv)

        # CSS
        css = Gtk.CssProvider()
        css.load_from_data(b".bold { font-weight: bold; }")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Charger l'archive après affichage de la fenêtre
        self.connect("map", lambda *_: self._load_archive())

        # Escape — à la toute fin après tout le setup
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        sc = Gtk.ShortcutController()
        sc.set_scope(Gtk.ShortcutScope.MANAGED)
        sc.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("Escape"),
            Gtk.CallbackAction.new(lambda *_: self.close() or True)))
        self.add_controller(sc)

    # -- Chargement archive --------------------------------------------------


    def _load_archive(self):
        # Délai court pour laisser GTK afficher la fenêtre
        GLib.timeout_add(300, self._do_load)

    def _do_load(self):
        entries = _list_archive(self._archive_path)
        self._entries   = entries
        self._collapsed = set()  # chemins des dossiers collapsed
        # Collecter tous les dossiers et les collapser par défaut
        # sauf le niveau racine
        for e in entries:
            if e.is_dir:
                depth = e.path.rstrip("/").count("/")
                if depth > 0:
                    self._collapsed.add(e.path.rstrip("/"))
        self._refresh_store()
        return False

    def _refresh_store(self):
        """Reconstruit le store en respectant les collapsed."""
        self._store.remove_all()
        visible = self._get_visible_entries()
        self._pending = visible[:]
        self._load_page()

    def _get_visible_entries(self):
        """Retourne les entrées visibles selon l'état collapsed."""
        visible = []
        for e in self._entries:
            path  = e.path.rstrip("/")
            parts = path.split("/")
            # Vérifier si un ancêtre est collapsed
            hidden = False
            for i in range(len(parts) - 1):
                ancestor = "/".join(parts[:i+1])
                if ancestor in self._collapsed:
                    hidden = True
                    break
            if not hidden:
                visible.append(e)
        return visible

    def _load_page(self):
        if not hasattr(self, "_pending") or not self._pending:
            return False
        batch = self._pending[:150]
        self._pending = self._pending[150:]
        for e in batch:
            self._store.append(e)
        if self._pending:
            GLib.timeout_add(8, self._load_page)
        return False



    # -- Factory -------------------------------------------------------------

    def _factory_setup(self, factory, item):
        box  = Gtk.Box(spacing=6)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(2)
        box.set_margin_bottom(2)
        icon = Gtk.Image()
        icon.set_pixel_size(16)
        name = Gtk.Label()
        name.set_halign(Gtk.Align.START)
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        size = Gtk.Label()
        size.set_width_chars(10)
        size.set_halign(Gtk.Align.END)
        size.add_css_class("dim-label")
        date = Gtk.Label()
        date.set_width_chars(16)
        date.set_halign(Gtk.Align.END)
        date.add_css_class("dim-label")
        box.append(icon)
        box.append(name)
        box.append(size)
        box.append(date)
        item.set_child(box)

    def _factory_bind(self, factory, item):
        entry = item.get_item()
        box   = item.get_child()
        icon  = box.get_first_child()
        name  = icon.get_next_sibling()
        size  = name.get_next_sibling()
        date  = size.get_next_sibling()

        # Indentation selon profondeur
        box.set_margin_start(4 + entry.depth * 16)

        if entry.is_dir:
            path = entry.path.rstrip("/")
            collapsed = hasattr(self, "_collapsed") and path in self._collapsed
            icon.set_from_icon_name(
                "folder-symbolic" if collapsed else "folder-open-symbolic")
            name.add_css_class("bold")
            size.set_text("▶" if collapsed else "▼")
        else:
            # Icône selon extension
            ext   = os.path.splitext(entry.name)[1].lower()
            iname = "text-x-generic-symbolic"
            for check, ico in [
                ({".jpg",".jpeg",".png",".gif",".webp",".svg"}, "image-x-generic-symbolic"),
                ({".mp4",".mkv",".avi",".mov",".webm"},          "video-x-generic-symbolic"),
                ({".mp3",".flac",".ogg",".wav",".aac"},          "audio-x-generic-symbolic"),
                ({".pdf"},                                         "application-pdf-symbolic"),
                ({".zip",".7z",".rar",".tar",".gz"},             "package-x-generic-symbolic"),
                ({".py",".js",".sh",".c",".cpp",".rs"},          "text-x-script-symbolic"),
            ]:
                if ext in check:
                    iname = ico
                    break
            icon.set_from_icon_name(iname)
            name.remove_css_class("bold")
            size.set_text(_fmt_size(entry.size))

        name.set_text(entry.name)
        date.set_text(entry.date[:16] if entry.date else "")

    def _on_activate(self, lv, pos):
        """Double-clic — ouvrir fichier."""
        entry = self._store.get_item(pos)
        if not entry or entry.is_dir:
            return
        # Extraire et ouvrir le fichier
        tmp = tempfile.mkdtemp(prefix="archive_open_")
        _extract_entries(self._archive_path, [entry], tmp, self._password)
        extracted = os.path.join(tmp, os.path.basename(entry.path))
        if os.path.exists(extracted):
            try:
                Gio.AppInfo.launch_default_for_uri(
                    Gio.File.new_for_path(extracted).get_uri(), None)
            except Exception:
                pass

    def _on_click(self, gesture, n, x, y):
        """Simple clic — toggle collapse pour les dossiers."""
        # Trouver l'index de la ligne cliquée
        widget = gesture.get_widget()
        row    = widget.get_first_child()
        idx    = 0
        cumul  = 0
        while row:
            h = row.get_height()
            if cumul <= y < cumul + h:
                break
            cumul += h
            idx   += 1
            row    = row.get_next_sibling()

        if idx >= self._store.get_n_items():
            return
        entry = self._store.get_item(idx)
        if not entry or not entry.is_dir:
            return

        path = entry.path.rstrip("/")
        if not hasattr(self, "_collapsed"):
            self._collapsed = set()
        if path in self._collapsed:
            self._collapsed.discard(path)
        else:
            self._collapsed.add(path)
        self._refresh_store()

    # -- Recherche -----------------------------------------------------------

    def _on_search(self, entry):
        text = entry.get_text().lower().strip()
        self._store.remove_all()
        if not text:
            for e in self._entries:
                self._store.append(e)
        else:
            for e in self._entries:
                if text in e.name.lower() or text in e.path.lower():
                    self._store.append(e)

    # -- DnD -----------------------------------------------------------------

    def _on_drag_prepare(self, drag_src, x, y):
        """Prépare les fichiers à extraire dans un dossier tmp pour le DnD."""
        selected = self._get_selected()
        if not selected:
            return None

        # Extraire dans un dossier temp
        tmp = tempfile.mkdtemp(prefix="archive_browser_")
        _extract_entries(self._archive_path, selected, tmp, self._password)

        # Construire la liste des fichiers extraits
        files = []
        for e in selected:
            extracted = os.path.join(tmp, os.path.basename(e.path.rstrip("/")))
            if os.path.exists(extracted):
                files.append(Gio.File.new_for_path(extracted))

        if not files:
            return None

        file_list = Gdk.FileList.new_from_list(files)
        return Gdk.ContentProvider.new_for_value(file_list)

    def _on_drag_begin(self, drag_src, drag):
        selected = self._get_selected()
        if selected:
            icon = Gtk.DragIcon.get_for_drag(drag)
            img  = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
            img.set_pixel_size(32)
            icon.set_child(img)

    def _on_drop(self, target, value, x, y):
        """Reçoit un drop de fichiers → les copie dans la destination."""
        if isinstance(value, Gdk.FileList):
            for gfile in value.get_files():
                dst = os.path.join(self._dest_path, os.path.basename(gfile.get_path()))
                try:
                    if os.path.isdir(gfile.get_path()):
                        shutil.copytree(gfile.get_path(), dst)
                    else:
                        shutil.copy2(gfile.get_path(), dst)
                except Exception as e:
                    self._show_error(str(e))
        return True

    # -- Extraction ----------------------------------------------------------

    def _on_extract_all(self, _):
        self._do_extract([])

    def _on_extract_sel(self, _):
        selected = self._get_selected()
        if not selected:
            dlg = Adw.MessageDialog(transient_for=self,
                                    heading=T["no_selection"])
            dlg.add_response("ok", T["ok"])
            dlg.present()
            return
        self._do_extract(selected)

    def _do_extract(self, entries):
        self._progress.set_visible(True)
        self._progress.pulse()
        self._extract_all_btn.set_sensitive(False)
        self._extract_sel_btn.set_sensitive(False)

        # Pulse pendant l'extraction
        def _pulse():
            if self._progress.get_visible():
                self._progress.pulse()
                return True
            return False
        GLib.timeout_add(100, _pulse)

        def _work():
            _extract_entries(
                self._archive_path, entries,
                self._dest_path, self._password,
                callback=self._on_extract_done)

        threading.Thread(target=_work, daemon=True).start()

    def _on_extract_done(self, ok):
        self._progress.set_visible(False)
        self._extract_all_btn.set_sensitive(True)
        self._extract_sel_btn.set_sensitive(True)
        if ok:
            # Ouvrir le dossier destination dans Nautilus
            try:
                Gio.AppInfo.launch_default_for_uri(
                    Gio.File.new_for_path(self._dest_path).get_uri(), None)
            except Exception:
                pass
        return False

    # -- Destination ---------------------------------------------------------

    def _on_browse_dest(self, _):
        dlg = Gtk.FileDialog()
        dlg.set_initial_folder(Gio.File.new_for_path(self._dest_path))
        dlg.select_folder(self, None, self._on_dest_selected)

    def _on_dest_selected(self, dlg, result):
        try:
            folder = dlg.select_folder_finish(result)
            if folder:
                self._dest_path = folder.get_path()
                self._dest_lbl.set_text(self._dest_path)
        except Exception:
            pass

    # -- Helpers -------------------------------------------------------------

    def _get_selected(self):
        entries  = []
        sel_bits = self._sel_model.get_selection()
        for i in range(self._store.get_n_items()):
            if sel_bits.contains(i):
                entries.append(self._store.get_item(i))
        return entries

    def _show_error(self, msg):
        dlg = Adw.MessageDialog(transient_for=self,
                                heading=T["err_title"], body=msg)
        dlg.add_response("ok", T["ok"])
        dlg.present()

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
            ArchiveBrowserWindow(archives[0].get_location().get_path()).present())
        return [item]

    def get_background_items(self, folder):
        return []
