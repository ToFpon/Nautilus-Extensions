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
# NAME: Hidden Files Dimmer (icon only)
# DESC: Dims icons of hidden files (dot-prefixed) in Nautilus
# INSTALL:
#   cp hidden-dim-icon.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q

import gi
gi.require_version("Nautilus", "4.0")
gi.require_version("Gtk",     "4.0")
from gi.repository import Nautilus, GObject, Gtk, GLib, Gio

# Opacité appliquée aux icônes des fichiers cachés
DIM_OPACITY = 0.35

# ---------------------------------------------------------------------------
# Helpers — parcours ciblé de l'arbre GTK
# ---------------------------------------------------------------------------

def _first_picture(widget):
    if isinstance(widget, Gtk.Picture):
        return widget
    child = widget.get_first_child()
    while child:
        r = _first_picture(child)
        if r:
            return r
        child = child.get_next_sibling()
    return None


def _first_label_text(widget):
    if isinstance(widget, Gtk.Label):
        return widget.get_text()
    child = widget.get_first_child()
    while child:
        r = _first_label_text(child)
        if r:
            return r
        child = child.get_next_sibling()
    return None


def _process_cell(cell):
    text = _first_label_text(cell)
    if text is None:
        return
    is_hidden = text.startswith(".") and len(text) > 1
    pic       = _first_picture(cell)
    if pic is None:
        return
    current = pic.get_opacity()
    target  = DIM_OPACITY if is_hidden else 1.0
    if abs(current - target) > 0.01:
        pic.set_opacity(target)


def _walk(widget):
    name = type(widget).__name__
    if name in ("NautilusNameCell", "NautilusGridCell"):
        _process_cell(widget)
        return
    child = widget.get_first_child()
    while child:
        _walk(child)
        child = child.get_next_sibling()


def _walk_all_windows(app):
    """Walk toutes les fenêtres Nautilus."""
    if app is not None:
        windows = app.get_windows()
    else:
        windows = [w for w in Gtk.Window.list_toplevels()
                   if "Nautilus" in type(w).__name__]
    for win in windows:
        _walk(win)

# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

class HiddenFileDimmer(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "HiddenFileDimmer"

    def __init__(self):
        super().__init__()
        self._app      = Gtk.Application.get_default()
        self._monitors = []   # GFileMonitor actifs
        self._pending  = False  # un seul walk schedulé à la fois

        # Walk initial — court délai pour laisser Nautilus finir son rendu
        GLib.timeout_add(300, self._initial_walk)

        # Surveiller le home pour les changements filesystem
        self._watch(GLib.get_home_dir())

        # Timer léger pour capter les changements de vue liste↔grille
        GLib.timeout_add(600, self._view_tick)

    def _initial_walk(self):
        """Premier passage au démarrage."""
        _walk_all_windows(self._app)
        return False  # one-shot

    def _view_tick(self):
        """Timer léger — reapplique le dim à chaque tick pour capter les changements de vue."""
        _walk_all_windows(self._app)
        return True  # continuer

    def _watch(self, path):
        """Installe un GFileMonitor sur un dossier."""
        try:
            gfile   = Gio.File.new_for_path(path)
            monitor = gfile.monitor_directory(
                Gio.FileMonitorFlags.NONE, None)
            monitor.connect("changed", self._on_fs_changed)
            self._monitors.append(monitor)  # garder en vie
        except Exception:
            pass

    def _on_fs_changed(self, monitor, file, other, event):
        """Filesystem changé → walk différé pour laisser Nautilus se mettre à jour."""
        if self._pending:
            return
        self._pending = True
        GLib.timeout_add(250, self._deferred_walk)

    def _deferred_walk(self):
        """Walk déclenché après un changement filesystem."""
        _walk_all_windows(self._app)
        self._pending = False
        return False  # one-shot

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        # Navigation vers un nouveau dossier → walk immédiat
        # (léger délai pour laisser Nautilus rendre la nouvelle vue)
        GLib.timeout_add(150, self._deferred_walk)
        return []
