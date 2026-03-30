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
# NAME: Hidden Files Dimmer (icon + label)
# DESC: Dims icons AND labels of hidden files (dot-prefixed) in Nautilus
# INSTALL:
#   cp hidden-dim-all.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q

import gi
gi.require_version("Nautilus", "4.0")
gi.require_version("Gtk",     "4.0")
from gi.repository import Nautilus, GObject, Gtk, GLib, Gio

DIM_OPACITY = 0.6
DIM_COLOR   = "#c0bfbc"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _walk(widget):
    if isinstance(widget, Gtk.Label):
        text = widget.get_text()
        if text.startswith(".") and len(text) > 1:
            # Dim label
            widget.set_markup(
                f'<span foreground="{DIM_COLOR}">'
                f'{GLib.markup_escape_text(text)}</span>')
            # Dim parent cell (icône + label)
            parent = widget.get_parent()
            for _ in range(10):
                if parent is None:
                    break
                if any(x in type(parent).__name__
                       for x in ("ViewCell", "FlowBoxChild",
                                 "GridCell", "Thumbnail", "CanvasItem")):
                    current = parent.get_opacity()
                    if abs(current - DIM_OPACITY) > 0.01:
                        parent.set_opacity(DIM_OPACITY)
                    break
                parent = parent.get_parent()

    child = widget.get_first_child()
    while child:
        _walk(child)
        child = child.get_next_sibling()


def _walk_all_windows(app):
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
    __gtype_name__ = "HiddenFileDimmerAll"

    def __init__(self):
        super().__init__()
        self._app      = Gtk.Application.get_default()
        self._monitors = []
        self._pending  = False

        # Walk initial
        GLib.timeout_add(300, self._initial_walk)

        # Surveiller le home pour les changements filesystem
        self._watch(GLib.get_home_dir())

        # Timer léger pour capter les changements de vue liste↔grille
        GLib.timeout_add(600, self._view_tick)

    def _initial_walk(self):
        _walk_all_windows(self._app)
        return False

    def _view_tick(self):
        _walk_all_windows(self._app)
        return True

    def _watch(self, path):
        try:
            gfile   = Gio.File.new_for_path(path)
            monitor = gfile.monitor_directory(
                Gio.FileMonitorFlags.NONE, None)
            monitor.connect("changed", self._on_fs_changed)
            self._monitors.append(monitor)
        except Exception:
            pass

    def _on_fs_changed(self, monitor, file, other, event):
        if self._pending:
            return
        self._pending = True
        GLib.timeout_add(250, self._deferred_walk)

    def _deferred_walk(self):
        _walk_all_windows(self._app)
        self._pending = False
        return False

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        GLib.timeout_add(150, self._deferred_walk)
        return []
