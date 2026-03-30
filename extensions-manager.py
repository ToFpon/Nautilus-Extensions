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
# NAME: Extensions Manager – Nautilus Python Extension
# DESC: Activer/désactiver les extensions Nautilus depuis Nautilus
# INSTALL:
#   cp extensions-manager.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import shutil
import subprocess
import locale

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gdk, GLib, Nautilus, Pango

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":   "Gérer les extensions",
        "title":        "Gestionnaire d'extensions",
        "active":       "Actives",
        "disabled":     "Désactivées",
        "enable":       "Activer",
        "disable":      "Désactiver",
        "restart":      "Redémarrer Nautilus",
        "restart_msg":  "Nautilus va redémarrer pour appliquer les changements.",
        "confirm":      "Confirmer",
        "cancel":       "Annuler",
        "this_ext":     "(ce gestionnaire)",
        "no_active":    "Aucune extension active",
        "no_disabled":  "Aucune extension désactivée",
        "restart_warn": "⚠ Redémarrer Nautilus fermera toutes les fenêtres.",
    }
else:
    T = {
        "menu_label":   "Manage extensions",
        "title":        "Extensions Manager",
        "active":       "Active",
        "disabled":     "Disabled",
        "enable":       "Enable",
        "disable":      "Disable",
        "restart":      "Restart Nautilus",
        "restart_msg":  "Nautilus will restart to apply changes.",
        "confirm":      "Confirm",
        "cancel":       "Cancel",
        "this_ext":     "(this manager)",
        "no_active":    "No active extensions",
        "no_disabled":  "No disabled extensions",
        "restart_warn": "⚠ Restarting Nautilus will close all windows.",
    }

EXTENSIONS_DIR = os.path.expanduser("~/.local/share/nautilus-python/extensions")
DISABLED_DIR   = os.path.join(EXTENSIONS_DIR, "disabled")
THIS_EXT       = os.path.basename(__file__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    return app.get_active_window()

EXCLUDED = {"nautilus-gsconnect.py", "extensions-manager.py"}

def _get_extensions(directory):
    """Liste les fichiers .py dans un dossier."""
    if not os.path.isdir(directory):
        return []
    return sorted([
        f for f in os.listdir(directory)
        if f.endswith(".py")
        and not f.startswith("__")
        and f not in EXCLUDED
    ])

def _ensure_disabled_dir():
    os.makedirs(DISABLED_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Extension row widget
# ---------------------------------------------------------------------------

class ExtRow(Gtk.Box):
    __gtype_name__ = "ExtRow"

    def __init__(self, filename, is_active, on_toggle):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # Icône
        if is_active:
            # Icône type MIME Python — comme dans Nautilus
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            icon  = Gtk.Image()
            icon.set_pixel_size(16)
            for iname in ["text-x-python", "text-x-script", "text-plain"]:
                if theme.has_icon(iname):
                    paint = theme.lookup_icon(iname, None, 16, 1,
                        Gtk.TextDirection.LTR, Gtk.IconLookupFlags.FORCE_REGULAR)
                    icon.set_from_paintable(paint)
                    break
        else:
            icon = Gtk.Image.new_from_icon_name("process-stop-symbolic")
            icon.set_pixel_size(16)
            icon.add_css_class("dim-label")
        self.append(icon)

        # Nom
        name = filename.replace(".py", "").replace("-", " ").title()
        lbl  = Gtk.Label(label=name)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        if filename == THIS_EXT:
            lbl.set_markup(f"<b>{GLib.markup_escape_text(name)}</b> "
                           f"<small>{T['this_ext']}</small>")
        if not is_active:
            lbl.add_css_class("dim-label")
        self.append(lbl)

        # Nom de fichier
        fname_lbl = Gtk.Label(label=filename)
        fname_lbl.add_css_class("dim-label")
        fname_lbl.add_css_class("caption")
        fname_lbl.set_halign(Gtk.Align.END)
        self.append(fname_lbl)

        # Bouton toggle
        if filename != THIS_EXT:
            btn = Gtk.Button(label=T["disable"] if is_active else T["enable"])
            btn.add_css_class("flat")
            if is_active:
                btn.add_css_class("destructive-action")
            else:
                btn.add_css_class("suggested-action")
            btn.connect("clicked", lambda _: on_toggle(filename, is_active))
            self.append(btn)

# ---------------------------------------------------------------------------
# Manager Window
# ---------------------------------------------------------------------------

class ExtManagerWindow(Adw.Window):
    __gtype_name__ = "ExtManagerWindow"

    def __init__(self):
        super().__init__(title=T["title"])
        self.set_default_size(560, -1)
        self.set_resizable(True)
        self.set_transient_for(_nautilus_window())

        tv = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_decoration_layout(":close")
        header.set_title_widget(Gtk.Label(label=T["title"]))
        tv.add_top_bar(header)

        # Contenu principal
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.append(self._content)

        # Bouton redémarrer
        main.append(Gtk.Separator())
        bottom = Gtk.Box(spacing=8)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)
        bottom.set_margin_top(8)
        bottom.set_margin_bottom(8)

        warn = Gtk.Label(label=T["restart_warn"])
        warn.add_css_class("dim-label")
        warn.add_css_class("caption")
        warn.set_hexpand(True)
        warn.set_halign(Gtk.Align.START)
        warn.set_wrap(True)
        bottom.append(warn)

        restart_btn = Gtk.Button(label=T["restart"])
        restart_btn.add_css_class("suggested-action")
        restart_btn.connect("clicked", self._on_restart)
        bottom.append(restart_btn)
        main.append(bottom)

        tv.set_content(main)
        self.set_content(tv)

        self._populate()

    def _populate(self):
        # Vider
        while True:
            child = self._content.get_first_child()
            if child is None:
                break
            self._content.remove(child)

        _ensure_disabled_dir()
        active   = _get_extensions(EXTENSIONS_DIR)
        disabled = _get_extensions(DISABLED_DIR)

        # Section Active
        self._content.append(self._section_header(T["active"], len(active)))
        if active:
            for f in active:
                row = ExtRow(f, True, self._on_toggle)
                self._content.append(row)
                self._content.append(Gtk.Separator())
        else:
            lbl = Gtk.Label(label=T["no_active"])
            lbl.set_margin_top(12)
            lbl.set_margin_bottom(12)
            lbl.add_css_class("dim-label")
            self._content.append(lbl)

        # Séparateur entre sections
        sep = Gtk.Separator()
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        self._content.append(sep)

        # Section Désactivées
        self._content.append(self._section_header(T["disabled"], len(disabled)))
        if disabled:
            for f in disabled:
                row = ExtRow(f, False, self._on_toggle)
                self._content.append(row)
                self._content.append(Gtk.Separator())
        else:
            lbl = Gtk.Label(label=T["no_disabled"])
            lbl.set_margin_top(12)
            lbl.set_margin_bottom(12)
            lbl.add_css_class("dim-label")
            self._content.append(lbl)

    def _section_header(self, title, count):
        box = Gtk.Box(spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(4)

        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        box.append(lbl)

        badge = Gtk.Label(label=str(count))
        badge.add_css_class("dim-label")
        badge.add_css_class("caption")
        box.append(badge)
        return box

    def _on_toggle(self, filename, is_active):
        _ensure_disabled_dir()
        if is_active:
            # Désactiver → déplacer vers disabled/
            src = os.path.join(EXTENSIONS_DIR, filename)
            dst = os.path.join(DISABLED_DIR,   filename)
        else:
            # Activer → déplacer vers extensions/
            src = os.path.join(DISABLED_DIR,   filename)
            dst = os.path.join(EXTENSIONS_DIR, filename)
        try:
            shutil.move(src, dst)
            # Nettoyer le cache
            for d in [EXTENSIONS_DIR, DISABLED_DIR]:
                cache = os.path.join(d, "__pycache__")
                if os.path.isdir(cache):
                    shutil.rmtree(cache)
        except Exception as e:
            dlg = Adw.MessageDialog(transient_for=self, heading="Erreur", body=str(e))
            dlg.add_response("ok", "OK")
            dlg.present()
            return
        # Rafraîchir la liste
        self._populate()

    def _on_restart(self, _):
        dlg = Adw.MessageDialog(
            transient_for=self,
            heading=T["restart"],
            body=T["restart_msg"])
        dlg.add_response("cancel", T["cancel"])
        dlg.add_response("ok",     T["confirm"])
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.connect("response", self._do_restart)
        dlg.present()

    def _do_restart(self, dlg, response):
        if response != "ok":
            return
        self.close()
        GLib.timeout_add(200, self._restart_nautilus)

    def _restart_nautilus(self):
        # Lancer le nouveau Nautilus en arrière-plan AVANT de tuer l'actuel
        subprocess.Popen(["bash", "-c",
            "sleep 0.8 && nautilus &"
        ])
        # Tuer proprement le process actuel
        subprocess.Popen(["nautilus", "-q"])
        return False

# ---------------------------------------------------------------------------
# Nautilus extension
# ---------------------------------------------------------------------------

class ExtManagerExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "ExtManagerExtension"

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        item = Nautilus.MenuItem(
            name="ExtManager::Open",
            label=T["menu_label"],
            tip="Manage Nautilus Python extensions",
            icon="puzzle-piece-symbolic",
        )
        item.connect("activate", lambda *_: ExtManagerWindow().present())
        return [item]
