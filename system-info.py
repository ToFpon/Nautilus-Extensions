#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: System Info — Nautilus Python Extension
# DESC: Launches Hardinfo2 from Nautilus context menu
# AUTHOR: Tof
# VERSION: 1.0
# LICENSE: GNU General Public License v3.0
#
# REQUIRES: hardinfo2
# INSTALL:
#   cp system-info.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q

import shutil
import subprocess
import locale

import gi
gi.require_version("Gtk",     "4.0")
gi.require_version("Nautilus","4.0")
from gi.repository import GObject, Gtk, GLib, Nautilus

_lang = locale.getlocale()[0] or ""
_label = "Informations système" if _lang.startswith("fr") else "System Information"


def _launch_hardinfo2():
    if shutil.which("hardinfo2"):
        subprocess.Popen(["hardinfo2"])


class SystemInfoKeyHandler(GObject.GObject):
    __gtype_name__ = "SystemInfoKeyHandler"

    def __init__(self):
        super().__init__()
        app = Gtk.Application.get_default()
        if app:
            app.connect("window-added", self._on_window_added)
            for win in app.get_windows():
                self._attach_f6(win)
        GLib.timeout_add(2000, self._hook_windows)

    def _hook_windows(self):
        app = Gtk.Application.get_default()
        if app:
            for win in app.get_windows():
                if not getattr(win, "_sysinfo_f6", False):
                    self._attach_f6(win)
        return True

    def _on_window_added(self, app, win):
        self._attach_f6(win)

    def _attach_f6(self, window):
        if getattr(window, "_sysinfo_f6", False):
            return
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        trigger = Gtk.ShortcutTrigger.parse_string("F6")
        action  = Gtk.CallbackAction.new(lambda *_: _launch_hardinfo2() or True)
        ctrl.add_shortcut(Gtk.Shortcut.new(trigger, action))
        window.add_controller(ctrl)
        window._sysinfo_f6 = True


class SystemInfoExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "SystemInfoExtension"

    def __init__(self):
        super().__init__()
        self._key_handler = SystemInfoKeyHandler()

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        if not shutil.which("hardinfo2"):
            return []
        item = Nautilus.MenuItem(
            name  = "SystemInfo::Open",
            label = _label,
            tip   = "Launch Hardinfo2 — F6",
            icon  = "dialog-information-symbolic",
        )
        item.connect("activate", lambda *_: _launch_hardinfo2())
        return [item]
