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
# AUTHOR: Based on "Compress PDF" bash script by Ricardo Ferreira
# NAME: Compress PDF – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), ghostscript, python3-gi, gir1.2-gtk-4.0
# INSTALL:
#   cp compress-pdf.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import shutil
import subprocess
import threading
import locale

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gio, Nautilus

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":   "Compresser le PDF…",
        "dialog_title": "Compress PDF",
        "choose_level": "Choisissez un niveau d'optimisation :",
        "save_as":      "Enregistrer le PDF sous…",
        "compressing":  "Compression en cours…",
        "done_title":   "Compress PDF – Terminé",
        "done_msg":     "{name} a été compressé avec succès.",
        "err_gs":       "ghostscript est introuvable. Veuillez l'installer.",
        "err_nopdf":    "Le fichier sélectionné n'est pas un PDF valide.",
        "err_failed":   "La compression a échoué (code {code}).",
        "cancel":       "Annuler",
        "ok":           "OK",
        "postpend":     "-optimisé",
        "levels": [
            ("Défaut",                   "/default"),
            ("Affichage écran",          "/screen"),
            ("Basse qualité",            "/ebook"),
            ("Haute qualité",            "/printer"),
            ("Haute qualité (couleurs)", "/prepress"),
        ],
    }
else:
    T = {
        "menu_label":   "Compress PDF…",
        "dialog_title": "Compress PDF",
        "choose_level": "Please choose an optimization level:",
        "save_as":      "Save PDF as…",
        "compressing":  "Compressing…",
        "done_title":   "Compress PDF – Done",
        "done_msg":     "{name} has been successfully compressed.",
        "err_gs":       "ghostscript is not installed. Please install it first.",
        "err_nopdf":    "The selected file is not a valid PDF.",
        "err_failed":   "Compression failed (exit code {code}).",
        "cancel":       "Cancel",
        "ok":           "OK",
        "postpend":     "-optimized",
        "levels": [
            ("Default",                    "/default"),
            ("Screen-view only",           "/screen"),
            ("Low Quality",                "/ebook"),
            ("High Quality",               "/printer"),
            ("High Quality (Color Pres.)", "/prepress"),
        ],
    }

GS_BIN = shutil.which("ghostscript") or shutil.which("gs") or "/usr/bin/ghostscript"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_pdf(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"%PDF"
    except OSError:
        return False

def _suggest_output(path: str) -> str:
    base, ext = os.path.splitext(path)
    return f"{base}{T['postpend']}{ext}"

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    # get_active_window() peut renvoyer None quand le menu vient de se fermer
    win = app.get_active_window()
    if win is not None:
        return win
    windows = app.get_windows()
    return windows[0] if windows else None

def _show_message(msg: str, is_error: bool = False):
    """Affiche un message via Gtk.AlertDialog (GTK 4.10+)."""
    dlg = Gtk.AlertDialog(message=msg)
    dlg.show(_nautilus_window())


# ---------------------------------------------------------------------------
# Level-picker dialog  (GTK4 : signaux, pas de .run())
# ---------------------------------------------------------------------------

class LevelDialog(Adw.Window):
    __gtype_name__ = "CompressPDFLevelDialog"

    def __init__(self, callback):
        super().__init__(title=T["dialog_title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_default_size(360, -1)
        self._callback = callback

        # Toolbar + contenu via Adw.ToolbarView
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)

        lbl = Gtk.Label(label=T["choose_level"])
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        self._buttons = []
        group = None
        for name, setting in T["levels"]:
            btn = Gtk.CheckButton(label=name)
            btn.gs_setting = setting
            if group is None:
                group = btn
                btn.set_active(True)
            else:
                btn.set_group(group)
            box.append(btn)
            self._buttons.append(btn)

        # Boutons OK / Annuler
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(8)

        cancel_btn = Gtk.Button(label=T["cancel"])
        cancel_btn.connect("clicked", lambda _: self._respond(False))
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=T["ok"])
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda _: self._respond(True))
        btn_box.append(ok_btn)

        box.append(btn_box)
        toolbar_view.set_content(box)
        self.set_content(toolbar_view)

    def get_selected_setting(self):
        for btn in self._buttons:
            if btn.get_active():
                return btn.gs_setting
        return "/default"

    def _respond(self, ok: bool):
        setting = self.get_selected_setting() if ok else None
        self._callback(setting)
        self.destroy()


# ---------------------------------------------------------------------------
# Progress dialog
# ---------------------------------------------------------------------------

class ProgressDialog(Adw.Window):
    __gtype_name__ = "CompressPDFProgressDialog"

    def __init__(self, src: str, dst: str, gs_setting: str, done_callback):
        super().__init__(title=T["dialog_title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_deletable(False)
        self.set_default_size(340, -1)

        self._src        = src
        self._dst        = dst
        self._gs_setting = gs_setting
        self._tmp        = dst + ".tmp_compress.pdf"
        self._process    = None
        self._done_cb    = done_callback

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        box.append(Gtk.Label(label=T["compressing"]))

        self._bar = Gtk.ProgressBar()
        self._bar.set_pulse_step(0.05)
        box.append(self._bar)

        cancel_btn = Gtk.Button(label=T["cancel"])
        cancel_btn.connect("clicked", self._on_cancel)
        box.append(cancel_btn)

        toolbar_view.set_content(box)
        self.set_content(toolbar_view)

        self._thread = threading.Thread(target=self._compress, daemon=True)
        self._thread.start()
        GObject.timeout_add(80, self._pulse)

    def _pulse(self):
        if self._thread.is_alive():
            self._bar.pulse()
            return True
        return False

    def _on_cancel(self, _btn):
        if self._process and self._process.poll() is None:
            self._process.kill()
        self._cleanup_tmp()
        self._done_cb(False)
        self.destroy()

    def _cleanup_tmp(self):
        try:
            os.remove(self._tmp)
        except FileNotFoundError:
            pass

    def _compress(self):
        cmd = [
            GS_BIN,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS={self._gs_setting}",
            "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={self._tmp}",
            self._src,
        ]
        try:
            self._process = subprocess.Popen(cmd)
            rc = self._process.wait()
        except Exception as exc:
            GObject.idle_add(self._finish_error, str(exc))
            return

        if rc == 0:
            try:
                os.replace(self._tmp, self._dst)
            except OSError as exc:
                GObject.idle_add(self._finish_error, str(exc))
                return
            GObject.idle_add(self._finish_ok)
        else:
            self._cleanup_tmp()
            GObject.idle_add(self._finish_error, T["err_failed"].format(code=rc))

    def _finish_ok(self):
        self._bar.set_fraction(1.0)
        self._done_cb(True)
        self.destroy()

    def _finish_error(self, msg: str):
        _show_message(msg, is_error=True)
        self._done_cb(False)
        self.destroy()


# ---------------------------------------------------------------------------
# Extension Nautilus 4.0 / GTK4
# ---------------------------------------------------------------------------

class CompressPDFExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "CompressPDFExtension"

    def get_file_items(self, files):
        pdfs = [
            f for f in files
            if f.get_uri_scheme() == "file"
            and f.get_mime_type() == "application/pdf"
        ]
        if not pdfs:
            return []

        item = Nautilus.MenuItem(
            name="CompressPDF::Compress",
            label=T["menu_label"],
            tip="Compress and optimize the selected PDF file(s)",
        )
        item.connect("activate", self._on_activate, pdfs)
        return [item]

    def get_background_items(self, folder):
        return []

    def _on_activate(self, _item, pdf_items):
        if not os.path.isfile(GS_BIN) or not os.access(GS_BIN, os.X_OK):
            _show_message(T["err_gs"], is_error=True)
            return

        def on_level_chosen(setting):
            if setting is None:
                return
            self._process_files(pdf_items, setting)

        LevelDialog(callback=on_level_chosen).present()

    def _process_files(self, pdf_items, setting, index=0):
        if index >= len(pdf_items):
            return

        nfile = pdf_items[index]
        src   = nfile.get_location().get_path()

        if not _is_pdf(src):
            _show_message(T["err_nopdf"], is_error=True)
            self._process_files(pdf_items, setting, index + 1)
            return

        def do_compress(dst):
            if dst is None:
                return

            def on_done(success):
                if success:
                    _show_message(T["done_msg"].format(name=os.path.basename(src)))
                self._process_files(pdf_items, setting, index + 1)

            ProgressDialog(src, dst, setting, done_callback=on_done).present()

        if len(pdf_items) == 1:
            self._ask_save_path(src, callback=do_compress)
        else:
            do_compress(_suggest_output(src))

    def _ask_save_path(self, src: str, callback):
        dlg = Gtk.FileDialog(title=T["save_as"])
        dlg.set_initial_folder(Gio.File.new_for_path(os.path.dirname(src)))
        dlg.set_initial_name(os.path.basename(_suggest_output(src)))
        dlg.save(_nautilus_window(), None, self._on_save_response, callback)

    def _on_save_response(self, dlg, result, callback):
        try:
            gfile = dlg.save_finish(result)
            callback(gfile.get_path())
        except Exception:
            callback(None)  # annulé par l'utilisateur
