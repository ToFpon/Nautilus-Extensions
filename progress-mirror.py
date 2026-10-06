#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Progress Mirror — Nautilus Python Extension
# DESC: Affiche automatiquement une petite fenêtre devant Nautilus pendant les
#       copies/déplacements un peu longs, en recopiant (lecture seule) la
#       progression des widgets natifs de la bulle. Le cercle de progression
#       natif n'est pas touché.
# LICENSE: GNU General Public License v3.0
#
# PREMIER JET -- non testé sur une vraie version de Nautilus : les hypothèses
# sur la structure interne (voir "HYPOTHÈSES" plus bas) sont à valider avec
# l'inspecteur GTK (GTK_DEBUG=interactive nautilus) ou avec DEBUG = True.
#
# INSTALL:
#   cp progress-mirror.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q
#
# HYPOTHÈSES (d'après nautilus-progress-info-widget.c, à confirmer) :
#   1. Une opération = un widget de type "NautilusProgressInfoWidget", présent
#      dans l'arbre des widgets de la fenêtre Nautilus (dans le popover).
#   2. Ses enfants : un Gtk.ProgressBar, deux Gtk.Label (dans l'ordre : statut,
#      puis détails) et un Gtk.Button (annulation).
#   3. Il y a deux indicateurs dans Nautilus (barre d'en-tête et barre du bas
#      pour les fenêtres étroites) : la même opération apparaît donc deux fois.
#      On dédoublonne sur le texte du statut.

import gi
import time
import locale

gi.require_version("Nautilus", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Nautilus, GObject, Gtk, Adw, GLib, Pango

# ---------------------------------------------------------------------------
# Réglages
# ---------------------------------------------------------------------------
DEBUG       = False   # True : affiche dans le terminal les types "Progress" trouvés
TICK_MS     = 250     # fréquence de lecture des widgets natifs
SHOW_DELAY  = 0.5     # secondes : n'affiche la boîte que si l'opération dure
                      # plus longtemps (évite le clignotement sur NVMe)
NATIVE_TYPE = "NautilusProgressInfoWidget"

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""
if _lang.startswith("fr"):
    T = {"title": "Opérations en cours", "cancel": "Annuler"}
elif _lang.startswith("de"):
    T = {"title": "Laufende Vorgänge", "cancel": "Abbrechen"}
else:
    T = {"title": "File operations", "cancel": "Cancel"}


# ---------------------------------------------------------------------------
# Lecture des widgets natifs
# ---------------------------------------------------------------------------
def _collect_natives(widget, out):
    if type(widget).__name__ == NATIVE_TYPE:
        out.append(widget)
        return
    child = widget.get_first_child()
    while child:
        _collect_natives(child, out)
        child = child.get_next_sibling()


def _gather(widget, labels, bars, buttons):
    if isinstance(widget, Gtk.Label):
        labels.append(widget)
    elif isinstance(widget, Gtk.ProgressBar):
        bars.append(widget)
    elif isinstance(widget, Gtk.Button):
        buttons.append(widget)
    child = widget.get_first_child()
    while child:
        _gather(child, labels, bars, buttons)
        child = child.get_next_sibling()


class _Info:
    """Instantané de l'état d'une opération, lu sur le widget natif."""

    def __init__(self, native):
        labels, bars, buttons = [], [], []
        _gather(native, labels, bars, buttons)
        self.status   = labels[0].get_text() if labels else ""
        self.details  = labels[1].get_text() if len(labels) > 1 else ""
        self.fraction = bars[0].get_fraction() if bars else 0.0
        self.button   = buttons[0] if buttons else None
        self.key      = self.status          # clé de dédoublonnage
        self.done     = self.fraction >= 0.999


def _debug_dump(window):
    seen = set()

    def walk(w, depth=0):
        name = type(w).__name__
        if "Progress" in name and (name, depth) not in seen:
            seen.add((name, depth))
            print(f"[progress-mirror] {'  ' * depth}{name}")
        child = w.get_first_child()
        while child:
            walk(child, depth + 1)
            child = child.get_next_sibling()

    walk(window)


# ---------------------------------------------------------------------------
# Centrage sur la fenêtre Nautilus (X11)
# ---------------------------------------------------------------------------
def _center_on_parent_x11(win, parent):
    """GTK4 n'offre aucune API pour positionner une fenêtre de premier niveau,
    et Mutter ne centre pas ces fenêtres sur leur parent. Sous X11, on la
    déplace donc à la main via Xlib (ctypes, connexion X séparée). Sous
    Wayland (ou si quoi que ce soit manque) : ne fait rien, sans erreur."""
    try:
        import ctypes
        import ctypes.util
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11

        s_win, s_par = win.get_surface(), parent.get_surface()
        if not (isinstance(s_win, GdkX11.X11Surface)
                and isinstance(s_par, GdkX11.X11Surface)):
            return
        lib = ctypes.util.find_library("X11")
        if not lib:
            return

        c = ctypes
        x11 = c.CDLL(lib)
        x11.XOpenDisplay.restype = c.c_void_p
        x11.XOpenDisplay.argtypes = [c.c_char_p]
        x11.XDefaultRootWindow.restype = c.c_ulong
        x11.XDefaultRootWindow.argtypes = [c.c_void_p]
        x11.XGetGeometry.restype = c.c_int
        x11.XGetGeometry.argtypes = [
            c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong),
            c.POINTER(c.c_int), c.POINTER(c.c_int),
            c.POINTER(c.c_uint), c.POINTER(c.c_uint),
            c.POINTER(c.c_uint), c.POINTER(c.c_uint)]
        x11.XTranslateCoordinates.restype = c.c_int
        x11.XTranslateCoordinates.argtypes = [
            c.c_void_p, c.c_ulong, c.c_ulong, c.c_int, c.c_int,
            c.POINTER(c.c_int), c.POINTER(c.c_int), c.POINTER(c.c_ulong)]
        x11.XMoveWindow.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int]
        x11.XFlush.argtypes = [c.c_void_p]
        x11.XCloseDisplay.argtypes = [c.c_void_p]

        dpy = x11.XOpenDisplay(None)
        if not dpy:
            return
        try:
            def size_of(xid):
                root = c.c_ulong()
                x, y = c.c_int(), c.c_int()
                w, h, bw, depth = c.c_uint(), c.c_uint(), c.c_uint(), c.c_uint()
                x11.XGetGeometry(dpy, xid, c.byref(root), c.byref(x), c.byref(y),
                                 c.byref(w), c.byref(h), c.byref(bw), c.byref(depth))
                return w.value, h.value

            xid_win, xid_par = s_win.get_xid(), s_par.get_xid()
            ox, oy = c.c_int(), c.c_int()
            child = c.c_ulong()
            x11.XTranslateCoordinates(dpy, xid_par, x11.XDefaultRootWindow(dpy),
                                      0, 0, c.byref(ox), c.byref(oy), c.byref(child))
            pw, ph = size_of(xid_par)
            ww, wh = size_of(xid_win)
            x11.XMoveWindow(dpy, xid_win,
                            ox.value + (pw - ww) // 2,
                            oy.value + (ph - wh) // 2)
            x11.XFlush(dpy)
        finally:
            x11.XCloseDisplay(dpy)
    except Exception as exc:
        if DEBUG:
            print(f"[progress-mirror] centrage impossible : {exc}")


# ---------------------------------------------------------------------------
# Fenêtre miroir
# ---------------------------------------------------------------------------
class _MirrorRow:
    def __init__(self, on_cancel):
        self.native_button = None

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left.set_hexpand(True)

        self.status = Gtk.Label(xalign=0.0)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.status.set_max_width_chars(45)
        left.append(self.status)

        self.bar = Gtk.ProgressBar()
        self.bar.set_hexpand(True)
        left.append(self.bar)

        self.details = Gtk.Label(xalign=0.0)
        self.details.add_css_class("dim-label")
        self.details.add_css_class("caption")
        left.append(self.details)

        self.box.append(left)

        self.cancel = Gtk.Button.new_from_icon_name("window-close-symbolic")
        self.cancel.set_tooltip_text(T["cancel"])
        self.cancel.set_valign(Gtk.Align.CENTER)
        self.cancel.add_css_class("circular")
        self.cancel.connect("clicked", lambda _b: on_cancel(self))
        self.box.append(self.cancel)

    def update(self, info):
        self.native_button = info.button
        self.status.set_text(info.status)
        self.details.set_text(info.details)
        if info.fraction <= 0.0:
            self.bar.pulse()                   # mode "activité" (pas de fraction connue)
        else:
            self.bar.set_fraction(min(info.fraction, 1.0))


class _MirrorWindow(Adw.Window):
    __gtype_name__ = "ProgressMirrorWindow"

    def __init__(self, on_user_close):
        super().__init__(title=T["title"])
        self.set_default_size(420, -1)
        self.set_resizable(False)
        self._rows = {}
        self._on_user_close = on_user_close

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(self._list, f"set_margin_{side}")(16)

        # Adw.Window + ToolbarView : mêmes coins arrondis que tes autres
        # outils (un Gtk.Window nu ne les reçoit pas du thème).
        header = Adw.HeaderBar()
        header.set_decoration_layout(":close")
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self._list)
        self.set_content(toolbar)

        self.connect("close-request", self._on_close)

    def _on_close(self, _win):
        # L'utilisateur ferme la boîte : on la masque et on mémorise les
        # opérations en cours pour ne pas la rouvrir à chaque tick.
        self._on_user_close(set(self._rows))
        self.set_visible(False)
        return True

    def _cancel(self, row):
        # Annulation relayée au bouton natif : Nautilus gère le GCancellable.
        if row.native_button is not None:
            try:
                row.native_button.emit("clicked")
            except Exception:
                pass

    def sync(self, active):
        """active : dict clé -> _Info. Met à jour, ajoute, retire les lignes."""
        for key in list(self._rows):
            if key not in active:
                self._list.remove(self._rows.pop(key).box)
        for key, info in active.items():
            row = self._rows.get(key)
            if row is None:
                row = _MirrorRow(self._cancel)
                self._rows[key] = row
                self._list.append(row.box)
            row.update(info)

    def is_empty(self):
        return not self._rows


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------
class ProgressMirror(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "ProgressMirror"

    def __init__(self):
        super().__init__()
        self._first_seen = {}     # clé -> instant de première apparition
        self._dismissed  = set()  # clés fermées à la main par l'utilisateur
        self._win        = None   # référence forte, sinon le ramasse-miettes la ferme
        self._debug_done = False
        GLib.timeout_add(TICK_MS, self._tick)

    def _dismiss(self, keys):
        self._dismissed |= keys

    def _tick(self):
        seen, parent = {}, None
        for win in Gtk.Window.list_toplevels():
            if "Nautilus" not in type(win).__name__:
                continue
            if DEBUG and not self._debug_done:
                _debug_dump(win)
            natives = []
            _collect_natives(win, natives)
            for native in natives:
                info = _Info(native)
                if info.key and info.key not in seen:   # dédoublonnage
                    seen[info.key] = info
                    parent = parent or win
        self._debug_done = True

        now = time.monotonic()
        for key in seen:
            self._first_seen.setdefault(key, now)
        for key in list(self._first_seen):
            if key not in seen:                          # opération disparue
                del self._first_seen[key]
                self._dismissed.discard(key)

        active = {
            k: v for k, v in seen.items()
            if not v.done
            and k not in self._dismissed
            and now - self._first_seen[k] >= SHOW_DELAY
        }
        self._update_window(active, parent)
        return True

    def _update_window(self, active, parent):
        if not active:
            if self._win is not None and self._win.get_visible():
                self._win.sync({})
                self._win.set_visible(False)
            return
        if self._win is None:
            self._win = _MirrorWindow(self._dismiss)
        self._win.sync(active)
        if not self._win.get_visible():
            if parent is not None:
                self._win.set_transient_for(parent)   # ici voulu : comportement "dialogue"
            self._win.present()
            if parent is not None:
                # Laisser le temps à la fenêtre d'être affichée avant de la déplacer.
                GLib.timeout_add(120, self._center, parent)

    def _center(self, parent):
        if self._win is not None and self._win.get_visible():
            _center_on_parent_x11(self._win, parent)
        return False

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        return []
