#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Deb Installer — Nautilus Python Extension
# DESC: Visual installer for .deb packages launched from Nautilus
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
#   cp deb-installer.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q

import os
import subprocess
import threading
import locale

import gi
gi.require_version("Gtk",     "4.0")
gi.require_version("Adw",     "1")
gi.require_version("Nautilus","4.0")
from gi.repository import GObject, Gtk, Adw, GLib, Pango, Nautilus

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":    "Installer le paquet",
        "title":         "Installation de paquet",
        "package":       "Paquet :",
        "install":       "Installer",
        "close":         "Fermer",
        "cancel":        "Annuler",
        "installing":    "Installation en cours…",
        "success":       "✓ Installation terminée avec succès.",
        "error":         "✗ Erreur lors de l'installation.",
        "cancelled":     "Installation annulée.",
        "need_password": "Authentification requise (mot de passe sudo).",
        "not_deb":       "Ce fichier n'est pas un paquet .deb valide.",
        "confirm":       "Voulez-vous installer ce paquet ?",
        "warning":       "⚠ L'installation de paquets tiers peut être risquée.\nVérifiez la source avant de continuer.",
    }
elif _lang.startswith("de"):
    T = {
        "menu_label":    "Paket installieren",
        "title":         "Paketinstallation",
        "package":       "Paket:",
        "install":       "Installieren",
        "close":         "Schließen",
        "cancel":        "Abbrechen",
        "installing":    "Installation läuft…",
        "success":       "✓ Installation erfolgreich abgeschlossen.",
        "error":         "✗ Fehler bei der Installation.",
        "cancelled":     "Installation abgebrochen.",
        "need_password": "Authentifizierung erforderlich (sudo-Passwort).",
        "not_deb":       "Diese Datei ist kein gültiges .deb-Paket.",
        "confirm":       "Möchten Sie dieses Paket installieren?",
        "warning":       "⚠ Die Installation von Drittanbieter-Paketen kann riskant sein.\nBitte Quelle vor der Installation prüfen.",
    }
else:
    T = {
        "menu_label":    "Install package",
        "title":         "Package Installation",
        "package":       "Package:",
        "install":       "Install",
        "close":         "Close",
        "cancel":        "Cancel",
        "installing":    "Installing…",
        "success":       "✓ Installation completed successfully.",
        "error":         "✗ Installation failed.",
        "cancelled":     "Installation cancelled.",
        "need_password": "Authentication required (sudo password).",
        "not_deb":       "This file is not a valid .deb package.",
        "confirm":       "Do you want to install this package?",
        "warning":       "⚠ Installing third-party packages can be risky.\nPlease verify the source before continuing.",
    }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    return app.get_active_window() if app else None

def _pkg_info(path):
    """Retourne (name, version, description) via dpkg-deb."""
    try:
        out = subprocess.check_output(
            ["dpkg-deb", "-f", path, "Package", "Version", "Description"],
            stderr=subprocess.DEVNULL).decode(errors="replace")
        info = {}
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        name    = info.get("Package", os.path.basename(path))
        version = info.get("Version", "")
        desc    = info.get("Description", "")
        return name, version, desc
    except Exception:
        return os.path.basename(path), "", ""

# ---------------------------------------------------------------------------
# Installer Window
# ---------------------------------------------------------------------------

class DebInstallerWindow(Adw.Window):
    __gtype_name__ = "DebInstallerWindow"

    def __init__(self, deb_path):
        super().__init__(title=T["title"])
        self.set_default_size(620, 480)
        self.set_resizable(True)
        self.set_transient_for(_nautilus_window())
        self._deb_path   = deb_path
        self._process    = None
        self._cancelled  = False
        self._done       = False

        tv  = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_decoration_layout(":close")
        hdr.set_title_widget(Gtk.Label(label=T["title"]))
        tv.add_top_bar(hdr)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_vexpand(True)

        # ── Infos paquet ──────────────────────────────────────────────────────
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info_box.set_margin_start(16)
        info_box.set_margin_end(16)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(8)

        name, version, desc = _pkg_info(deb_path)
        pkg_filename = os.path.basename(deb_path)

        # Icône + nom fichier
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        pkg_icon  = Gtk.Image.new_from_icon_name("application-x-deb")
        pkg_icon.set_pixel_size(48)
        title_box.append(pkg_icon)

        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_lbl = Gtk.Label(label=name if name else pkg_filename)
        name_lbl.set_halign(Gtk.Align.START)
        name_lbl.add_css_class("title-2")
        name_box.append(name_lbl)

        if version:
            ver_lbl = Gtk.Label(label=f"v{version}")
            ver_lbl.set_halign(Gtk.Align.START)
            ver_lbl.add_css_class("dim-label")
            name_box.append(ver_lbl)

        file_lbl = Gtk.Label(label=pkg_filename)
        file_lbl.set_halign(Gtk.Align.START)
        file_lbl.add_css_class("dim-label")
        file_lbl.add_css_class("caption")
        file_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name_box.append(file_lbl)

        title_box.append(name_box)
        info_box.append(title_box)

        if desc:
            desc_lbl = Gtk.Label(label=desc)
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.set_wrap(True)
            desc_lbl.set_xalign(0)
            desc_lbl.add_css_class("dim-label")
            desc_lbl.set_margin_top(4)
            info_box.append(desc_lbl)

        # Warning
        warn_lbl = Gtk.Label(label=T["warning"])
        warn_lbl.set_halign(Gtk.Align.START)
        warn_lbl.set_wrap(True)
        warn_lbl.set_xalign(0)
        warn_lbl.add_css_class("warning")
        warn_lbl.set_margin_top(6)
        info_box.append(warn_lbl)

        main.append(info_box)
        main.append(Gtk.Separator())

        # ── Terminal output ───────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self._textview = Gtk.TextView()
        self._textview.set_editable(False)
        self._textview.set_cursor_visible(False)
        self._textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._textview.set_margin_start(8)
        self._textview.set_margin_end(8)
        self._textview.set_margin_top(6)
        self._textview.set_margin_bottom(6)
        self._textview.add_css_class("monospace")
        self._buffer = self._textview.get_buffer()

        # Tags couleur
        self._tag_ok  = self._buffer.create_tag("ok",    foreground="#33d17a")
        self._tag_err = self._buffer.create_tag("error", foreground="#e01b24")
        self._tag_dim = self._buffer.create_tag("dim",   foreground="#9a9996")

        scroll.set_child(self._textview)
        main.append(scroll)
        main.append(Gtk.Separator())

        # ── Barre de statut + boutons ─────────────────────────────────────────
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)
        bottom.set_margin_top(8)
        bottom.set_margin_bottom(8)

        self._status_lbl = Gtk.Label(label=T["confirm"])
        self._status_lbl.set_halign(Gtk.Align.START)
        self._status_lbl.set_hexpand(True)
        self._status_lbl.set_wrap(True)
        bottom.append(self._status_lbl)

        self._btn_cancel = Gtk.Button(label=T["cancel"])
        self._btn_cancel.connect("clicked", self._on_cancel)
        bottom.append(self._btn_cancel)

        self._btn_install = Gtk.Button(label=T["install"])
        self._btn_install.add_css_class("suggested-action")
        self._btn_install.connect("clicked", self._on_install)
        bottom.append(self._btn_install)

        self._btn_close = Gtk.Button(label=T["close"])
        self._btn_close.set_visible(False)
        self._btn_close.connect("clicked", lambda _: self.close())
        bottom.append(self._btn_close)

        main.append(bottom)
        tv.set_content(main)
        self.set_content(tv)

    # ── Helpers TextView ──────────────────────────────────────────────────────

    def _append_text(self, text, tag=None):
        """Ajoute du texte dans le terminal et scrolle vers le bas."""
        end = self._buffer.get_end_iter()
        if tag:
            self._buffer.insert_with_tags(end, text, tag)
        else:
            self._buffer.insert(end, text)
        # Auto-scroll
        adj = self._textview.get_parent().get_vadjustment()
        adj.set_value(adj.get_upper())

    # ── Installation ──────────────────────────────────────────────────────────

    def _on_install(self, _):
        self._btn_install.set_sensitive(False)
        self._btn_cancel.set_sensitive(True)
        self._status_lbl.set_text(T["installing"])
        self._append_text(f"$ pkexec dpkg -i {self._deb_path}\n", self._tag_dim)
        threading.Thread(target=self._run_install, daemon=True).start()

    def _run_install(self):
        try:
            self._process = subprocess.Popen(
                ["pkexec", "dpkg", "-i", self._deb_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in self._process.stdout:
                if self._cancelled:
                    break
                GLib.idle_add(self._append_text, line)

            self._process.wait()
            rc = self._process.returncode

            if self._cancelled:
                GLib.idle_add(self._on_done, False, True)
            elif rc == 0:
                GLib.idle_add(self._on_done, True, False)
            else:
                GLib.idle_add(self._on_done, False, False)

        except Exception as e:
            GLib.idle_add(self._append_text, f"\n{e}\n", self._tag_err)
            GLib.idle_add(self._on_done, False, False)

    def _on_done(self, success, cancelled):
        self._done = True
        self._btn_cancel.set_visible(False)
        self._btn_install.set_visible(False)
        self._btn_close.set_visible(True)

        if cancelled:
            self._status_lbl.set_text(T["cancelled"])
            self._append_text(f"\n{T['cancelled']}\n", self._tag_dim)
        elif success:
            self._status_lbl.set_text(T["success"])
            self._append_text(f"\n{T['success']}\n", self._tag_ok)
        else:
            self._status_lbl.set_text(T["error"])
            self._append_text(f"\n{T['error']}\n", self._tag_err)

    def _on_cancel(self, _):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception:
                pass
        if not self._done:
            self._on_done(False, True)

# ---------------------------------------------------------------------------
# Extension Nautilus
# ---------------------------------------------------------------------------

class DebInstallerExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "DebInstallerExtension"

    def get_file_items(self, files):
        if len(files) != 1:
            return []
        f = files[0]
        if f.get_uri_scheme() != "file":
            return []
        path = f.get_location().get_path()
        if not path or not path.lower().endswith(".deb"):
            return []

        item = Nautilus.MenuItem(
            name  = "DebInstaller::Install",
            label = T["menu_label"],
            tip   = "Install this .deb package",
            icon  = "system-software-install-symbolic",
        )
        item.connect("activate", lambda *_: DebInstallerWindow(path).present())
        return [item]

    def get_background_items(self, folder):
        return []
