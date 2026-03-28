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
from gi.repository import Nautilus, GObject, Gtk, GLib

# Opacité appliquée aux icônes des fichiers cachés
DIM_OPACITY  = 0.35
# Intervalle du timer en ms — assez long pour ne pas peser sur le CPU
TICK_MS      = 800
# Attribut marqueur pour éviter de retraiter un widget déjà traité
_MARKER      = "_hdim_done"


# ---------------------------------------------------------------------------
# Helpers — parcours ciblé de l'arbre GTK
# ---------------------------------------------------------------------------

def _first_picture(widget):
    """Retourne le premier Gtk.Picture trouvé sous widget, ou None."""
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
    """Retourne le texte du premier Gtk.Label trouvé, ou None."""
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
    """Applique ou retire le dim sur une NautilusNameCell/NautilusGridCell.
    Retourne True si le widget était déjà traité (court-circuit possible)."""
    # On relit le label à chaque fois — la cellule est recyclée par GTK
    text = _first_label_text(cell)
    if text is None:
        return

    is_hidden = text.startswith(".") and len(text) > 1
    pic       = _first_picture(cell)
    if pic is None:
        return

    # Appliquer seulement si l'opacité doit changer — évite les redraws inutiles
    current = pic.get_opacity()
    target  = DIM_OPACITY if is_hidden else 1.0
    if abs(current - target) > 0.01:
        pic.set_opacity(target)


def _walk(widget):
    """Parcourt l'arbre en s'arrêtant dès qu'on trouve une cellule Nautilus."""
    name = type(widget).__name__

    if name in ("NautilusNameCell", "NautilusGridCell"):
        _process_cell(widget)
        return          # pas besoin de descendre plus bas

    child = widget.get_first_child()
    while child:
        _walk(child)
        child = child.get_next_sibling()


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

class HiddenFileDimmer(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "HiddenFileDimmer"

    def __init__(self):
        super().__init__()
        self._app = Gtk.Application.get_default()
        GLib.timeout_add(TICK_MS, self._tick)

    def _tick(self):
        # Utiliser get_windows() si dispo (plus ciblé que list_toplevels)
        if self._app is not None:
            windows = self._app.get_windows()
        else:
            # Fallback : filtrer les toplevel Nautilus
            windows = [w for w in Gtk.Window.list_toplevels()
                       if "Nautilus" in type(w).__name__]

        for win in windows:
            _walk(win)
        return True     # continuer le timer

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        return []
