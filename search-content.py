#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Search Content — Nautilus Python Extension
# DESC: Real content search using grep/ripgrep from Nautilus
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
# INSTALL:
#   cp search-content.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q
# OPTIONAL: sudo apt install ripgrep

import os
import shutil
import subprocess
import threading
import locale

import gi
gi.require_version("Gtk",     "4.0")
gi.require_version("Adw",     "1")
gi.require_version("Nautilus","4.0")
from gi.repository import GObject, Gtk, Adw, GLib, Pango, Gdk, Nautilus

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":   "Rechercher dans les fichiers",
        "title":        "Recherche de contenu",
        "pattern":      "Texte à rechercher…",
        "extensions":   "Extensions (ex: py,txt,md — vide = tous)",
        "recursive":    "Récursif (sous-dossiers)",
        "case":         "Respecter la casse",
        "regex":        "Expression régulière",
        "search":       "Rechercher",
        "clear":        "Effacer",
        "tool":         "Outil :",
        "results":      "{n} résultat(s)",
        "results_max":  "{n} sur {total} résultats — limite atteinte",
        "no_results":   "Aucun résultat.",
        "searching":    "Recherche en cours…",
        "open_file":    "Ouvrir le fichier",
        "open_gedit":   "Ouvrir avec Gedit",
        "open_folder":  "Ouvrir le dossier",
        "copy_path":    "Copier le chemin",
        "col_file":     "Fichier",
        "col_line":     "Ligne",
        "col_match":    "Contenu",
        "error":        "Erreur : ",
    }
elif _lang.startswith("de"):
    T = {
        "menu_label":   "In Dateien suchen",
        "title":        "Inhaltssuche",
        "pattern":      "Suchtext…",
        "extensions":   "Erweiterungen (z.B. py,txt,md — leer = alle)",
        "recursive":    "Rekursiv (Unterordner)",
        "case":         "Groß-/Kleinschreibung",
        "regex":        "Regulärer Ausdruck",
        "search":       "Suchen",
        "clear":        "Löschen",
        "tool":         "Werkzeug:",
        "results":      "{n} Ergebnis(se)",
        "results_max":  "{n} von {total} Ergebnissen — Limit erreicht",
        "no_results":   "Keine Ergebnisse.",
        "searching":    "Suche läuft…",
        "open_file":    "Datei öffnen",
        "open_gedit":   "Mit Gedit öffnen",
        "open_folder":  "Ordner öffnen",
        "copy_path":    "Pfad kopieren",
        "col_file":     "Datei",
        "col_line":     "Zeile",
        "col_match":    "Inhalt",
        "error":        "Fehler: ",
    }
else:
    T = {
        "menu_label":   "Search in files",
        "title":        "Content Search",
        "pattern":      "Text to search…",
        "extensions":   "Extensions (e.g. py,txt,md — empty = all)",
        "recursive":    "Recursive (subfolders)",
        "case":         "Case sensitive",
        "regex":        "Regular expression",
        "search":       "Search",
        "clear":        "Clear",
        "tool":         "Tool:",
        "results":      "{n} result(s)",
        "results_max":  "{n} of {total} results — limit reached",
        "no_results":   "No results.",
        "searching":    "Searching…",
        "open_file":    "Open file",
        "open_gedit":   "Open with Gedit",
        "open_folder":  "Open folder",
        "copy_path":    "Copy path",
        "col_file":     "File",
        "col_line":     "Line",
        "col_match":    "Content",
        "error":        "Error: ",
    }

HAS_RG = shutil.which("rg") is not None
HAS_GEDIT = shutil.which("gedit") is not None
MAX_RESULTS = 2000


def _nautilus_window():
    app = Gtk.Application.get_default()
    return app.get_active_window() if app else None


# ---------------------------------------------------------------------------
# Search Window
# ---------------------------------------------------------------------------

class SearchWindow(Adw.Window):
    __gtype_name__ = "SearchContentWindow"

    def __init__(self, folder):
        super().__init__(title=T["title"])
        self.set_default_size(820, 600)
        self.set_resizable(True)
        self.set_transient_for(_nautilus_window())
        self._folder = folder
        self._closed = False

        tv  = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_decoration_layout(":close")
        hdr.set_title_widget(Gtk.Label(label=T["title"]))
        tv.add_top_bar(hdr)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)

        # ── Form ──────────────────────────────────────────────────────────────
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        form.set_margin_start(12); form.set_margin_end(12)
        form.set_margin_top(12); form.set_margin_bottom(8)

        self._entry = Gtk.SearchEntry()
        self._entry.set_placeholder_text(T["pattern"])
        self._entry.connect("activate", lambda _: self._on_search())
        form.append(self._entry)

        self._ext = Gtk.Entry()
        self._ext.set_placeholder_text(T["extensions"])
        form.append(self._ext)

        opts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._rec = Gtk.CheckButton(label=T["recursive"]); self._rec.set_active(True)
        opts.append(self._rec)
        self._cas = Gtk.CheckButton(label=T["case"]); opts.append(self._cas)
        self._reg = Gtk.CheckButton(label=T["regex"]); opts.append(self._reg)

        tool_lbl = Gtk.Label(label=T["tool"])
        tool_lbl.add_css_class("dim-label"); tool_lbl.set_margin_start(8)
        opts.append(tool_lbl)
        tool_name = Gtk.Label()
        if HAS_RG:
            tool_name.set_markup("<b>ripgrep</b>")
        else:
            tool_name.set_text("grep")
        tool_name.add_css_class("dim-label")
        opts.append(tool_name)
        form.append(opts)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._btn = Gtk.Button(label=T["search"])
        self._btn.add_css_class("suggested-action")
        self._btn.connect("clicked", lambda _: self._on_search())
        btns.append(self._btn)
        self._btn_clear = Gtk.Button(label=T["clear"])
        self._btn_clear.add_css_class("flat")
        self._btn_clear.connect("clicked", lambda _: self._clear())
        btns.append(self._btn_clear)
        self._status = Gtk.Label(label="")
        self._status.set_hexpand(True); self._status.set_halign(Gtk.Align.START)
        self._status.add_css_class("dim-label")
        btns.append(self._status)
        form.append(btns)

        main.append(form)
        main.append(Gtk.Separator())

        # ── Colonnes ──────────────────────────────────────────────────────────
        col_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        col_hdr.set_margin_start(12); col_hdr.set_margin_end(12)
        col_hdr.set_margin_top(4); col_hdr.set_margin_bottom(4)
        for label, size in [(T["col_file"], 220), (T["col_line"], 50), (T["col_match"], -1)]:
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.add_css_class("dim-label")
            if size > 0:
                lbl.set_size_request(size, -1)
            else:
                lbl.set_hexpand(True)
            col_hdr.append(lbl)
        main.append(col_hdr)
        main.append(Gtk.Separator())

        # ── Résultats ─────────────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        scroll.set_child(self._list)
        main.append(scroll)

        tv.set_content(main)
        self.set_content(tv)

        self.connect("close-request",
                     lambda *_: setattr(self, "_closed", True) or False)
        # Focus différé — lambda False pour ne pas boucler
        GLib.idle_add(lambda: (self._entry.grab_focus(), False)[1])

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search(self):
        pattern = self._entry.get_text().strip()
        if not pattern:
            return
        self._clear()
        self._btn.set_sensitive(False)
        self._status.set_text(T["searching"])
        threading.Thread(target=self._do_search, args=(pattern,), daemon=True).start()

    def _do_search(self, pattern):
        exts_list = [e.strip().lstrip(".") for e in self._ext.get_text().split(",") if e.strip()]
        if HAS_RG:
            cmd = ["rg", "--line-number", "--no-heading", "--color=never"]
            if not self._cas.get_active(): cmd.append("--ignore-case")
            if not self._reg.get_active(): cmd.append("--fixed-strings")
            if not self._rec.get_active(): cmd.append("--max-depth=1")
            for e in exts_list:
                cmd += ["--glob", f"*.{e}"]
            cmd += [pattern, self._folder]
        else:
            cmd = ["grep", "-n", "-H", "--binary-files=without-match",
                   "--exclude-dir=.git", "--exclude-dir=node_modules",
                   "--exclude-dir=__pycache__"]
            if self._rec.get_active(): cmd.append("-r")
            if not self._cas.get_active(): cmd.append("-i")
            if not self._reg.get_active(): cmd.append("-F")
            if exts_list:
                for e in exts_list:
                    cmd += ["--include", f"*.{e}"]
            cmd += [pattern, self._folder]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    errors="replace", timeout=300)
            lines = result.stdout.splitlines()
        except Exception as e:
            if not self._closed:
                GLib.idle_add(self._status.set_text, T["error"] + str(e))
                GLib.idle_add(self._btn.set_sensitive, True)
            return

        if not self._closed:
            GLib.idle_add(self._display_results, lines)

    def _display_results(self, lines):
        if self._closed:
            return False
        count = 0
        total = len(lines)
        for line in lines[:MAX_RESULTS]:
            parts = line.split(":", 2)
            if len(parts) < 3: continue
            filepath, lineno, content_str = parts
            if not os.path.isfile(filepath): continue
            self._add_result(filepath, lineno, content_str)
            count += 1
        if total > MAX_RESULTS:
            self._status.set_text(T["results_max"].format(n=count, total=total))
        else:
            self._status.set_text(T["results"].format(n=count) if count else T["no_results"])
        self._btn.set_sensitive(True)
        return False

    # ── Result row ────────────────────────────────────────────────────────────

    def _add_result(self, filepath, lineno, content_str):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(4); box.set_margin_end(4)
        box.set_margin_top(2); box.set_margin_bottom(2)

        rel = os.path.relpath(filepath, self._folder)
        fl = Gtk.Label(label=rel); fl.set_halign(Gtk.Align.START)
        fl.set_ellipsize(Pango.EllipsizeMode.MIDDLE); fl.set_size_request(220, -1)
        fl.add_css_class("monospace"); box.append(fl)

        ll = Gtk.Label(label=lineno); ll.set_halign(Gtk.Align.END)
        ll.set_size_request(50, -1); ll.add_css_class("dim-label")
        ll.add_css_class("monospace"); box.append(ll)

        ml = Gtk.Label(label=content_str.strip()); ml.set_halign(Gtk.Align.START)
        ml.set_hexpand(True); ml.set_ellipsize(Pango.EllipsizeMode.END)
        ml.set_selectable(False); ml.add_css_class("monospace"); box.append(ml)

        row.set_child(box)
        row._filepath = filepath

        # Double-clic gauche → ouvrir
        gc_dbl = Gtk.GestureClick()
        gc_dbl.set_button(1)
        gc_dbl.connect("pressed", self._on_left_click, filepath)
        row.add_controller(gc_dbl)

        # Clic droit → menu contextuel
        gc = Gtk.GestureClick()
        gc.set_button(3)
        gc.connect("pressed", self._on_right_click, filepath)
        row.add_controller(gc)

        self._list.append(row)

    def _on_left_click(self, gesture, n_press, x, y, filepath):
        """Ouvre uniquement sur double-clic."""
        if n_press == 2:
            subprocess.Popen(["xdg-open", filepath])

    def _on_right_click(self, gesture, n, x, y, filepath):
        """Clic droit → menu contextuel."""
        popover = Gtk.Popover()
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        menu.set_margin_start(4); menu.set_margin_end(4)
        menu.set_margin_top(4); menu.set_margin_bottom(4)

        def make_btn(label, callback):
            b = Gtk.Button(label=label)
            b.add_css_class("flat")
            b.set_halign(Gtk.Align.FILL)
            child = b.get_child()
            if isinstance(child, Gtk.Label):
                child.set_halign(Gtk.Align.START)
            b.connect("clicked", lambda _: (popover.popdown(), callback()))
            menu.append(b)

        make_btn(T["open_file"],
                 lambda: subprocess.Popen(["xdg-open", filepath]))
        if HAS_GEDIT:
            make_btn(T["open_gedit"],
                     lambda: subprocess.Popen(["gedit", filepath]))
        make_btn(T["open_folder"],
                 lambda: subprocess.Popen(["xdg-open", os.path.dirname(filepath)]))
        make_btn(T["copy_path"],
                 lambda: Gdk.Display.get_default().get_clipboard().set(filepath))

        popover.set_child(menu)
        popover.set_parent(gesture.get_widget())
        popover.set_has_arrow(True)
        popover.popup()

    def _clear(self):
        while True:
            row = self._list.get_first_child()
            if row is None: break
            self._list.remove(row)
        self._status.set_text("")


# ---------------------------------------------------------------------------
# Nautilus Extension
# ---------------------------------------------------------------------------

class SearchContentExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "SearchContentExtension"

    def get_file_items(self, files):
        if len(files) != 1: return []
        f = files[0]
        if f.get_uri_scheme() != "file" or not f.is_directory(): return []
        path = f.get_location().get_path()
        if not path: return []
        item = Nautilus.MenuItem(
            name  = "SearchContent::OpenFolder",
            label = T["menu_label"],
            tip   = "Search text content in files",
            icon  = "edit-find-symbolic",
        )
        item.connect("activate", lambda *_: SearchWindow(path).present())
        return [item]

    def get_background_items(self, folder):
        path = folder.get_location().get_path() if folder else None
        if not path: return []
        item = Nautilus.MenuItem(
            name  = "SearchContent::Open",
            label = T["menu_label"],
            tip   = "Search text content in files",
            icon  = "edit-find-symbolic",
        )
        item.connect("activate", lambda *_: SearchWindow(path).present())
        return [item]
