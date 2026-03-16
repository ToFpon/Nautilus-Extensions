# Folder Color Revival - based on Folder Color 0.4.1
# Original: https://github.com/costales/folder-color
# Copyright (C) 2012-2024 Marcos Alvarez Costales
# Revival / Debug for Nautilus 43+ / GTK4 / python3-nautilus 4.0
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

import os
import sys
import logging
import gi
from pathlib import Path

# ---------------------------------------------------------------------------
# Debug logging — set DEBUG=1 to enable:
#   DEBUG=1 nautilus --no-desktop 2>&1 | grep "folder-color"
# ---------------------------------------------------------------------------
_DEBUG = os.environ.get("DEBUG", "0") == "1"
logging.basicConfig(
    stream=sys.stderr,
    format="[folder-color-revival] %(levelname)s: %(message)s",
)
log = logging.getLogger("folder-color-revival")
log.setLevel(logging.DEBUG if _DEBUG else logging.WARNING)

log.debug("Extension loading...")

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Nautilus", "4.0")

from gi.repository import Nautilus, Gtk, Gdk, GObject, Gio, GLib

# ---------------------------------------------------------------------------
# FIX 1 : i18n — les placeholders @GETTEXT_PACKAGE@ / @LOCALEDIR@ n'étaient
# jamais remplacés (script prévu pour être compilé via autotools).
# On tombe back sur gettext standard sans domaine custom.
# ---------------------------------------------------------------------------
try:
    from gettext import gettext as _
except Exception:
    def _(s): return s

COLOR  = _("Color")
EMBLEM = _("Emblem")

COLORS_ALL = {
    "black":   _("Black"),
    "blue":    _("Blue"),
    "brown":   _("Brown"),
    "cyan":    _("Cyan"),
    "green":   _("Green"),
    "grey":    _("Grey"),
    "magenta": _("Magenta"),
    "orange":  _("Orange"),
    "pink":    _("Pink"),
    "purple":  _("Purple"),
    "red":     _("Red"),
    "violet":  _("Violet"),
    "white":   _("White"),
    "yellow":  _("Yellow"),
}

EMBLEMS_ALL = {
    "emblem-important": _("Important"),
    "emblem-urgent":    _("In Progress"),
    "emblem-favorite":  _("Favorite"),
    "emblem-default":   _("Finished"),
    "emblem-new":       _("New"),
}

ICON_SIZES = {
    "extra-large": 256,
    "large":       128,
    "medium":       96,
    "small-plus":   64,
    "small":        48,
}

# ---------------------------------------------------------------------------
# FIX 2 : USER_DIRS était construit au niveau MODULE, avant l'initialisation
# complète de GLib/Nautilus → freeze garanti.
# On le construit à la demande, une seule fois, dans une fonction lazy.
# ---------------------------------------------------------------------------
_USER_DIRS = None

def _get_user_dirs():
    global _USER_DIRS
    if _USER_DIRS is None:
        _USER_DIRS = {
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_DESKTOP):      "desktop",
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_DOCUMENTS):    "documents",
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_DOWNLOAD):     "downloads",
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_MUSIC):        "music",
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_PICTURES):     "pictures",
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_PUBLIC_SHARE): "public",
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_TEMPLATES):    "templates",
            GLib.get_user_special_dir(GLib.USER_DIRECTORY_VIDEOS):       "videos",
        }
    return _USER_DIRS


# ---------------------------------------------------------------------------
# FolderColor
# ---------------------------------------------------------------------------

class FolderColor:
    """Folder Color logic"""

    def __init__(self):
        self.is_modified = False
        self.colors      = []
        self.emblems     = []
        self.icon_size   = 96  # valeur par défaut safe

        # FIX 3 : Gio.Settings.new() planterait si le schéma n'est pas installé.
        # On enveloppe dans un try/except et on ne connecte le signal que si ça marche.
        try:
            self.gio_settings = Gio.Settings.new("org.gnome.nautilus.icon-view")
            self.icon_size    = ICON_SIZES.get(
                self.gio_settings.get_string("default-zoom-level"), 96)
            self.gio_settings.connect(
                "changed::default-zoom-level", self.on_changed_zoom_level)
        except Exception as e:
            log.warning(f"GSettings unavailable: {e}")
            self.gio_settings = None

        # FIX 4 : set_colors_theme() / set_emblems_theme() faisaient des lookups
        # d'icônes lourds dans __init__, bloquant le thread principal de Nautilus.
        # On les diffère au premier vrai usage via GLib.idle_add (hors init).
        GLib.idle_add(self._lazy_load_theme)

    def _lazy_load_theme(self):
        """Chargement différé des thèmes — exécuté quand Nautilus est idle."""
        log.debug("Lazy loading icon theme...")
        self.set_colors_theme()
        self.set_emblems_theme()
        log.debug(f"Theme loaded: {len(self.colors)} colors, {len(self.emblems)} emblems")
        return False  # ne pas répéter

    def on_changed_zoom_level(self, settings, key="default-zoom-level"):
        self.icon_size = ICON_SIZES.get(settings.get_string(key), 96)
        self.set_colors_theme()
        self.set_emblems_theme()

    def _get_icon(self, icon_name, is_color=True):
        """Lookup d'icône dans le thème courant."""
        try:
            icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            size_aux   = self.icon_size if is_color else 24
            icon       = icon_theme.lookup_icon(
                icon_name, None, size_aux, 1,
                Gtk.TextDirection.LTR, Gtk.IconLookupFlags.FORCE_REGULAR,
            )
            if icon_theme.has_icon(icon_name):
                return {"icon": Path(icon.get_icon_name()).stem,
                        "uri":  icon.get_file().get_uri()}
        except Exception:
            pass
        return {"icon": "", "uri": ""}

    def set_colors_theme(self):
        self.colors.clear()
        icon_options = [
            "folder-", "folder_color_", "folder_",          # thème courant
            "folder-", "folder_color_", "folder_",          # hicolor fallback
        ]
        for color in COLORS_ALL:
            for i, option in enumerate(icon_options):
                icon_aux = self._get_icon(option + color)
                if i < 3 and icon_aux["icon"] and "/hicolor/" not in icon_aux["uri"]:
                    self.colors.append({"icon": icon_aux["icon"],
                                        "label": COLORS_ALL[color],
                                        "uri":   icon_aux["uri"]})
                    break
                if i >= 3 and icon_aux["icon"]:
                    self.colors.append({"icon": icon_aux["icon"],
                                        "label": COLORS_ALL[color],
                                        "uri":   icon_aux["uri"]})
                    break

    def set_emblems_theme(self):
        self.emblems.clear()
        for emblem in EMBLEMS_ALL:
            icon_aux = self._get_icon(emblem, False)
            if icon_aux["icon"]:
                self.emblems.append({"icon": icon_aux["icon"],
                                     "label": EMBLEMS_ALL[emblem],
                                     "uri":   icon_aux["uri"]})

    def get_colors_theme(self):
        return self.colors

    def get_emblems_theme(self):
        return self.emblems

    def _get_skel_folder(self, folder, color, uri=True):
        user_dirs  = _get_user_dirs()
        color_param = color
        if folder in user_dirs:
            skel_color = "-".join([color["icon"], user_dirs[folder]])
            if "_" in skel_color:
                skel_color = skel_color.replace("-", "_")
            color_aux = self._get_icon(skel_color)
            if color_aux["icon"]:
                color_param = color_aux
        return color_param["uri"] if uri else color_param["icon"]

    def set_color(self, item, color, uri=True):
        if self.is_modified:
            self._set_restore_folder(item)
        try:
            item_aux = Gio.File.new_for_path(item)
            attr     = "metadata::custom-icon" if uri else "metadata::custom-icon-name"
            info     = item_aux.query_info(attr, 0, None)
            info.set_attribute_string(attr, self._get_skel_folder(item, color, uri))
            item_aux.set_attributes_from_info(info, 0, None)
            self._reload_icon(item)
        except Exception as e:
            log.error(f"set_color: {e}")

    def set_emblem(self, item, emblem):
        try:
            emblems  = [emblem["icon"], None]
            item_aux = Gio.File.new_for_path(item)
            info     = item_aux.query_info("metadata::emblems", 0, None)
            info.set_attribute_stringv("metadata::emblems", emblems)
            item_aux.set_attributes_from_info(info, 0, None)
            self._reload_icon(item)
        except Exception as e:
            log.error(f"set_emblem: {e}")

    def set_restore(self, item):
        self._set_restore_folder(item)
        self._set_restore_emblem(item)
        self._reload_icon(item)

    def _set_restore_folder(self, item):
        try:
            item_aux = Gio.File.new_for_path(item)
            info     = item_aux.query_info("metadata::custom-icon-name", 0, None)
            info.set_attribute("metadata::custom-icon",
                               Gio.FileAttributeType.INVALID, 0)
            info.set_attribute("metadata::custom-icon-name",
                               Gio.FileAttributeType.INVALID, 0)
            item_aux.set_attributes_from_info(info, 0, None)
        except Exception as e:
            log.error(f"restore_folder: {e}")

    def _set_restore_emblem(self, item):
        try:
            item_aux = Gio.File.new_for_path(item)
            info     = item_aux.query_info("metadata::emblems", 0, None)
            info.set_attribute("metadata::emblems",
                               Gio.FileAttributeType.INVALID, 0)
            item_aux.set_attributes_from_info(info, 0, None)
        except Exception as e:
            print(f"[folder-color] restore_emblem error: {e}")

    def _reload_icon(self, item):
        try:
            os.utime(item, None)
        except Exception:
            pass

    def get_is_modified(self, items):
        for item in items:
            try:
                item_path = item.get_location().get_path()
                item_file = Gio.File.new_for_path(item_path)
                info      = item_file.query_info("metadata", 0, None)
                if (info.get_attribute_as_string("metadata::custom-icon-name") or
                        info.get_attribute_as_string("metadata::custom-icon") or
                        info.get_attribute_as_string("metadata::emblems")):
                    self.is_modified = True
                    return True
            except Exception:
                continue
        self.is_modified = False
        return False


# ---------------------------------------------------------------------------
# Nautilus Menu Provider
# ---------------------------------------------------------------------------

class FolderColorMenu(GObject.GObject, Nautilus.MenuProvider):
    # FIX 5 : __gtype_name__ explicite pour éviter les conflits de types GLib
    # avec d'autres extensions ou entre rechargements.
    __gtype_name__ = "FolderColorMenu"

    def __init__(self):
        GObject.Object.__init__(self)
        self.all_dirs    = True
        self.foldercolor = FolderColor()
        self.theme       = ""
        # Ne pas appeler _load_theme() ici — déjà différé dans FolderColor.__init__

    def get_file_items(self, items):
        if not self._check_show_menu(items):
            return []

        # Rechargement du thème si changé depuis la dernière fois
        current_theme = Gtk.Settings.get_default().get_property("gtk-icon-theme-name")
        if self.theme != current_theme:
            self.theme = current_theme
            self.foldercolor.set_colors_theme()
            self.foldercolor.set_emblems_theme()

        log.debug(f"get_file_items: {len(items)} item(s), all_dirs={self.all_dirs}")
        return self._show_menu(items) or []

    def _check_show_menu(self, items):
        if not items:
            return False
        self.all_dirs = True
        for item in items:
            if item.get_uri_scheme() != "file":
                return False
            if not item.is_directory():
                self.all_dirs = False
        return True

    def _show_menu(self, items):
        colors     = self.foldercolor.get_colors_theme()
        emblems    = self.foldercolor.get_emblems_theme()
        is_modified = self.foldercolor.get_is_modified(items)

        if self.all_dirs and colors:
            top_menuitem = Nautilus.MenuItem(
                name="FolderColorMenu::colors", label=COLOR, icon="color-picker")
        elif emblems:
            top_menuitem = Nautilus.MenuItem(
                name="FolderColorMenu::colors", label=EMBLEM, icon="color-picker")
        else:
            return []

        submenu = Nautilus.Menu()
        top_menuitem.set_submenu(submenu)

        # Couleurs
        if self.all_dirs:
            for color in colors:
                item = Nautilus.MenuItem(
                    name="FolderColorMenu::color_" + color["icon"],
                    label=color["label"],
                    icon=color["icon"],
                )
                item.connect("activate", self._menu_activate_color, items, color)
                submenu.append_item(item)

        # Emblèmes
        if emblems:
            if self.all_dirs and colors:
                submenu.append_item(Nautilus.MenuItem(
                    name="FolderColorMenu::sep_emblems",
                    label="―――", sensitive=False))
            for emblem in emblems:
                item = Nautilus.MenuItem(
                    name="FolderColorMenu::emblem_" + emblem["icon"],
                    label=emblem["label"],
                    icon=emblem["icon"],
                )
                item.connect("activate", self._menu_activate_emblem, items, emblem)
                submenu.append_item(item)

        # Restaurer
        if is_modified:
            submenu.append_item(Nautilus.MenuItem(
                name="FolderColorMenu::sep_restore",
                label="―――", sensitive=False))
            item = Nautilus.MenuItem(
                name="FolderColorMenu::restore",
                label=_("Default"), icon="undo")
            item.connect("activate", self._menu_activate_restore, items)
            submenu.append_item(item)

        return (top_menuitem,)

    def _menu_activate_color(self, menu, items, color):
        for item in items:
            if not item.is_gone():
                self.foldercolor.set_color(item.get_location().get_path(), color)

    def _menu_activate_emblem(self, menu, items, emblem):
        for item in items:
            if not item.is_gone():
                self.foldercolor.set_emblem(item.get_location().get_path(), emblem)

    def _menu_activate_restore(self, menu, items):
        for item in items:
            if not item.is_gone():
                self.foldercolor.set_restore(item.get_location().get_path())
