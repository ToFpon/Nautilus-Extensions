#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Search Content — Nautilus Python Extension
# DESC: Real content search & replace using grep/ripgrep/sed from Nautilus
# AUTHOR: Tof
# VERSION: 1.3
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
import re
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
        "tab_search":   "Rechercher",
        "tab_replace":  "Rechercher & Remplacer",
        "pattern":      "Texte à rechercher…",
        "replace_with": "Remplacer par…",
        "extensions":   "Extensions (ex: py,txt,md — vide = tous)",
        "recursive":    "Récursif (sous-dossiers)",
        "case":         "Respecter la casse",
        "regex":        "Expression régulière",
        "search":       "Rechercher",
        "preview":      "Aperçu",
        "replace_all":  "Tout remplacer",
        "clear":        "Effacer",
        "tool":         "Outil :",
        "results":      "{n} résultat(s)",
        "results_max":  "{n} sur {total} résultats — limite atteinte",
        "no_results":   "Aucun résultat.",
        "searching":    "Recherche en cours…",
        "replacing":    "Remplacement en cours…",
        "previewing":   "Génération de l'aperçu…",
        "replaced":     "{n} remplacement(s) dans {f} fichier(s) ✓",
        "preview_info": "{n} remplacement(s) dans {f} fichier(s) — cliquez « Tout remplacer » pour appliquer",
        "open_file":    "Ouvrir le fichier",
        "open_gedit":   "Ouvrir avec Gedit",
        "open_folder":  "Ouvrir le dossier",
        "copy_path":    "Copier le chemin",
        "col_file":     "Fichier",
        "col_line":     "Ligne",
        "col_match":    "Contenu",
        "error":        "Erreur : ",
        "empty_search": "Saisissez un texte à rechercher.",
        "confirm_title":"Confirmer le remplacement",
        "confirm_body": "Cette action va modifier {f} fichier(s). Une sauvegarde .bak sera créée. Continuer ?",
        "confirm_ok":   "Remplacer",
        "confirm_cancel":"Annuler",
        "backup_note":  "Sauvegarde .bak créée pour chaque fichier modifié.",
        "toggle_all":   "Tout cocher / décocher",
        "none_selected":"Aucune ligne sélectionnée.",
    }
elif _lang.startswith("de"):
    T = {
        "menu_label":   "In Dateien suchen",
        "title":        "Inhaltssuche",
        "tab_search":   "Suchen",
        "tab_replace":  "Suchen & Ersetzen",
        "pattern":      "Suchtext…",
        "replace_with": "Ersetzen durch…",
        "extensions":   "Erweiterungen (z.B. py,txt,md — leer = alle)",
        "recursive":    "Rekursiv (Unterordner)",
        "case":         "Groß-/Kleinschreibung",
        "regex":        "Regulärer Ausdruck",
        "search":       "Suchen",
        "preview":      "Vorschau",
        "replace_all":  "Alle ersetzen",
        "clear":        "Löschen",
        "tool":         "Werkzeug:",
        "results":      "{n} Ergebnis(se)",
        "results_max":  "{n} von {total} Ergebnissen — Limit erreicht",
        "no_results":   "Keine Ergebnisse.",
        "searching":    "Suche läuft…",
        "replacing":    "Ersetzen läuft…",
        "previewing":   "Vorschau wird erstellt…",
        "replaced":     "{n} Ersetzung(en) in {f} Datei(en) ✓",
        "preview_info": "{n} Ersetzung(en) in {f} Datei(en) — „Alle ersetzen“ zum Anwenden",
        "open_file":    "Datei öffnen",
        "open_gedit":   "Mit Gedit öffnen",
        "open_folder":  "Ordner öffnen",
        "copy_path":    "Pfad kopieren",
        "col_file":     "Datei",
        "col_line":     "Zeile",
        "col_match":    "Inhalt",
        "error":        "Fehler: ",
        "empty_search": "Bitte einen Suchtext eingeben.",
        "confirm_title":"Ersetzen bestätigen",
        "confirm_body": "Diese Aktion ändert {f} Datei(en). Eine .bak-Sicherung wird erstellt. Fortfahren?",
        "confirm_ok":   "Ersetzen",
        "confirm_cancel":"Abbrechen",
        "backup_note":  ".bak-Sicherung für jede geänderte Datei erstellt.",
        "toggle_all":   "Alle an-/abwählen",
        "none_selected":"Keine Zeile ausgewählt.",
    }
else:
    T = {
        "menu_label":   "Search in files",
        "title":        "Content Search",
        "tab_search":   "Search",
        "tab_replace":  "Search & Replace",
        "pattern":      "Text to search…",
        "replace_with": "Replace with…",
        "extensions":   "Extensions (e.g. py,txt,md — empty = all)",
        "recursive":    "Recursive (subfolders)",
        "case":         "Case sensitive",
        "regex":        "Regular expression",
        "search":       "Search",
        "preview":      "Preview",
        "replace_all":  "Replace all",
        "clear":        "Clear",
        "tool":         "Tool:",
        "results":      "{n} result(s)",
        "results_max":  "{n} of {total} results — limit reached",
        "no_results":   "No results.",
        "searching":    "Searching…",
        "replacing":    "Replacing…",
        "previewing":   "Building preview…",
        "replaced":     "{n} replacement(s) in {f} file(s) ✓",
        "preview_info": "{n} replacement(s) in {f} file(s) — click “Replace all” to apply",
        "open_file":    "Open file",
        "open_gedit":   "Open with Gedit",
        "open_folder":  "Open folder",
        "copy_path":    "Copy path",
        "col_file":     "File",
        "col_line":     "Line",
        "col_match":    "Content",
        "error":        "Error: ",
        "empty_search": "Enter a text to search for.",
        "confirm_title":"Confirm replacement",
        "confirm_body": "This will modify {f} file(s). A .bak backup will be created. Continue?",
        "confirm_ok":   "Replace",
        "confirm_cancel":"Cancel",
        "backup_note":  ".bak backup created for each modified file.",
        "toggle_all":   "Check / uncheck all",
        "none_selected":"No line selected.",
    }

HAS_RG = shutil.which("rg") is not None
HAS_GEDIT = shutil.which("gedit") is not None
MAX_RESULTS = 2000


def _nautilus_window():
    app = Gtk.Application.get_default()
    return app.get_active_window() if app else None


def _build_search_cmd(pattern, folder, recursive, exts_text, case, regex):
    """Construit la commande grep/rg de recherche."""
    exts_list = [e.strip().lstrip(".") for e in exts_text.split(",") if e.strip()]
    if HAS_RG:
        cmd = ["rg", "--line-number", "--no-heading", "--color=never"]
        if not case:      cmd.append("--ignore-case")
        if not regex:     cmd.append("--fixed-strings")
        if not recursive: cmd.append("--max-depth=1")
        for e in exts_list:
            cmd += ["--glob", f"*.{e}"]
        cmd += [pattern, folder]
    else:
        cmd = ["grep", "-n", "-H", "--binary-files=without-match",
               "--exclude-dir=.git", "--exclude-dir=node_modules",
               "--exclude-dir=__pycache__"]
        if recursive: cmd.append("-r")
        if not case:  cmd.append("-i")
        if not regex: cmd.append("-F")
        if exts_list:
            for e in exts_list:
                cmd += ["--include", f"*.{e}"]
        cmd += [pattern, folder]
    return cmd


# ---------------------------------------------------------------------------
# Search Window (with Search + Search&Replace tabs)
# ---------------------------------------------------------------------------

class SearchWindow(Adw.Window):
    __gtype_name__ = "SearchContentWindow"

    def __init__(self, folder):
        super().__init__(title=T["title"])
        self.set_default_size(840, 620)
        self.set_resizable(True)
        self.set_transient_for(_nautilus_window())
        self._folder = folder
        self._closed = False
        self._preview_edits = None  # cache des modifs pour le replace
        self._r_checks = []         # checkboxes des lignes d'aperçu
        self._selected_edits = []   # edits cochés au moment du remplacement

        tv  = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_decoration_layout(":close")

        # ViewSwitcher dans la barre de titre
        self._stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher()
        switcher.set_stack(self._stack)
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        hdr.set_title_widget(switcher)
        tv.add_top_bar(hdr)

        # Pages
        self._stack.add_titled_with_icon(
            self._build_search_page(), "search",
            T["tab_search"], "edit-find-symbolic")
        self._stack.add_titled_with_icon(
            self._build_replace_page(), "replace",
            T["tab_replace"], "edit-find-replace-symbolic")

        tv.set_content(self._stack)

        # ToastOverlay pour les confirmations
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(tv)
        self.set_content(self._toast_overlay)

        self.connect("close-request",
                     lambda *_: setattr(self, "_closed", True) or False)
        GLib.idle_add(lambda: (self._entry.grab_focus(), False)[1])

    def _toast(self, message):
        """Affiche un toast natif dans la fenêtre."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)

    # ───────────────────────────────────────────────────────────────────────
    # Page 1 : Search
    # ───────────────────────────────────────────────────────────────────────

    def _build_search_page(self):
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)

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
        tool_name.set_markup("<b>ripgrep</b>" if HAS_RG else "grep")
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

        self._folder_lbl = Gtk.Label()
        self._folder_lbl.set_markup(
            f"<small>📁 <tt>{GLib.markup_escape_text(self._folder)}</tt></small>")
        self._folder_lbl.set_halign(Gtk.Align.START)
        self._folder_lbl.set_hexpand(True)
        self._folder_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._folder_lbl.set_selectable(True)
        self._folder_lbl.add_css_class("dim-label")
        self._folder_lbl.set_margin_start(8)
        btns.append(self._folder_lbl)

        self._status = Gtk.Label(label="")
        self._status.set_halign(Gtk.Align.END)
        self._status.add_css_class("dim-label")
        btns.append(self._status)
        form.append(btns)

        main.append(form)
        main.append(Gtk.Separator())

        col_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        col_hdr.set_margin_start(12); col_hdr.set_margin_end(12)
        col_hdr.set_margin_top(4); col_hdr.set_margin_bottom(4)
        for label, size in [(T["col_file"], 220), (T["col_line"], 50), (T["col_match"], -1)]:
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.add_css_class("dim-label")
            if size > 0: lbl.set_size_request(size, -1)
            else:        lbl.set_hexpand(True)
            col_hdr.append(lbl)
        main.append(col_hdr)
        main.append(Gtk.Separator())

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        scroll.set_child(self._list)
        main.append(scroll)
        return main

    # ───────────────────────────────────────────────────────────────────────
    # Page 2 : Search & Replace
    # ───────────────────────────────────────────────────────────────────────

    def _build_replace_page(self):
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)

        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        form.set_margin_start(12); form.set_margin_end(12)
        form.set_margin_top(12); form.set_margin_bottom(8)

        self._r_entry = Gtk.SearchEntry()
        self._r_entry.set_placeholder_text(T["pattern"])
        self._r_entry.connect("activate", lambda _: self._on_preview())
        form.append(self._r_entry)

        self._r_replace = Gtk.Entry()
        self._r_replace.set_placeholder_text(T["replace_with"])
        form.append(self._r_replace)

        self._r_ext = Gtk.Entry()
        self._r_ext.set_placeholder_text(T["extensions"])
        form.append(self._r_ext)

        opts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._r_rec = Gtk.CheckButton(label=T["recursive"]); self._r_rec.set_active(True)
        opts.append(self._r_rec)
        self._r_cas = Gtk.CheckButton(label=T["case"]); opts.append(self._r_cas)
        self._r_reg = Gtk.CheckButton(label=T["regex"]); opts.append(self._r_reg)

        tool_lbl = Gtk.Label(label=T["tool"])
        tool_lbl.add_css_class("dim-label"); tool_lbl.set_margin_start(8)
        opts.append(tool_lbl)
        tool_name = Gtk.Label()
        tool_name.set_markup("<b>ripgrep</b>" if HAS_RG else "grep")
        tool_name.add_css_class("dim-label")
        opts.append(tool_name)
        form.append(opts)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._r_btn_preview = Gtk.Button(label=T["preview"])
        self._r_btn_preview.connect("clicked", lambda _: self._on_preview())
        btns.append(self._r_btn_preview)

        self._r_btn_replace = Gtk.Button(label=T["replace_all"])
        self._r_btn_replace.add_css_class("destructive-action")
        self._r_btn_replace.set_sensitive(False)
        self._r_btn_replace.connect("clicked", lambda _: self._on_replace_all())
        btns.append(self._r_btn_replace)

        self._r_btn_clear = Gtk.Button(label=T["clear"])
        self._r_btn_clear.add_css_class("flat")
        self._r_btn_clear.connect("clicked", lambda _: self._r_clear())
        btns.append(self._r_btn_clear)

        # Dossier courant (affichage à droite)
        self._r_folder_lbl = Gtk.Label()
        self._r_folder_lbl.set_markup(
            f"<small>📁 <tt>{GLib.markup_escape_text(self._folder)}</tt></small>")
        self._r_folder_lbl.set_halign(Gtk.Align.START)
        self._r_folder_lbl.set_hexpand(True)
        self._r_folder_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._r_folder_lbl.set_selectable(True)
        self._r_folder_lbl.add_css_class("dim-label")
        self._r_folder_lbl.set_margin_start(8)
        btns.append(self._r_folder_lbl)

        self._r_status = Gtk.Label(label="")
        self._r_status.set_halign(Gtk.Align.END)
        self._r_status.add_css_class("dim-label")
        btns.append(self._r_status)
        form.append(btns)

        main.append(form)
        main.append(Gtk.Separator())

        # En-tête colonnes (☑ / Fichier / Ligne / Avant → Après)
        col_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        col_hdr.set_margin_start(12); col_hdr.set_margin_end(12)
        col_hdr.set_margin_top(4); col_hdr.set_margin_bottom(4)

        # Case "tout cocher / décocher"
        self._r_check_all = Gtk.CheckButton()
        self._r_check_all.set_active(True)
        self._r_check_all.set_tooltip_text(T["toggle_all"])
        self._r_check_all.connect("toggled", self._on_toggle_all)
        self._r_check_all.set_size_request(24, -1)
        col_hdr.append(self._r_check_all)

        for label, size in [(T["col_file"], 180), (T["col_line"], 50), (T["col_match"], -1)]:
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.add_css_class("dim-label")
            if size > 0: lbl.set_size_request(size, -1)
            else:        lbl.set_hexpand(True)
            col_hdr.append(lbl)
        main.append(col_hdr)
        main.append(Gtk.Separator())

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._r_list = Gtk.ListBox()
        self._r_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._r_list.add_css_class("navigation-sidebar")
        scroll.set_child(self._r_list)
        main.append(scroll)
        return main

    # ───────────────────────────────────────────────────────────────────────
    # Search logic (page 1)
    # ───────────────────────────────────────────────────────────────────────

    def _on_search(self):
        pattern = self._entry.get_text().strip()
        if not pattern:
            return
        self._clear()
        self._btn.set_sensitive(False)
        self._status.set_text(T["searching"])
        threading.Thread(target=self._do_search, args=(pattern,), daemon=True).start()

    def _do_search(self, pattern):
        cmd = _build_search_cmd(pattern, self._folder,
                                self._rec.get_active(), self._ext.get_text(),
                                self._cas.get_active(), self._reg.get_active())
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

        gc_dbl = Gtk.GestureClick()
        gc_dbl.set_button(1)
        gc_dbl.connect("pressed", self._on_left_click, filepath)
        row.add_controller(gc_dbl)

        gc = Gtk.GestureClick()
        gc.set_button(3)
        gc.connect("pressed", self._on_right_click, filepath)
        row.add_controller(gc)

        self._list.append(row)

    def _on_left_click(self, gesture, n_press, x, y, filepath):
        if n_press == 2:
            subprocess.Popen(["xdg-open", filepath])

    def _on_right_click(self, gesture, n, x, y, filepath):
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

    # ───────────────────────────────────────────────────────────────────────
    # Search & Replace logic (page 2)
    # ───────────────────────────────────────────────────────────────────────

    def _r_clear(self):
        while True:
            row = self._r_list.get_first_child()
            if row is None: break
            self._r_list.remove(row)
        self._r_status.set_text("")
        self._preview_edits = None
        self._r_checks = []
        self._r_btn_replace.set_sensitive(False)

    def _on_toggle_all(self, check):
        active = check.get_active()
        for c in self._r_checks:
            c.set_active(active)

    def _on_preview(self):
        pattern = self._r_entry.get_text()
        if not pattern.strip():
            self._r_status.set_text(T["empty_search"])
            return
        self._r_clear()
        self._r_btn_preview.set_sensitive(False)
        self._r_status.set_text(T["previewing"])
        threading.Thread(target=self._do_preview, args=(pattern,), daemon=True).start()

    def _do_preview(self, pattern):
        replacement = self._r_replace.get_text()
        case   = self._r_cas.get_active()
        regex  = self._r_reg.get_active()

        # 1. Trouver les fichiers concernés via grep/rg (liste de fichiers)
        cmd = _build_search_cmd(pattern, self._folder,
                                self._r_rec.get_active(), self._r_ext.get_text(),
                                case, regex)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    errors="replace", timeout=300)
            lines = result.stdout.splitlines()
        except Exception as e:
            if not self._closed:
                GLib.idle_add(self._r_status.set_text, T["error"] + str(e))
                GLib.idle_add(self._r_btn_preview.set_sensitive, True)
            return

        # 2. Construire le regex Python pour l'aperçu
        try:
            flags = 0 if case else re.IGNORECASE
            if regex:
                rx = re.compile(pattern, flags)
            else:
                rx = re.compile(re.escape(pattern), flags)
        except re.error as e:
            if not self._closed:
                GLib.idle_add(self._r_status.set_text, T["error"] + str(e))
                GLib.idle_add(self._r_btn_preview.set_sensitive, True)
            return

        # 3. Parser les lignes et calculer le remplacement
        edits = []   # (filepath, lineno, before, after)
        files_set = set()
        for line in lines[:MAX_RESULTS]:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            filepath, lineno, before = parts
            if not os.path.isfile(filepath):
                continue
            try:
                after = rx.sub(replacement, before)
            except re.error:
                after = before
            if after != before:
                edits.append((filepath, lineno, before, after))
                files_set.add(filepath)

        if not self._closed:
            GLib.idle_add(self._show_preview, edits, len(files_set))

    def _show_preview(self, edits, nfiles):
        if self._closed:
            return False
        self._preview_edits = edits
        self._r_checks = []
        self._r_check_all.set_active(True)
        nrepl = len(edits)
        for filepath, lineno, before, after in edits[:MAX_RESULTS]:
            self._add_preview_row(filepath, lineno, before, after)
        if nrepl:
            self._r_status.set_text(T["preview_info"].format(n=nrepl, f=nfiles))
            self._r_btn_replace.set_sensitive(True)
        else:
            self._r_status.set_text(T["no_results"])
            self._r_btn_replace.set_sensitive(False)
        self._r_btn_preview.set_sensitive(True)
        return False

    def _add_preview_row(self, filepath, lineno, before, after):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(4); box.set_margin_end(4)
        box.set_margin_top(2); box.set_margin_bottom(2)

        # Case à cocher (cochée par défaut)
        check = Gtk.CheckButton()
        check.set_active(True)
        check.set_valign(Gtk.Align.CENTER)
        check.set_size_request(24, -1)
        box.append(check)
        self._r_checks.append(check)

        rel = os.path.relpath(filepath, self._folder)
        fl = Gtk.Label(label=rel); fl.set_halign(Gtk.Align.START)
        fl.set_ellipsize(Pango.EllipsizeMode.MIDDLE); fl.set_size_request(180, -1)
        fl.add_css_class("monospace"); box.append(fl)

        ll = Gtk.Label(label=lineno); ll.set_halign(Gtk.Align.END)
        ll.set_size_request(50, -1); ll.add_css_class("dim-label")
        ll.add_css_class("monospace"); box.append(ll)

        # Avant (rouge barré) → Après (vert)
        diff_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        diff_box.set_hexpand(True)

        before_lbl = Gtk.Label()
        before_lbl.set_markup(
            f"<span strikethrough='true' foreground='#e01b24'>"
            f"{GLib.markup_escape_text(before.strip())}</span>")
        before_lbl.set_halign(Gtk.Align.START)
        before_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        before_lbl.add_css_class("monospace")
        diff_box.append(before_lbl)

        after_lbl = Gtk.Label()
        after_lbl.set_markup(
            f"<span foreground='#26a269'>"
            f"{GLib.markup_escape_text(after.strip())}</span>")
        after_lbl.set_halign(Gtk.Align.START)
        after_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        after_lbl.add_css_class("monospace")
        diff_box.append(after_lbl)

        box.append(diff_box)
        row.set_child(box)
        self._r_list.append(row)

    def _on_replace_all(self):
        if not self._preview_edits:
            return
        # Ne garder que les lignes cochées
        selected = [e for e, c in zip(self._preview_edits, self._r_checks)
                    if c.get_active()]
        if not selected:
            self._r_status.set_text(T["none_selected"])
            return
        self._selected_edits = selected
        files_set = set(e[0] for e in selected)
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading=T["confirm_title"],
            body=T["confirm_body"].format(f=len(files_set)))
        dlg.add_response("cancel", T["confirm_cancel"])
        dlg.add_response("ok", T["confirm_ok"])
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", self._do_replace_confirmed)
        dlg.present()

    def _do_replace_confirmed(self, dlg, response):
        if response != "ok":
            return
        self._r_btn_replace.set_sensitive(False)
        self._r_btn_preview.set_sensitive(False)
        self._r_status.set_text(T["replacing"])

        pattern     = self._r_entry.get_text()
        replacement = self._r_replace.get_text()
        case   = self._r_cas.get_active()
        regex  = self._r_reg.get_active()

        # Regrouper les numéros de ligne sélectionnés par fichier
        targets = {}   # filepath -> set(lineno_int)
        for filepath, lineno, before, after in self._selected_edits:
            try:
                targets.setdefault(filepath, set()).add(int(lineno))
            except ValueError:
                continue

        threading.Thread(
            target=self._do_replace,
            args=(pattern, replacement, case, regex, targets),
            daemon=True).start()

    def _do_replace(self, pattern, replacement, case, regex, targets):
        flags = 0 if case else re.IGNORECASE
        try:
            if regex:
                rx = re.compile(pattern, flags)
            else:
                rx = re.compile(re.escape(pattern), flags)
        except re.error as e:
            if not self._closed:
                GLib.idle_add(self._r_status.set_text, T["error"] + str(e))
            return

        total_repl = 0
        nfiles = 0
        for filepath, linenos in targets.items():
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                changed = False
                file_repl = 0
                for idx, line in enumerate(lines):
                    # idx+1 = numéro de ligne (1-based)
                    if (idx + 1) in linenos:
                        new_line, n = rx.subn(replacement, line)
                        if n > 0 and new_line != line:
                            lines[idx] = new_line
                            file_repl += n
                            changed = True
                if changed:
                    # Sauvegarde .bak
                    shutil.copy2(filepath, filepath + ".bak")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    total_repl += file_repl
                    nfiles += 1
            except Exception:
                continue

        if not self._closed:
            GLib.idle_add(self._replace_done, total_repl, nfiles)

    def _replace_done(self, total_repl, nfiles):
        if self._closed:
            return False
        msg = T["replaced"].format(n=total_repl, f=nfiles)
        self._r_status.set_text(msg)
        if total_repl:
            self._toast(msg)
        self._r_btn_preview.set_sensitive(True)
        self._r_btn_replace.set_sensitive(False)
        self._preview_edits = None
        # Rafraîchir l'aperçu (les lignes sont maintenant remplacées)
        GLib.timeout_add(400, lambda: self._on_preview() or False)
        return False


# ---------------------------------------------------------------------------
# F8 key handler (hooks Nautilus windows via timer)
# ---------------------------------------------------------------------------

class SearchContentKeyHandler(GObject.GObject):
    """Capture F8 dans toutes les fenêtres Nautilus via GtkEventControllerKey."""
    __gtype_name__ = "SearchContentKeyHandler"

    _current_path = None

    def __init__(self):
        super().__init__()
        self._hooked = set()
        GLib.timeout_add(1000, self._hook_windows)

    def _hook_windows(self):
        app = Gtk.Application.get_default()
        if app is None:
            return True
        for win in app.get_windows():
            if win in self._hooked:
                continue
            self._hooked.add(win)
            ctrl = Gtk.ShortcutController()
            ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)

            def on_f8(widget, args):
                path = (SearchContentKeyHandler._current_path
                        or os.path.expanduser("~"))
                SearchWindow(path).present()
                return True

            trigger = Gtk.ShortcutTrigger.parse_string("F8")
            action  = Gtk.CallbackAction.new(on_f8)
            ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))
            win.add_controller(ctrl)
        return True


# ---------------------------------------------------------------------------
# Nautilus Extension
# ---------------------------------------------------------------------------

class SearchContentExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "SearchContentExtension"

    def __init__(self):
        super().__init__()
        self._key_handler = SearchContentKeyHandler()

    def get_file_items(self, files):
        if len(files) != 1: return []
        f = files[0]
        if f.get_uri_scheme() != "file" or not f.is_directory(): return []
        path = f.get_location().get_path()
        if not path: return []
        SearchContentKeyHandler._current_path = path
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
        SearchContentKeyHandler._current_path = path
        item = Nautilus.MenuItem(
            name  = "SearchContent::Open",
            label = T["menu_label"],
            tip   = "Search text content in files",
            icon  = "edit-find-symbolic",
        )
        item.connect("activate", lambda *_: SearchWindow(path).present())
        return [item]
