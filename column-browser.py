#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Column Browser — Nautilus Python Extension
# DESC: Fast Miller-columns (macOS Finder style) folder browser, standalone
#       window launched from Nautilus. Extracted from Dual Panel's column
#       view mode — kept single-pane on purpose: this tool is for browsing
#       fast, not for copy/move (Dual Panel already does that).
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
# REQUIRES: python3-nautilus (>= 4.0), python3-gi, gir1.2-adw-1
# INSTALL:
#   cp column-browser.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import locale

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
        "menu_label": "Spaltenansicht öffnen",
        "title":      "Spaltenansicht",
        "go_up":      "Übergeordneter Ordner",
        "refresh":    "Neu laden",
        "err_title":  "Fehler",
    }
elif _lang.startswith("fr"):
    T = {
        "menu_label": "Ouvrir en vue colonnes",
        "title":      "Vue Colonnes",
        "go_up":      "Dossier parent",
        "refresh":    "Actualiser",
        "err_title":  "Erreur",
    }
else:
    T = {
        "menu_label": "Open in column view",
        "title":      "Column Browser",
        "go_up":      "Parent folder",
        "refresh":    "Refresh",
        "err_title":  "Error",
    }

# ---------------------------------------------------------------------------
# Helpers (dupliqués depuis dual-panel.py — chaque extension Nautilus est
# chargée comme un module isolé, pas d'import propre possible entre les deux
# sans dépendance d'ordre de chargement fragile).
# ---------------------------------------------------------------------------

_EXTENSIONS_DIR = os.path.expanduser("~/.local/share/nautilus-python/extensions")
_DIM_OPACITY    = 0.35


def _hidden_dim_active():
    """Retourne True si hidden-dim-icon.py ou hidden-dim-all.py est actif."""
    return (os.path.isfile(os.path.join(_EXTENSIONS_DIR, "hidden-dim-icon.py")) or
            os.path.isfile(os.path.join(_EXTENSIONS_DIR, "hidden-dim-all.py")))


def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    win = app.get_active_window()
    return win or (app.get_windows()[0] if app.get_windows() else None)


def _icon_for(path, is_dir):
    """Retourne l'icône régulière du thème pour un fichier ou dossier."""
    try:
        if is_dir:
            gfile = Gio.File.new_for_path(path)
            info  = gfile.query_info("standard::icon", 0, None)
            gicon = info.get_icon()
            if gicon:
                theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
                names = gicon.get_names() if hasattr(gicon, "get_names") else []
                for name in names:
                    if theme.has_icon(name):
                        return name
            return "folder"
        else:
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


def _resolve_column_icon() -> str:
    """'view-column-symbolic' est absente de certains thèmes (Adwaita depuis
    GNOME 48) -- repli sur 'view-dual-symbolic', déjà utilisée par Dual Panel
    et confirmée présente dans les thèmes courants."""
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    return "view-column-symbolic" if theme.has_icon("view-column-symbolic") else "view-dual-symbolic"


class FileEntry(GObject.Object):
    __gtype_name__ = "ColumnBrowserFileEntry"

    def __init__(self, path, is_dir=None):
        super().__init__()
        self.path = path
        self.name = os.path.basename(path)
        # is_dir peut être fourni par l'appelant -- MillerColumn le connaît
        # déjà via DirEntry.is_dir() (qui réutilise le d_type du readdir(),
        # sans stat() supplémentaire). Sinon on le calcule nous-mêmes.
        self.is_dir = os.path.isdir(path) if is_dir is None else is_dir


# ---------------------------------------------------------------------------
# Miller Columns — même logique que dans Dual Panel, sans dépendance à un
# FilePanel : le "owner" ici est directement la fenêtre ColumnBrowserWindow.
# ---------------------------------------------------------------------------

MILLER_COLUMN_WIDTH_DEFAULT = 220
MILLER_COLUMN_MIN_WIDTH     = 120
MILLER_COLUMN_MAX_WIDTH     = 640
MILLER_WINDOW_MIN_WIDTH     = 640   # jamais plus étroit qu'~2-3 colonnes, même à 1 seule colonne ouverte


def _make_miller_sorter() -> Gtk.CustomSorter:
    """Dossiers d'abord, cachés groupés après les visibles, puis alpha --
    même logique que dual-panel, en plus simple (une seule colonne, pas de
    choix de clé de tri)."""
    def compare(a, b, *_):
        a_hidden = a.name.startswith(".")
        b_hidden = b.name.startswith(".")
        def group(e, hidden):
            return (0 if not hidden else 1) if e.is_dir else (2 if not hidden else 3)
        ga, gb = group(a, a_hidden), group(b, b_hidden)
        if ga != gb:
            return Gtk.Ordering.SMALLER if ga < gb else Gtk.Ordering.LARGER
        na, nb = a.name.lower(), b.name.lower()
        if na < nb: return Gtk.Ordering.SMALLER
        if na > nb: return Gtk.Ordering.LARGER
        return Gtk.Ordering.EQUAL
    return Gtk.CustomSorter.new(compare)


class MillerColumn(Gtk.Box):
    """Une colonne unique du chemin Miller : liste le contenu d'un dossier.
    Ne connaît rien des colonnes voisines — sélectionner une ligne prévient
    juste le parent (MillerColumnsView) via on_select, qui décide seul
    d'ajouter une colonne ou de tronquer la chaîne."""

    __gtype_name__ = "ColumnBrowserMillerColumn"

    def __init__(self, dir_path: str, on_select, width: int = MILLER_COLUMN_WIDTH_DEFAULT):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.dir_path      = dir_path
        self._on_select    = on_select
        self.current_width = width   # source de vérité pour le calcul de largeur fenêtre
        self._load_gen     = 0
        self.set_size_request(width, -1)

        self._store = Gio.ListStore(item_type=FileEntry)
        # Tri synchrone (pas incrémental) : les lots arrivent maintenant en
        # ordre brut du système de fichiers via l'énumération GIO -- un tri
        # incrémental continuerait à réordonner après le dernier lot et
        # ferait dériver le défilement (constaté et corrigé sur dual-panel).
        self._sort_model = Gtk.SortListModel.new(self._store, _make_miller_sorter())
        self._sort_model.set_incremental(False)
        self._selection = Gtk.SingleSelection(model=self._sort_model)
        # Sans ça, GTK sélectionne automatiquement la première ligne dès le
        # chargement -> drill-down involontaire dans le premier dossier venu.
        self._selection.set_autoselect(False)
        self._selection.connect("selection-changed", self._on_selection_changed)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_row)
        factory.connect("bind",  self._bind_row)

        self._list_view = Gtk.ListView(model=self._selection, factory=factory)
        self._list_view.add_css_class("navigation-sidebar")
        self._list_view.connect("activate", self._on_row_activate)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(self._list_view)
        self.append(scroller)

        self._load()

    # -- Chargement -----------------------------------------------------------

    def _load(self):
        # Listing asynchrone via GIO -- exactement le mécanisme du vrai
        # Nautilus (Gio.File.enumerate_children_async), et non plus un
        # threading.Thread + os.scandir()/stat() bloquants. Ce dernier
        # pattern s'est avéré pathologiquement lent sur certaines machines
        # pour des raisons jamais totalement élucidées (voir l'historique
        # de debug sur dual-panel : py-spy, cgroup/PSI, ordonnancement et
        # C-states tous vérifiés normaux) -- plutôt que de le contourner,
        # on l'évite entièrement.
        self._load_gen += 1
        my_gen = self._load_gen
        path = self.dir_path

        ATTRS = "standard::name,standard::type"
        BATCH = 200

        gfile = Gio.File.new_for_path(path)

        def on_enum_ready(source, result, _data=None):
            if my_gen != self._load_gen:
                return
            try:
                enumerator = source.enumerate_children_finish(result)
            except GLib.Error as exc:
                print(f"[column-browser] enumerate_children({path}): {exc}")
                return
            request_next_batch(enumerator)

        def request_next_batch(enumerator):
            enumerator.next_files_async(
                BATCH, GLib.PRIORITY_DEFAULT, None, on_batch_ready, enumerator)

        def on_batch_ready(enumerator, result, _data=None):
            if my_gen != self._load_gen:
                return
            try:
                infos = enumerator.next_files_finish(result)
            except GLib.Error as exc:
                print(f"[column-browser] next_files({path}): {exc}")
                infos = []

            if not infos:
                enumerator.close_async(GLib.PRIORITY_DEFAULT, None, lambda *a: None)
                return

            entries = []
            for info in infos:
                name = info.get_name()
                is_dir = info.get_file_type() == Gio.FileType.DIRECTORY
                entries.append(FileEntry(os.path.join(path, name), is_dir))

            n = self._store.get_n_items()
            self._store.splice(n, 0, entries)
            request_next_batch(enumerator)

        # Repartir d'une colonne vide à chaque (re)chargement -- refresh()
        # peut être appelé plusieurs fois (F5) sur la même colonne.
        self._store.remove_all()
        gfile.enumerate_children_async(
            ATTRS, Gio.FileQueryInfoFlags.NONE, GLib.PRIORITY_DEFAULT,
            None, on_enum_ready, None)

    def refresh(self):
        """Recharge le contenu sans toucher à la sélection/à la chaîne (F5)."""
        self._load()

    # -- Rendu ------------------------------------------------------------------

    def _setup_row(self, factory, item):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(6); box.set_margin_end(4)
        box.set_margin_top(2);   box.set_margin_bottom(2)
        icon = Gtk.Image()
        icon.set_icon_size(Gtk.IconSize.NORMAL)
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.set_hexpand(True)
        chevron = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        chevron.set_pixel_size(12)
        chevron.add_css_class("miller-chevron")
        box.append(icon); box.append(lbl); box.append(chevron)
        item.set_child(box)

    def _bind_row(self, factory, item):
        entry = item.get_item()
        box     = item.get_child()
        icon    = box.get_first_child()
        lbl     = icon.get_next_sibling()
        chevron = lbl.get_next_sibling()

        icon_name = _icon_for(entry.path, entry.is_dir)
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        if theme.has_icon(icon_name):
            paintable = theme.lookup_icon(
                icon_name, None, 20, 1,
                Gtk.TextDirection.NONE, Gtk.IconLookupFlags.FORCE_REGULAR)
            icon.set_from_paintable(paintable)
        else:
            icon.set_from_icon_name(icon_name)
        lbl.set_text(entry.name)
        chevron.set_visible(entry.is_dir)

        is_hidden = entry.name.startswith(".") and len(entry.name) > 1
        if _hidden_dim_active() and is_hidden:
            icon.set_opacity(_DIM_OPACITY)
            lbl.add_css_class("dim-label")
        else:
            icon.set_opacity(1.0)
            lbl.remove_css_class("dim-label")

    # -- Événements ---------------------------------------------------------------

    def _on_selection_changed(self, selection, *_a):
        pos = selection.get_selected()
        entry = self._sort_model.get_item(pos) if pos != Gtk.INVALID_LIST_POSITION else None
        self._on_select(self, entry)

    def _on_row_activate(self, list_view, position):
        # Le drill-down des dossiers passe déjà par selection-changed (le
        # simple clic sélectionne avant d'activer) -- ici on ne gère que
        # l'ouverture d'un fichier au double-clic/Entrée.
        entry = self._sort_model.get_item(position)
        if entry and not entry.is_dir:
            try:
                Gio.AppInfo.launch_default_for_uri(f"file://{entry.path}", None)
            except Exception:
                pass


def _make_miller_resize_handle(target_column: "MillerColumn") -> Gtk.Widget:
    """Poignée de 4px entre deux colonnes : le drag redimensionne la colonne
    à sa gauche (target_column). Pas de Gtk.Paned imbriqués -- la chaîne
    s'allonge/se raccourcit trop souvent pour que ce soit gérable à
    reconstruire à chaque clic."""
    handle = Gtk.Box()
    handle.set_size_request(4, -1)
    handle.add_css_class("miller-resize-handle")
    handle.set_cursor(Gdk.Cursor.new_from_name("col-resize", None))

    state = {"start_width": 0}
    drag = Gtk.GestureDrag()

    def on_begin(_g, _x, _y):
        state["start_width"] = target_column.current_width

    def on_update(_g, dx, _dy):
        new_w = int(state["start_width"] + dx)
        new_w = max(MILLER_COLUMN_MIN_WIDTH, min(MILLER_COLUMN_MAX_WIDTH, new_w))
        target_column.set_size_request(new_w, -1)
        target_column.current_width = new_w

    drag.connect("drag-begin", on_begin)
    drag.connect("drag-update", on_update)
    handle.add_controller(drag)
    return handle


class MillerColumnsView(Gtk.ScrolledWindow):
    """Le chemin de colonnes Miller complet. Défilement horizontal pour la
    chaîne ; chaque MillerColumn défile verticalement pour son propre compte."""

    __gtype_name__ = "ColumnBrowserMillerColumnsView"

    def __init__(self, owner: "ColumnBrowserWindow"):
        super().__init__()
        self._owner = owner
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._chain_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(self._chain_box)

        self._columns = []

    # -- Construction de la chaîne ------------------------------------------

    def reset_to(self, path: str):
        for w in list(self._chain_box):
            self._chain_box.remove(w)
        self._columns.clear()
        if os.path.isdir(path):
            self._append_column(path)

    def _append_column(self, path: str, width: int = None) -> "MillerColumn":
        col = MillerColumn(path, on_select=self._on_column_select,
                            width=width or MILLER_COLUMN_WIDTH_DEFAULT)
        if self._columns:
            self._chain_box.append(_make_miller_resize_handle(self._columns[-1]))
        self._chain_box.append(col)
        self._columns.append(col)
        return col

    def _truncate_after(self, column: "MillerColumn"):
        idx = self._columns.index(column)
        del self._columns[idx + 1:]
        children = list(self._chain_box)
        pos = children.index(column)
        for w in children[pos + 1:]:
            self._chain_box.remove(w)

    def refresh_all(self):
        """Recharge chaque colonne ouverte sans casser la chaîne (F5)."""
        for col in self._columns:
            col.refresh()

    def _scroll_to_end(self):
        adj = self.get_hadjustment()
        if adj is not None:
            adj.set_value(adj.get_upper())
        return False

    def _needed_width(self) -> int:
        """Largeur totale de la chaîne actuelle (colonnes + poignées de 4px),
        calculée à partir de current_width -- pas de get_width(), qui n'est
        fiable qu'une fois la fenêtre allouée, ce qui n'est pas garanti juste
        après un append()."""
        cols   = sum(c.current_width for c in self._columns)
        gaps   = 4 * max(0, len(self._columns) - 1)
        return cols + gaps

    # -- Sélection ------------------------------------------------------------

    def _on_column_select(self, column: "MillerColumn", entry):
        self._truncate_after(column)
        if entry is None:
            self._owner._path_changed(column.dir_path)
            self._owner._sync_window_width(self._needed_width())
        elif entry.is_dir:
            self._append_column(entry.path)
            self._owner._path_changed(entry.path)
            # 1) on ajuste la largeur de fenêtre pour montrer la colonne en
            #    entier sans scroll ; 2) si l'écran est trop petit pour ça,
            #    le scroll reste le filet de sécurité.
            self._owner._sync_window_width(self._needed_width())
            GLib.idle_add(self._scroll_to_end)
        else:
            self._owner._path_changed(column.dir_path)
            self._owner._sync_window_width(self._needed_width())
            try:
                Gio.AppInfo.launch_default_for_uri(f"file://{entry.path}", None)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Fenêtre
# ---------------------------------------------------------------------------

# Sans set_transient_for(), rien d'autre ne retient ces fenêtres en Python
# une fois .present() retourné dans l'extension -- sans cette liste, le
# ramasse-miettes pourrait les fermer aussitôt.
_open_windows = []


class ColumnBrowserWindow(Adw.Window):
    __gtype_name__ = "ColumnBrowserWindow"

    def __init__(self, start_path: str):
        super().__init__(title=T["title"])
        self.set_default_size(1100, 650)
        # PAS de set_transient_for() ici : sur Mutter, une fenêtre transiente
        # est traitée comme un dialogue et se voit refuser minimize/maximize
        # au niveau du protocole -- decoration-layout ne peut rien y changer
        # (déjà vécu sur annotate-image.py). En contrepartie, la fenêtre
        # devient indépendante : on la garde en vie via _open_windows,
        # sinon rien n'empêche le ramasse-miettes Python de la fermer juste
        # après le .present() dans get_file_items()/get_background_items().
        _open_windows.append(self)
        self.connect("destroy", lambda w: _open_windows.remove(w) if w in _open_windows else None)
        self._path = start_path

        # ── CSS (poignée de resize + chevron) ──────────────────────────────
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            .miller-resize-handle { background-color: alpha(#000000, 0.06); }
            .miller-resize-handle:hover { background-color: alpha(#3584e4, 0.4); }
            .miller-chevron { opacity: 0.45; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        tv = Adw.ToolbarView()
        header = Adw.HeaderBar()
        # GNOME/Zorin n'affiche par défaut que le bouton "fermer" sur les
        # fenêtres CSD -- on force explicitement minimize+maximize+close ici
        # plutôt que de dépendre du réglage global org.gnome.desktop.wm
        # (qui reste inchangé pour toutes les autres applications).
        header.set_decoration_layout(":minimize,maximize,close")
        tv.add_top_bar(header)

        # ── Barre adresse ───────────────────────────────────────────────────
        addr_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        addr_bar.set_margin_top(4); addr_bar.set_margin_bottom(4)
        addr_bar.set_margin_start(8); addr_bar.set_margin_end(8)

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
        refresh_btn.connect("clicked", lambda _: self._miller.refresh_all())
        addr_bar.append(refresh_btn)

        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header_box.append(addr_bar)
        header_box.append(Gtk.Separator())
        tv.add_top_bar(header_box)

        # ── Vue colonnes ────────────────────────────────────────────────────
        self._miller = MillerColumnsView(self)
        tv.set_content(self._miller)
        self.set_content(tv)

        self._setup_shortcuts()
        self.navigate(start_path)

    def _sync_window_width(self, needed_content_width: int):
        """Ajuste la largeur de fenêtre au nombre de colonnes réellement
        ouvertes -- grandit à l'ouverture d'une colonne, rétrécit à sa
        fermeture (retour demandé par deux testeurs : l'espace vide laissé
        à droite après une remontée dans l'arborescence était plus gênant
        que le fait que la fenêtre change de taille). Reste borné par
        MILLER_WINDOW_MIN_WIDTH d'un côté et l'espace utile de l'écran de
        l'autre ; au-delà de l'écran, le scroll auto reste le filet de
        sécurité (MillerColumnsView._scroll_to_end)."""
        surface = self.get_surface()
        display = self.get_display()
        if surface is None or display is None:
            return
        monitor = display.get_monitor_at_surface(surface)
        if monitor is None:
            return
        geo = monitor.get_geometry()
        max_w = int(geo.width * 0.92)              # marge pour ne pas coller les bords de l'écran
        target_w = max(MILLER_WINDOW_MIN_WIDTH,
                        min(needed_content_width + 40, max_w))  # +40 = marges internes / scrollbar
        cur_w = self.get_width() or 0
        if target_w != cur_w:
            self.set_default_size(target_w, self.get_height() or 650)

    def _setup_shortcuts(self):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)

        def add_shortcut(trigger_str, cb):
            trigger = Gtk.ShortcutTrigger.parse_string(trigger_str)
            action  = Gtk.CallbackAction.new(lambda *a: cb() or True)
            ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))

        add_shortcut("F5",          lambda: self._miller.refresh_all())
        add_shortcut("BackSpace",   lambda: self.navigate(os.path.dirname(self._path)))
        add_shortcut("<Alt>Left",   lambda: self.navigate(os.path.dirname(self._path)))
        add_shortcut("Escape",      lambda: self.close())

        self.add_controller(ctrl)

    # -- Navigation ------------------------------------------------------------

    def navigate(self, path: str):
        """Point d'entrée externe (adresse, dossier parent, raccourcis) —
        repart toujours d'une chaîne à une seule colonne."""
        if not os.path.isdir(path):
            return
        self._path = path
        self._addr_entry.set_text(path)
        self._miller.reset_to(path)

    def _path_changed(self, new_path: str):
        """Callback interne : la chaîne Miller a changé de profondeur
        (drill-down ou sélection d'un fichier terminal) — met juste à jour
        l'adresse affichée, sans reconstruire la chaîne."""
        self._path = new_path
        self._addr_entry.set_text(new_path)

    def _on_addr_activate(self, entry):
        self.navigate(entry.get_text().strip())


# ---------------------------------------------------------------------------
# Nautilus extension
# ---------------------------------------------------------------------------

class ColumnBrowserKeyHandler(GObject.GObject):
    """Capture F9 dans toutes les fenêtres Nautilus via GtkEventControllerKey."""
    __gtype_name__ = "ColumnBrowserKeyHandler"

    _current_path = None

    def __init__(self):
        super().__init__()
        self._hooked = set()   # fenêtres déjà hookées
        GLib.timeout_add(500, self._hook_windows)

    def _hook_windows(self):
        app = Gtk.Application.get_default()
        if app is None:
            return True
        for win in app.get_windows():
            wid = id(win)
            if wid not in self._hooked:
                self._attach_f9(win)
                self._hooked.add(wid)
        return True  # continuer

    def _attach_f9(self, window):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)

        def on_f9(*_):
            path = (ColumnBrowserKeyHandler._current_path
                    or os.path.expanduser("~"))
            ColumnBrowserWindow(path).present()
            return True

        trigger = Gtk.ShortcutTrigger.parse_string("F9")
        action  = Gtk.CallbackAction.new(on_f9)
        ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))
        window.add_controller(ctrl)


class ColumnBrowserExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "ColumnBrowserExtension"

    def __init__(self):
        super().__init__()
        # Démarrer le hook F9 dès que l'extension est chargée
        self._key_handler = ColumnBrowserKeyHandler()

    def get_file_items(self, files):
        dirs = [f for f in files
                if f.get_uri_scheme() == "file" and f.is_directory()]
        if not dirs:
            return []

        item = Nautilus.MenuItem(
            name="ColumnBrowser::Open",
            label=T["menu_label"],
            tip="Open a Miller-columns browser starting here",
            icon=_resolve_column_icon(),
        )
        item.connect("activate", self._on_activate, dirs[0])
        return [item]

    def get_background_items(self, folder):
        if folder:
            p = folder.get_location().get_path()
            if p:
                ColumnBrowserKeyHandler._current_path = p

        item = Nautilus.MenuItem(
            name="ColumnBrowser::OpenBg",
            label=T["menu_label"],
            tip="Open a Miller-columns browser here",
            icon=_resolve_column_icon(),
        )
        item.connect("activate", self._on_activate_bg, folder)
        return [item]

    def _on_activate(self, _item, nfile):
        ColumnBrowserWindow(nfile.get_location().get_path()).present()

    def _on_activate_bg(self, _item, folder):
        ColumnBrowserWindow(folder.get_location().get_path()).present()
