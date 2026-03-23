#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Dual Panel – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), python3-gi, gir1.2-adw-1
# INSTALL:
#   cp dual-panel.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import re
import shutil
import subprocess
import locale
import stat
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gdk, Gio, GLib, Pango, Nautilus

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("de"):
    T = {
        "menu_label":    "Im Dual Panel Modus öffnen",
        "title":         "Dual Panel",
        "copy":          "Kopieren →",
        "copy_left":     "← Kopieren",
        "move":          "Verschieben →",
        "move_left":     "← Verschieben",
        "new_folder":    "Neuer Ordner",
        "new_file":      "Neue Datei",
        "rename":        "Umbenennen",
        "delete":        "Löschen",
        "refresh":       "Neu Laden",
        "go_up":         "Vorheriger Ordner",
        "col_name":      "Name",
        "col_size":      "Größe",
        "col_date":      "Verändert",
        "col_perms":     "Eigenschaften",
        "confirm_del":   "{name} löschen?",
        "confirm_del2":  "{n} Objekte löschen?",
        "confirm_move":  "{name} nach {dst} verschieben?",
        "confirm_move2": "{n} Objekte nach {dst} verschieben?",
        "err_title":     "Fehler",
        "new_folder_name": "Neuer Ordner",
        "new_file_name":   "Neu.txt",
        "enter_name":    "Name:",
        "cancel":        "Abbrechen",
        "ok":            "OK",
        "delete_ok":     "Löschen",
        "open_terminal": "In Terminal öffnen",
        "sidebar_favorites": "Favoriten",
        "toast_copy_done":  "Kopieren abgeschlossen",
        "toast_move_done":  "Verschieben abgeschlossen",
        "toast_error":      "Fehler: {msg}",
        "sidebar_trash":     "Papierkorb",
        "sidebar_bookmarks": "Lesezeichen",
        "sidebar_places":    "Orte",
        "delete_perm":   "Dauerhaft Löschen",
        "confirm_perm":  "{name} wirklich dauerhaft löschen? Das kann nicht rückgängig gemacht werden!",
        "confirm_perm2": "{n} Objekte wirklich dauerhaft löschen? Das kann nicht rückgängig gemacht werden!",
        "context_open":        "Öffnen",
        "context_copy":        "In anderes Panel kopieren",
        "context_move":        "In anderes Panel verschieben",
        "context_rename":      "Umbenennen",
        "context_delete":      "In Papierkorb verschieben",
        "context_delete_perm": "Dauerhaft Löschen",
        "context_new_folder":  "Neuer Ordner",
        "context_new_file":    "Neue Datei",
        "context_terminal":    "In Terminal öffnen",
    }

elif _lang.startswith("fr"):
    T = {
        "menu_label":    "Ouvrir en double panneau",
        "title":         "Double Panneau",
        "copy":          "Copier →",
        "copy_left":     "← Copier",
        "move":          "Déplacer →",
        "move_left":     "← Déplacer",
        "new_folder":    "Nouveau dossier",
        "new_file":      "Nouveau fichier",
        "rename":        "Renommer",
        "delete":        "Supprimer",
        "refresh":       "Actualiser",
        "go_up":         "Dossier parent",
        "col_name":      "Nom",
        "col_size":      "Taille",
        "col_date":      "Modifié",
        "col_perms":     "Droits",
        "confirm_del":   "Supprimer {name} ?",
        "confirm_del2":  "Supprimer {n} éléments ?",
        "confirm_move":  "Déplacer {name} vers {dst} ?",
        "confirm_move2": "Déplacer {n} éléments vers {dst} ?",
        "err_title":     "Erreur",
        "new_folder_name": "Nouveau dossier",
        "new_file_name":   "nouveau_fichier.txt",
        "enter_name":    "Nom :",
        "cancel":        "Annuler",
        "ok":            "OK",
        "delete_ok":     "Supprimer",
        "open_terminal":  "Terminal ici",
        "sidebar_favorites": "Favoris",
        "toast_copy_done":  "Copie terminée",
        "toast_move_done":  "Déplacement terminé",
        "toast_error":      "Erreur : {msg}",
        "sidebar_trash":     "Corbeille",
        "sidebar_bookmarks": "Signets",
        "sidebar_places":    "Emplacements",
        "delete_perm":    "Supprimer définitivement",
        "confirm_perm":   "Supprimer DÉFINITIVEMENT {name} ? Cette action est irréversible.",
        "confirm_perm2":  "Supprimer DÉFINITIVEMENT {n} éléments ? Cette action est irréversible.",
        "context_open":   "Ouvrir",
        "context_copy":   "Copier vers l'autre panneau",
        "context_move":   "Déplacer vers l'autre panneau",
        "context_rename": "Renommer",
        "context_delete": "Corbeille",
        "context_delete_perm": "Supprimer définitivement",
        "context_new_folder":  "Nouveau dossier",
        "context_new_file":    "Nouveau fichier",
        "context_terminal":    "Terminal ici",
    }
else:
    T = {
        "menu_label":    "Open in dual panel",
        "title":         "Dual Panel",
        "copy":          "Copy →",
        "copy_left":     "← Copy",
        "move":          "Move →",
        "move_left":     "← Move",
        "new_folder":    "New folder",
        "new_file":      "New file",
        "rename":        "Rename",
        "delete":        "Delete",
        "refresh":       "Refresh",
        "go_up":         "Parent folder",
        "col_name":      "Name",
        "col_size":      "Size",
        "col_date":      "Modified",
        "col_perms":     "Permissions",
        "confirm_del":   "Delete {name}?",
        "confirm_del2":  "Delete {n} items?",
        "confirm_move":  "Move {name} to {dst}?",
        "confirm_move2": "Move {n} items to {dst}?",
        "err_title":     "Error",
        "new_folder_name": "New folder",
        "new_file_name":   "new_file.txt",
        "enter_name":    "Name:",
        "cancel":        "Cancel",
        "ok":            "OK",
        "delete_ok":     "Delete",
        "open_terminal":  "Terminal here",
        "sidebar_favorites": "Favorites",
        "toast_copy_done":  "Copy complete",
        "toast_move_done":  "Move complete",
        "toast_error":      "Error: {msg}",
        "sidebar_trash":     "Trash",
        "sidebar_bookmarks": "Bookmarks",
        "sidebar_places":    "Places",
        "delete_perm":    "Delete permanently",
        "confirm_perm":   "Permanently DELETE {name}? This cannot be undone.",
        "confirm_perm2":  "Permanently DELETE {n} items? This cannot be undone.",
        "context_open":   "Open",
        "context_copy":   "Copy to other panel",
        "context_move":   "Move to other panel",
        "context_rename": "Rename",
        "context_delete": "Move to trash",
        "context_delete_perm": "Delete permanently",
        "context_new_folder":  "New folder",
        "context_new_file":    "New file",
        "context_terminal":    "Terminal here",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    win = app.get_active_window()
    return win or (app.get_windows()[0] if app.get_windows() else None)

def _fmt_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def _fmt_date(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))

def _fmt_perms(mode):
    bits = ""
    for who in [(stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
                (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
                (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)]:
        bits += "r" if mode & who[0] else "-"
        bits += "w" if mode & who[1] else "-"
        bits += "x" if mode & who[2] else "-"
    return bits

def _icon_for(path, is_dir):
    """Retourne l'icône régulière du thème pour un fichier ou dossier."""
    try:
        if is_dir:
            # Dossier spécial (Bureau, Musique...) ou dossier générique
            gfile    = Gio.File.new_for_path(path)
            info     = gfile.query_info("standard::icon", 0, None)
            gicon    = info.get_icon()
            if gicon:
                theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
                names = gicon.get_names() if hasattr(gicon, "get_names") else []
                for name in names:
                    if theme.has_icon(name):
                        return name
            return "folder"
        else:
            # Fichier — détection via Gio content type
            gfile = Gio.File.new_for_path(path)
            info  = gfile.query_info("standard::icon,standard::content-type", 0, None)
            gicon = info.get_icon()
            if gicon:
                theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
                names = gicon.get_names() if hasattr(gicon, "get_names") else []
                for name in names:
                    if theme.has_icon(name):
                        return name
            return "text-x-generic"
    except Exception:
        return "folder" if is_dir else "text-x-generic"


# ---------------------------------------------------------------------------
# File entry model
# ---------------------------------------------------------------------------

class FileEntry(GObject.Object):
    __gtype_name__ = "DualPanelFileEntry"

    def __init__(self, path):
        super().__init__()
        self.path    = path
        self.name    = os.path.basename(path)
        self.is_dir  = os.path.isdir(path)
        try:
            s = os.stat(path)
            self.size  = s.st_size
            self.mtime = s.st_mtime
            self.mode  = s.st_mode
        except OSError:
            self.size = self.mtime = self.mode = 0

    @property
    def size_str(self):
        return "—" if self.is_dir else _fmt_size(self.size)

    @property
    def date_str(self):
        return _fmt_date(self.mtime) if self.mtime else ""

    @property
    def perms_str(self):
        return _fmt_perms(self.mode) if self.mode else ""


# ---------------------------------------------------------------------------
# Panel widget
# ---------------------------------------------------------------------------

class FilePanel(Gtk.Box):
    __gtype_name__ = "DualPanelFilePanel"

    def __init__(self, start_path: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._path     = start_path
        self._entries  = []
        self._other    = None   # référence à l'autre panneau (setté après)
        self._sort_col = "name"
        self._sort_asc = True

        self._build()
        self.navigate(start_path)

    def set_other_panel(self, other):
        self._other = other

    # -- Construction --------------------------------------------------------

    def _build(self):
        # Barre adresse
        addr_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        addr_bar.set_margin_top(4)
        addr_bar.set_margin_bottom(4)
        addr_bar.set_margin_start(6)
        addr_bar.set_margin_end(6)

        up_btn = Gtk.Button(icon_name="go-up-symbolic")
        up_btn.set_tooltip_text(T["go_up"])
        up_btn.connect("clicked", lambda _: self.navigate(os.path.dirname(self._path)))
        addr_bar.append(up_btn)

        self._addr_entry = Gtk.Entry()
        self._addr_entry.set_hexpand(True)
        self._addr_entry.connect("activate", self._on_addr_activate)
        addr_bar.append(self._addr_entry)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(T["refresh"])
        refresh_btn.connect("clicked", lambda _: self.refresh())
        addr_bar.append(refresh_btn)

        term_btn = Gtk.Button(icon_name="utilities-terminal-symbolic")
        term_btn.set_tooltip_text(T["open_terminal"])
        term_btn.connect("clicked", self._open_terminal)
        addr_bar.append(term_btn)

        self.append(addr_bar)

        # Séparateur
        self.append(Gtk.Separator())

        # Liste
        self._store     = Gio.ListStore(item_type=FileEntry)
        self._sort_model = Gtk.SortListModel.new(self._store, None)
        self._selection  = Gtk.MultiSelection.new(self._sort_model)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup",  self._factory_setup)
        factory.connect("bind",   self._factory_bind)

        # CSS pour la corbeille rouge
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            .red-icon { color: #e01b24; }
            .destructive-trash:hover { background: alpha(#e01b24, 0.15); }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        col_view = Gtk.ColumnView(model=self._selection)
        col_view.set_show_column_separators(True)
        col_view.set_single_click_activate(False)
        col_view.connect("activate", self._on_activate)
        self._col_view = col_view

        # Colonnes
        self._add_column(col_view, T["col_name"],  "name",  260, self._factory_name_setup,  self._factory_name_bind, expand=True)
        self._add_column(col_view, T["col_size"],  "size",  90,  self._factory_size_setup,  self._factory_size_bind)
        self._add_column(col_view, T["col_date"],  "mtime", 140, self._factory_date_setup,  self._factory_date_bind)
        self._add_column(col_view, T["col_perms"], "perms", 105,  self._factory_perms_setup, self._factory_perms_bind)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(col_view)
        self.append(scroll)

        # Actions bar
        self._build_actions()

        # Drag & drop
        self._setup_dnd()

        # Menu contextuel + raccourcis
        self._setup_context_menu()
        self._setup_keyboard()

    def _add_column(self, cv, title, sort_key, width, setup_fn, bind_fn, expand=False):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", setup_fn)
        factory.connect("bind",  bind_fn)
        col = Gtk.ColumnViewColumn(title=title, factory=factory)
        col.set_fixed_width(width)
        col.set_resizable(True)
        col.set_expand(expand)
        col.sort_key = sort_key
        header_btn = Gtk.Button(label=title)
        header_btn.connect("clicked", self._on_sort_click, sort_key)
        cv.append_column(col)

    def _build_actions(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bar.set_margin_top(4)
        bar.set_margin_bottom(4)
        bar.set_margin_start(6)
        bar.set_margin_end(6)

        def add_btn(label, icon, tooltip, cb):
            b = Gtk.Button(icon_name=icon)
            b.set_tooltip_text(tooltip)
            b.connect("clicked", cb)
            bar.append(b)
            return b

        add_btn("", "folder-new-symbolic",       T["new_folder"], self._on_new_folder)
        add_btn("", "document-new-symbolic",     T["new_file"],   self._on_new_file)
        add_btn("", "document-edit-symbolic",    T["rename"],     self._on_rename)
        add_btn("", "user-trash-symbolic",       T["delete"],     self._on_delete)
        # Bouton corbeille rouge pour suppression définitive
        perm_btn = Gtk.Button()
        perm_btn.set_tooltip_text(T["delete_perm"])
        perm_img = Gtk.Image.new_from_icon_name("user-trash-symbolic")
        perm_img.add_css_class("red-icon")
        perm_btn.set_child(perm_img)
        perm_btn.add_css_class("destructive-trash")
        perm_btn.connect("clicked", self._on_delete_perm)
        bar.append(perm_btn)

        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        self._copy_btn = Gtk.Button(label=T["copy"])
        self._copy_btn.add_css_class("suggested-action")
        self._copy_btn.connect("clicked", self._on_copy)
        bar.append(self._copy_btn)

        self._move_btn = Gtk.Button(label=T["move"])
        self._move_btn.connect("clicked", self._on_move)
        bar.append(self._move_btn)

        self.append(Gtk.Separator())
        self.append(bar)

    # -- Column factories ----------------------------------------------------

    def _factory_name_setup(self, factory, item):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(4)
        icon = Gtk.Image()
        icon.set_icon_size(Gtk.IconSize.NORMAL)
        lbl  = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.set_hexpand(True)
        box.append(icon)
        box.append(lbl)
        item.set_child(box)

    def _factory_name_bind(self, factory, item):
        entry      = item.get_item()
        box        = item.get_child()
        icon       = box.get_first_child()
        lbl        = icon.get_next_sibling()
        icon_name  = _icon_for(entry.path, entry.is_dir)

        # Chercher l'icône colorée (regular) dans le thème
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        if theme.has_icon(icon_name):
            paintable = theme.lookup_icon(
                icon_name, None, 24, 1,
                Gtk.TextDirection.NONE,
                Gtk.IconLookupFlags.FORCE_REGULAR,
            )
            icon.set_from_paintable(paintable)
        else:
            icon.set_from_icon_name(icon_name)

        lbl.set_text(entry.name)
        if entry.is_dir:
            lbl.add_css_class("bold")

    def _factory_size_setup(self, factory, item):
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.END)
        lbl.set_margin_end(8)
        item.set_child(lbl)

    def _factory_size_bind(self, factory, item):
        item.get_child().set_text(item.get_item().size_str)

    def _factory_date_setup(self, factory, item):
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        item.set_child(lbl)

    def _factory_date_bind(self, factory, item):
        item.get_child().set_text(item.get_item().date_str)

    def _factory_perms_setup(self, factory, item):
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        lbl.add_css_class("monospace")
        item.set_child(lbl)

    def _factory_perms_bind(self, factory, item):
        item.get_child().set_text(item.get_item().perms_str)

    def _factory_setup(self, f, i): pass
    def _factory_bind(self, f, i):  pass

    # -- Navigation ----------------------------------------------------------

    def navigate(self, path: str):
        if not os.path.isdir(path):
            return
        self._path = path
        self._addr_entry.set_text(path)
        self.refresh()

    def refresh(self):
        import threading
        path = self._path
        self._store.remove_all()

        # Spinner pendant le chargement
        if not hasattr(self, "_spinner"):
            self._spinner = Gtk.Spinner()
            self._spinner.set_halign(Gtk.Align.CENTER)
            self._spinner.set_valign(Gtk.Align.CENTER)
            self._spinner.set_size_request(32, 32)
        self._spinner.start()
        # Insérer le spinner comme overlay sur le scroll
        if hasattr(self, "_scroll") and self._spinner.get_parent() is None:
            self._overlay = Gtk.Overlay()
            child = self._scroll.get_child()
            self._scroll.set_child(None)
            self._overlay.set_child(child)
            self._overlay.add_overlay(self._spinner)
            self._scroll.set_child(self._overlay)

        def _work():
            entries = []
            try:
                items = sorted(os.scandir(path), key=lambda e: (
                    not e.is_dir(follow_symlinks=False),
                    e.name.startswith("."),
                    e.name.lower()
                ))
                for it in items:
                    entries.append(FileEntry(it.path))
            except PermissionError:
                pass
            GLib.idle_add(self._load_entries, path, entries)

        threading.Thread(target=_work, daemon=True).start()

    def _load_entries(self, path, entries):
        if path != self._path:
            return False
        self._pending = entries[:]
        self._load_page()
        return False

    def _load_page(self):
        if not hasattr(self, "_pending") or not self._pending:
            # Tout chargé — arrêter le spinner
            if hasattr(self, "_spinner"):
                self._spinner.stop()
            return
        batch = self._pending[:100]
        self._pending = self._pending[100:]
        n = self._store.get_n_items()
        self._store.splice(n, 0, batch)
        if self._pending:
            GLib.timeout_add(8, self._load_page)
        else:
            if hasattr(self, "_spinner"):
                self._spinner.stop()

    def _apply_sort(self):
        def compare(a, b, _):
            # Ordre Nautilus :
            # 1. Dossiers normaux  2. Dossiers cachés
            # 3. Fichiers normaux  4. Fichiers cachés
            a_hidden = a.name.startswith(".")
            b_hidden = b.name.startswith(".")

            # Groupe de priorité : dossier normal=0, dossier caché=1,
            #                      fichier normal=2, fichier caché=3
            def group(e, hidden):
                if e.is_dir:
                    return 1 if hidden else 0
                return 3 if hidden else 2

            ga, gb = group(a, a_hidden), group(b, b_hidden)
            if ga != gb:
                # Le groupement ne s'inverse pas avec le sens du tri
                return -1 if ga < gb else 1

            va = getattr(a, self._sort_col, a.name)
            vb = getattr(b, self._sort_col, b.name)
            if isinstance(va, str):
                # Pour les cachés, ignorer le "." dans la comparaison alpha
                va = va.lstrip(".").lower()
                vb = vb.lstrip(".").lower()
            if va < vb:
                result = -1
            elif va > vb:
                result = 1
            else:
                result = 0
            return result if self._sort_asc else -result

        sorter = Gtk.CustomSorter.new(compare)
        self._sort_model.set_sorter(sorter)

    def _on_addr_activate(self, entry):
        self.navigate(entry.get_text().strip())

    def _on_activate(self, col_view, pos):
        entry = self._sort_model.get_item(pos)
        if entry and entry.is_dir:
            self.navigate(entry.path)
        elif entry:
            try:
                Gio.AppInfo.launch_default_for_uri(
                    f"file://{entry.path}", None)
            except Exception:
                pass

    def _on_sort_click(self, btn, sort_key):
        if self._sort_col == sort_key:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = sort_key
            self._sort_asc = True
        self._apply_sort()

    # -- Sélection -----------------------------------------------------------

    def get_selected_entries(self):
        result = []
        bs = self._selection.get_selection()
        for i in range(self._sort_model.get_n_items()):
            if bs.contains(i):
                result.append(self._sort_model.get_item(i))
        return result

    # -- Actions -------------------------------------------------------------

    def _on_copy(self, _btn):
        if not self._other:
            return
        self._do_transfer(self._other._path, move=False)

    def _on_move(self, _btn):
        if not self._other:
            return
        self._do_transfer(self._other._path, move=True)

    def _do_transfer(self, dst_dir: str, move: bool):
        selected = self.get_selected_entries()
        if not selected:
            return
        verb = T["move"] if move else T["copy"]
        n    = len(selected)
        if n == 1:
            msg = (T["confirm_move"] if move else T["confirm_del"]).format(
                name=selected[0].name, dst=dst_dir)
        else:
            msg = (T["confirm_move2"] if move else T["confirm_del2"]).format(
                n=n, dst=dst_dir)
        # Pas de confirm pour copy, seulement pour move
        if move:
            self._confirm(msg, lambda: self._exec_transfer(selected, dst_dir, move))
        else:
            self._exec_transfer(selected, dst_dir, move)

    def _exec_transfer(self, entries, dst_dir, move):
        import threading
        win = self._get_window()
        if win:
            GLib.idle_add(win.start_progress)

        def _work():
            total = len(entries)
            for i, e in enumerate(entries):
                dst = os.path.join(dst_dir, e.name)
                try:
                    if move:
                        # Move : rsync + suppression source
                        self._rsync(e.path, dst_dir,
                            lambda f: GLib.idle_add(win.set_progress,
                                (i + f) / total) if win else None)
                        shutil.rmtree(e.path) if e.is_dir else os.remove(e.path)
                    else:
                        self._rsync(e.path, dst_dir,
                            lambda f: GLib.idle_add(win.set_progress,
                                (i + f) / total) if win else None)
                except Exception as ex:
                    GLib.idle_add(self._error, str(ex))
                    break
            def _done():
                self.refresh()
                if self._other:
                    self._other.refresh()
                if win:
                    win.stop_progress()
                    win.show_toast(
                        T["toast_move_done"] if move else T["toast_copy_done"])
            GLib.idle_add(_done)

        threading.Thread(target=_work, daemon=True).start()

    def _rsync(self, src, dst_dir, progress_cb=None):
        """Copie via rsync avec progression."""
        cmd = ["rsync", "-a", "--progress", src, dst_dir + "/"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        for line in proc.stdout:
            # rsync --progress: "  1,234,567  45%   12.34MB/s    0:00:05"
            m = re.search("([0-9]+)%", line)
            if m and progress_cb:
                progress_cb(int(m.group(1)) / 100.0)
        proc.wait()
        if proc.returncode != 0:
            raise Exception(proc.stderr.read())

    def _get_window(self):
        """Remonte au DualPanelWindow parent."""
        w = self.get_root()
        from gi.repository import Adw as _Adw
        if isinstance(w, _Adw.Window):
            return w
        return None

    def _on_delete(self, _btn):
        selected = self.get_selected_entries()
        if not selected:
            return
        n   = len(selected)
        msg = T["confirm_del2"].format(n=n) if n > 1 else \
              T["confirm_del"].format(name=selected[0].name)
        self._confirm(msg, lambda: self._exec_delete(selected), danger=True)

    def _exec_delete(self, entries):
        for e in entries:
            try:
                trash = Gio.File.new_for_path(e.path)
                trash.trash(None)
            except Exception as ex:
                self._error(str(ex))
                return
        self.refresh()

    def _on_delete_perm(self, _btn):
        selected = self.get_selected_entries()
        if not selected:
            return
        n   = len(selected)
        msg = T["confirm_perm2"].format(n=n) if n > 1 else               T["confirm_perm"].format(name=selected[0].name)
        self._confirm(msg, lambda: self._exec_delete_perm(selected), danger=True)

    def _exec_delete_perm(self, entries):
        for e in entries:
            try:
                if e.is_dir:
                    shutil.rmtree(e.path)
                else:
                    os.remove(e.path)
            except Exception as ex:
                self._error(str(ex))
                return
        self.refresh()

    def _on_new_folder(self, _btn):
        self._ask_name(T["new_folder_name"], lambda name: self._exec_mkdir(name))

    def _exec_mkdir(self, name):
        try:
            os.makedirs(os.path.join(self._path, name), exist_ok=True)
            self.refresh()
        except Exception as ex:
            self._error(str(ex))

    def _on_new_file(self, _btn):
        self._ask_name(T["new_file_name"], lambda name: self._exec_touch(name))

    def _exec_touch(self, name):
        try:
            open(os.path.join(self._path, name), "a").close()
            self.refresh()
        except Exception as ex:
            self._error(str(ex))

    def _on_rename(self, _btn):
        selected = self.get_selected_entries()
        if len(selected) != 1:
            return
        self._ask_name(selected[0].name,
                       lambda name: self._exec_rename(selected[0].path, name))

    def _exec_rename(self, old_path, new_name):
        try:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            os.rename(old_path, new_path)
            self.refresh()
        except Exception as ex:
            self._error(str(ex))

    def _open_terminal(self, _btn):
        for term in ["gnome-terminal", "xterm", "konsole", "xfce4-terminal"]:
            if shutil.which(term):
                subprocess.Popen([term], cwd=self._path)
                return

    # -- Menu contextuel clic droit -----------------------------------------

    def _build_context_menu(self):
        menu = Gio.Menu()
        selected = self.get_selected_entries()

        if len(selected) == 1 and not selected[0].is_dir:
            menu.append(T["context_open"],   "panel.open-file")
        if selected:
            menu.append(T["context_copy"],   "panel.copy-other")
            menu.append(T["context_move"],   "panel.move-other")
        if len(selected) == 1:
            menu.append(T["context_rename"], "panel.rename")
        if selected:
            menu.append(T["context_delete"],      "panel.delete-trash")
            menu.append(T["context_delete_perm"],  "panel.delete-perm")
        menu.append(T["context_new_folder"], "panel.new-folder")
        menu.append(T["context_new_file"],   "panel.new-file")
        menu.append(T["context_terminal"],   "panel.terminal")
        return menu

    def _setup_context_menu(self):
        # Actions du groupe "panel"
        ag = Gio.SimpleActionGroup()
        actions = {
            "open-file":    lambda *_: self._open_selected(),
            "copy-other":   lambda *_: self._on_copy(None),
            "move-other":   lambda *_: self._on_move(None),
            "rename":       lambda *_: self._on_rename(None),
            "delete-trash": lambda *_: self._on_delete(None),
            "delete-perm":  lambda *_: self._on_delete_perm(None),
            "new-folder":   lambda *_: self._on_new_folder(None),
            "new-file":     lambda *_: self._on_new_file(None),
            "terminal":     lambda *_: self._open_terminal(None),
        }
        for name, cb in actions.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            ag.add_action(a)
        self._col_view.insert_action_group("panel", ag)

        # Geste clic droit
        gesture = Gtk.GestureClick()
        gesture.set_button(3)
        gesture.connect("pressed", self._on_right_click)
        self._col_view.add_controller(gesture)

    def _on_right_click(self, gesture, n, x, y):
        menu_model = self._build_context_menu()
        popover    = Gtk.PopoverMenu.new_from_model(menu_model)
        popover.set_parent(self._col_view)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    def _open_selected(self):
        selected = self.get_selected_entries()
        if len(selected) == 1 and not selected[0].is_dir:
            try:
                Gio.AppInfo.launch_default_for_uri(
                    f"file://{selected[0].path}", None)
            except Exception:
                pass

    # -- Raccourcis clavier --------------------------------------------------

    def _setup_keyboard(self):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.LOCAL)

        def add(trigger_str, cb):
            trigger = Gtk.ShortcutTrigger.parse_string(trigger_str)
            action  = Gtk.CallbackAction.new(lambda *a: cb() or True)
            ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))

        add("Delete",         lambda: self._on_delete(None))          # Suppr → corbeille
        add("<Shift>Delete",  lambda: self._on_delete_perm(None))     # Shift+Suppr → définitif
        add("F2",             lambda: self._on_rename(None))
        add("<Ctrl>c",        lambda: self._on_copy(None))
        add("<Ctrl>x",        lambda: self._on_move(None))
        add("<Ctrl>n",        lambda: self._on_new_folder(None))
        add("BackSpace",      lambda: self.navigate(os.path.dirname(self._path)))

        self._col_view.add_controller(ctrl)
        self._col_view.set_focusable(True)

    # -- DnD -----------------------------------------------------------------

    def _setup_dnd(self):
        # Source drag
        drag_src = Gtk.DragSource()
        drag_src.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        drag_src.connect("prepare", self._on_drag_prepare)
        self._col_view.add_controller(drag_src)

        # Drop target
        drop_tgt = Gtk.DropTarget.new(GObject.TYPE_STRING,
                                      Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        drop_tgt.connect("drop", self._on_drop)
        self._col_view.add_controller(drop_tgt)

    def _on_drag_prepare(self, src, x, y):
        selected = self.get_selected_entries()
        if not selected:
            return None
        paths = "\n".join(e.path for e in selected)
        val   = GObject.Value(GObject.TYPE_STRING, paths)
        return Gdk.ContentProvider.new_for_value(val)

    def _on_drop(self, tgt, value, x, y):
        if not isinstance(value, str):
            return False
        paths = [p.strip() for p in value.splitlines() if p.strip()]
        for path in paths:
            try:
                dst = os.path.join(self._path, os.path.basename(path))
                shutil.copy2(path, dst) if os.path.isfile(path) else \
                    shutil.copytree(path, dst, dirs_exist_ok=True)
            except Exception as ex:
                self._error(str(ex))
                return False
        self.refresh()
        return True

    # -- Dialogs helpers -----------------------------------------------------

    def _get_parent_win(self):
        w = self.get_root()
        return w if isinstance(w, Gtk.Window) else _nautilus_window()

    def _confirm(self, msg, on_ok, danger=False):
        dlg = Adw.Window(title=T["title"])
        dlg.set_modal(True)
        dlg.set_transient_for(self._get_parent_win())
        dlg.set_default_size(360, -1)

        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)

        lbl = Gtk.Label(label=msg)
        lbl.set_wrap(True)
        box.append(lbl)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel = Gtk.Button(label=T["cancel"])
        cancel.connect("clicked", lambda _: dlg.destroy())
        btn_box.append(cancel)

        ok_label = T["delete_ok"] if danger else T["ok"]
        ok_btn = Gtk.Button(label=ok_label)
        ok_btn.add_css_class("destructive-action" if danger else "suggested-action")

        def on_ok_click(_):
            dlg.destroy()
            on_ok()

        ok_btn.connect("clicked", on_ok_click)
        btn_box.append(ok_btn)
        box.append(btn_box)

        tv.set_content(box)
        dlg.set_content(tv)
        dlg.present()

    def _ask_name(self, default: str, on_ok):
        dlg = Adw.Window(title=T["title"])
        dlg.set_modal(True)
        dlg.set_transient_for(self._get_parent_win())
        dlg.set_default_size(340, -1)

        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        box.append(Gtk.Label(label=T["enter_name"]))
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.select_region(0, -1)
        box.append(entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel = Gtk.Button(label=T["cancel"])
        cancel.connect("clicked", lambda _: dlg.destroy())
        btn_box.append(cancel)

        ok_btn = Gtk.Button(label=T["ok"])
        ok_btn.add_css_class("suggested-action")

        def do_ok(_):
            name = entry.get_text().strip()
            if name:
                dlg.destroy()
                on_ok(name)

        ok_btn.connect("clicked", do_ok)
        entry.connect("activate", do_ok)
        btn_box.append(ok_btn)
        box.append(btn_box)

        tv.set_content(box)
        dlg.set_content(tv)
        dlg.present()
        entry.grab_focus()

    def _error(self, msg: str):
        Gtk.AlertDialog(message=f"{T['err_title']}: {msg}").show(
            self._get_parent_win())


# ---------------------------------------------------------------------------
# Main dual-panel window
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sidebar (bookmarks GIO comme Nautilus)
# ---------------------------------------------------------------------------

class SidebarPanel(Gtk.Box):
    __gtype_name__ = "DualPanelSidebar"

    def __init__(self, on_select):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(180, -1)
        self.set_vexpand(True)
        self._on_select = on_select

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_overlay_scrolling(False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll.set_child(self._box)
        self.append(scroll)

        self._populate()

    def _btn(self, label, path, icon_name=None):
        row = Gtk.Button()
        row.set_has_frame(False)
        row.add_css_class("flat")

        inner = Gtk.Box(spacing=8)
        inner.set_margin_start(8)
        inner.set_margin_end(8)
        inner.set_margin_top(4)
        inner.set_margin_bottom(4)

        icon = Gtk.Image()
        icon.set_pixel_size(16)
        if icon_name:
            paint = None
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            if theme.has_icon(icon_name):
                paint = theme.lookup_icon(icon_name, None, 16, 1,
                    Gtk.TextDirection.LTR, Gtk.IconLookupFlags.FORCE_REGULAR)
            if paint:
                icon.set_from_paintable(paint)
            else:
                icon.set_from_icon_name(icon_name)

        lbl = Gtk.Label(label=label)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.set_hexpand(True)

        inner.append(icon)
        inner.append(lbl)
        row.set_child(inner)
        row.connect("clicked", lambda _: self._on_select(path))
        return row

    def _section_label(self, text):
        lbl = Gtk.Label(label=text)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_start(10)
        lbl.set_margin_top(8)
        lbl.set_margin_bottom(2)
        lbl.add_css_class("dim-label")
        lbl.add_css_class("caption")
        return lbl

    def _populate(self):
        # Dossiers spéciaux XDG
        # Noms XDG natifs — traduits automatiquement selon la locale
        _home = GLib.get_home_dir()
        specials = [
            (_home,
             "user-home-symbolic",
             os.path.basename(_home) or "Home"),
            (GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP),
             "user-desktop-symbolic",
             GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) and
             os.path.basename(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)) or "Desktop"),
            (GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS),
             "folder-documents-symbolic",
             GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) and
             os.path.basename(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)) or "Documents"),
            (GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD),
             "folder-download-symbolic",
             GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) and
             os.path.basename(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)) or "Downloads"),
            (GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC),
             "folder-music-symbolic",
             GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC) and
             os.path.basename(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC)) or "Music"),
            (GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES),
             "folder-pictures-symbolic",
             GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) and
             os.path.basename(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)) or "Pictures"),
            (GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS),
             "folder-videos-symbolic",
             GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS) and
             os.path.basename(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)) or "Videos"),
        ]
        self._box.append(self._section_label(T["sidebar_favorites"]))
        for path, icon, name in specials:
            if path and os.path.isdir(path):
                self._box.append(self._btn(name, path, icon))

        # Corbeille
        trash_btn = self._btn(T["sidebar_trash"], os.path.expanduser("~/.local/share/Trash/files"), "user-trash-symbolic")
        self._box.append(trash_btn)

        # Bookmarks GTK (~/.config/gtk-3.0/bookmarks)
        bm_file = os.path.expanduser("~/.config/gtk-3.0/bookmarks")
        bookmarks = []
        if os.path.exists(bm_file):
            with open(bm_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(" ", 1)
                    uri   = parts[0]
                    if uri.startswith("file://"):
                        path  = uri[7:]
                        label = parts[1] if len(parts) > 1 else os.path.basename(path)
                        if os.path.isdir(path):
                            bookmarks.append((path, label))

        if bookmarks:
            self._box.append(Gtk.Separator())
            self._box.append(self._section_label(T["sidebar_bookmarks"]))
            for path, label in bookmarks:
                self._box.append(self._btn(label, path, "folder-symbolic"))

        # Volumes/montages GIO
        vm = Gio.VolumeMonitor.get()
        mounts = vm.get_mounts()
        if mounts:
            self._box.append(Gtk.Separator())
            self._box.append(self._section_label(T["sidebar_places"]))
            for mount in mounts:
                root = mount.get_root()
                if root:
                    path = root.get_path()
                    if path and os.path.isdir(path):
                        icon_g = mount.get_icon()
                        iname  = "drive-harddisk-symbolic"
                        if icon_g and hasattr(icon_g, "get_names"):
                            names = icon_g.get_names()
                            if names:
                                iname = names[0]
                        self._box.append(self._btn(mount.get_name(), path, iname))


class DualPanelWindow(Adw.Window):
    __gtype_name__ = "DualPanelWindow"

    def __init__(self, start_path: str):
        super().__init__(title=T["title"])
        self.set_default_size(1500, 800)
        self.set_transient_for(_nautilus_window())

        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        self._left  = FilePanel(start_path)
        self._right = FilePanel(start_path)
        self._left.set_other_panel(self._right)
        self._right.set_other_panel(self._left)

        # Mise à jour des labels copier/déplacer selon quel panneau est actif
        self._left._copy_btn.set_label(T["copy"])
        self._right._copy_btn.set_label(T["copy_left"])
        self._left._move_btn.set_label(T["move"])
        self._right._move_btn.set_label(T["move_left"])

        # Sidebar à gauche
        self._sidebar = SidebarPanel(self._on_sidebar_select)

        # Deux panneaux côte à côte
        paned_panels = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned_panels.set_position(650)
        paned_panels.set_wide_handle(True)
        paned_panels.set_start_child(self._left)
        paned_panels.set_end_child(self._right)

        # Sidebar + panneaux
        paned_main = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned_main.set_position(185)
        paned_main.set_wide_handle(True)
        paned_main.set_resize_start_child(False)
        paned_main.set_shrink_start_child(False)
        paned_main.set_start_child(self._sidebar)
        paned_main.set_end_child(paned_panels)

        # Barre de progression — toute la largeur sous les panneaux
        self._prog = Gtk.ProgressBar()
        self._prog.set_visible(False)
        self._prog.set_margin_start(8)
        self._prog.set_margin_end(8)
        self._prog.set_margin_top(2)
        self._prog.set_margin_bottom(4)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.append(paned_main)
        main_box.append(self._prog)

        # Toast overlay pour les notifications
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(main_box)

        tv.set_content(self._toast_overlay)
        self.set_content(tv)

        # Raccourcis clavier
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)

        def add_shortcut(trigger_str, cb):
            trigger = Gtk.ShortcutTrigger.parse_string(trigger_str)
            action  = Gtk.CallbackAction.new(lambda *a: cb() or True)
            ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))

        add_shortcut("F5",          lambda: (self._left.refresh(), self._right.refresh()))
        add_shortcut("<Alt>Left",   lambda: self._left.navigate(
            os.path.dirname(self._left._path)))
        add_shortcut("<Alt>Right",  lambda: self._right.navigate(
            os.path.dirname(self._right._path)))
        add_shortcut("Escape",      lambda: self.close())

        self.add_controller(ctrl)

    def _on_sidebar_select(self, path):
        """Clic sur la sidebar → naviguer dans le panneau actif (gauche par défaut)."""
        self._left.navigate(path)

    def show_toast(self, msg):
        toast = Adw.Toast.new(msg)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)

    def start_progress(self):
        self._prog.set_fraction(0.0)
        self._prog.set_visible(True)

    def set_progress(self, fraction):
        self._prog.set_fraction(max(0.0, min(1.0, fraction)))

    def stop_progress(self):
        self._prog.set_visible(False)


# ---------------------------------------------------------------------------
# Nautilus extension
# ---------------------------------------------------------------------------

class DualPanelKeyHandler(GObject.GObject):
    """Capture F3 dans toutes les fenêtres Nautilus via GtkEventControllerKey."""
    __gtype_name__ = "DualPanelKeyHandler"

    def __init__(self):
        super().__init__()
        self._hooked = set()   # fenêtres déjà hookées
        # Vérifier périodiquement les nouvelles fenêtres
        GLib.timeout_add(500, self._hook_windows)

    def _hook_windows(self):
        app = Gtk.Application.get_default()
        if app is None:
            return True
        for win in app.get_windows():
            wid = id(win)
            if wid not in self._hooked:
                self._attach_f3(win)
                self._hooked.add(wid)
        return True  # continuer

    def _attach_f3(self, window):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)

        def on_f3(*_):
            # Récupérer le dossier courant via le titre ou fallback home
            path = os.path.expanduser("~")
            app  = Gtk.Application.get_default()
            if app:
                win = app.get_active_window()
                if win:
                    # Nautilus expose le dossier courant dans le titre
                    title = win.get_title() or ""
                    candidate = os.path.expanduser(
                        "~/" + title) if title else path
                    if os.path.isdir(candidate):
                        path = candidate
            DualPanelWindow(path).present()
            return True

        trigger = Gtk.ShortcutTrigger.parse_string("F3")
        action  = Gtk.CallbackAction.new(on_f3)
        ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))
        window.add_controller(ctrl)


class DualPanelExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "DualPanelExtension"

    def __init__(self):
        super().__init__()
        # Démarrer le hook F3 dès que l'extension est chargée
        self._key_handler = DualPanelKeyHandler()

    def get_file_items(self, files):
        # Afficher uniquement sur dossier ou espace vide
        dirs = [f for f in files
                if f.get_uri_scheme() == "file" and f.is_directory()]
        if not dirs:
            return []

        item = Nautilus.MenuItem(
            name="DualPanel::Open",
            label=T["menu_label"],
            tip="Open a dual-panel file manager starting here",
            icon="view-dual-symbolic",
        )
        item.connect("activate", self._on_activate, dirs[0])
        return [item]

    def get_background_items(self, folder):
        item = Nautilus.MenuItem(
            name="DualPanel::OpenBg",
            label=T["menu_label"],
            tip="Open a dual-panel file manager here",
            icon="view-dual-symbolic",
        )
        item.connect("activate", self._on_activate_bg, folder)
        return [item]

    def _on_activate(self, _item, nfile):
        DualPanelWindow(nfile.get_location().get_path()).present()

    def _on_activate_bg(self, _item, folder):
        DualPanelWindow(folder.get_location().get_path()).present()
