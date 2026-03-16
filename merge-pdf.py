#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Merge PDF – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), ghostscript, python3-gi, gir1.2-adw-1
# INSTALL:
#   cp merge-pdf.py ~/.local/share/nautilus-python/extensions/
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
        "menu_label":    "Fusionner les PDF…",
        "dialog_title":  "Fusionner les PDF",
        "order_label":   "Glissez pour réordonner les fichiers :",
        "save_as":       "Enregistrer le PDF fusionné sous…",
        "merging":       "Fusion en cours…",
        "done_title":    "Fusion terminée",
        "done_msg":      "Les PDF ont été fusionnés avec succès.",
        "err_gs":        "ghostscript est introuvable. Veuillez l'installer.",
        "err_single":    "Sélectionnez au moins deux fichiers PDF.",
        "err_failed":    "La fusion a échoué (code {code}).",
        "cancel":        "Annuler",
        "ok":            "Fusionner",
        "move_up":       "↑",
        "move_down":     "↓",
        "output_name":   "fusion.pdf",
    }
else:
    T = {
        "menu_label":    "Merge PDFs…",
        "dialog_title":  "Merge PDFs",
        "order_label":   "Drag to reorder files:",
        "save_as":       "Save merged PDF as…",
        "merging":       "Merging…",
        "done_title":    "Merge complete",
        "done_msg":      "PDFs have been successfully merged.",
        "err_gs":        "ghostscript is not installed. Please install it first.",
        "err_single":    "Please select at least two PDF files.",
        "err_failed":    "Merge failed (exit code {code}).",
        "cancel":        "Cancel",
        "ok":            "Merge",
        "move_up":       "↑",
        "move_down":     "↓",
        "output_name":   "merged.pdf",
    }

GS_BIN = shutil.which("ghostscript") or shutil.which("gs") or "/usr/bin/ghostscript"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    win = app.get_active_window()
    if win is not None:
        return win
    windows = app.get_windows()
    return windows[0] if windows else None

def _show_message(msg: str):
    dlg = Gtk.AlertDialog(message=msg)
    dlg.show(_nautilus_window())


# ---------------------------------------------------------------------------
# Order dialog  (liste réordonnables avec boutons ↑ ↓)
# ---------------------------------------------------------------------------

class OrderDialog(Adw.Window):
    __gtype_name__ = "MergePDFOrderDialog"

    def __init__(self, paths: list, callback):
        """callback(ordered_paths) ou callback(None) si annulé."""
        super().__init__(title=T["dialog_title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_default_size(480, 380)
        self._callback = callback
        self._paths    = list(paths)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(16)
        outer.set_margin_end(16)

        lbl = Gtk.Label(label=T["order_label"])
        lbl.set_halign(Gtk.Align.START)
        outer.append(lbl)

        # ScrolledWindow + ListBox
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.add_css_class("boxed-list")
        scroll.set_child(self._listbox)
        outer.append(scroll)

        self._populate()

        # Boutons ↑ ↓
        arrow_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        arrow_box.set_halign(Gtk.Align.START)

        up_btn = Gtk.Button(label=T["move_up"])
        up_btn.connect("clicked", self._move_up)
        arrow_box.append(up_btn)

        down_btn = Gtk.Button(label=T["move_down"])
        down_btn.connect("clicked", self._move_down)
        arrow_box.append(down_btn)

        outer.append(arrow_box)

        # OK / Annuler
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(4)

        cancel_btn = Gtk.Button(label=T["cancel"])
        cancel_btn.connect("clicked", lambda _: self._respond(False))
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=T["ok"])
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda _: self._respond(True))
        btn_box.append(ok_btn)

        outer.append(btn_box)

        toolbar_view.set_content(outer)
        self.set_content(toolbar_view)

    def _populate(self):
        # Vider la liste
        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)

        for path in self._paths:
            row = Gtk.ListBoxRow()
            row.path = path

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(12)
            box.set_margin_end(12)

            icon = Gtk.Image.new_from_icon_name("x-office-document")
            box.append(icon)

            lbl = Gtk.Label(label=os.path.basename(path))
            lbl.set_halign(Gtk.Align.START)
            lbl.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            lbl.set_hexpand(True)
            box.append(lbl)

            row.set_child(box)
            self._listbox.append(row)

    def _selected_index(self):
        row = self._listbox.get_selected_row()
        return row.get_index() if row else -1

    def _move_up(self, _btn):
        i = self._selected_index()
        if i > 0:
            self._paths[i], self._paths[i - 1] = self._paths[i - 1], self._paths[i]
            self._populate()
            self._listbox.select_row(self._listbox.get_row_at_index(i - 1))

    def _move_down(self, _btn):
        i = self._selected_index()
        if 0 <= i < len(self._paths) - 1:
            self._paths[i], self._paths[i + 1] = self._paths[i + 1], self._paths[i]
            self._populate()
            self._listbox.select_row(self._listbox.get_row_at_index(i + 1))

    def _respond(self, ok: bool):
        self._callback(self._paths if ok else None)
        self.destroy()


# ---------------------------------------------------------------------------
# Progress dialog
# ---------------------------------------------------------------------------

class MergeProgressDialog(Adw.Window):
    __gtype_name__ = "MergePDFProgressDialog"

    def __init__(self, paths: list, dst: str, done_callback):
        super().__init__(title=T["dialog_title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_deletable(False)
        self.set_default_size(340, -1)

        self._paths   = paths
        self._dst     = dst
        self._tmp     = dst + ".tmp_merge.pdf"
        self._process = None
        self._done_cb = done_callback

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        box.append(Gtk.Label(label=T["merging"]))

        self._bar = Gtk.ProgressBar()
        self._bar.set_pulse_step(0.05)
        box.append(self._bar)

        cancel_btn = Gtk.Button(label=T["cancel"])
        cancel_btn.connect("clicked", self._on_cancel)
        box.append(cancel_btn)

        toolbar_view.set_content(box)
        self.set_content(toolbar_view)

        self._thread = threading.Thread(target=self._merge, daemon=True)
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

    def _merge(self):
        cmd = [
            GS_BIN,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/default",
            "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={self._tmp}",
        ] + self._paths

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
        _show_message(msg)
        self._done_cb(False)
        self.destroy()


# ---------------------------------------------------------------------------
# Extension Nautilus 4.0 / GTK4
# ---------------------------------------------------------------------------

class MergePDFExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "MergePDFExtension"

    def get_file_items(self, files):
        pdfs = [
            f for f in files
            if f.get_uri_scheme() == "file"
            and f.get_mime_type() == "application/pdf"
        ]
        if len(pdfs) < 2:
            return []

        item = Nautilus.MenuItem(
            name="MergePDF::Merge",
            label=T["menu_label"],
            tip="Merge selected PDF files into one",
        )
        item.connect("activate", self._on_activate, pdfs)
        return [item]

    def get_background_items(self, folder):
        return []

    def _on_activate(self, _item, pdf_items):
        if not os.path.isfile(GS_BIN) or not os.access(GS_BIN, os.X_OK):
            _show_message(T["err_gs"])
            return

        paths = [f.get_location().get_path() for f in pdf_items]

        def on_order_chosen(ordered_paths):
            if ordered_paths is None:
                return
            self._ask_save_path(ordered_paths)

        OrderDialog(paths=paths, callback=on_order_chosen).present()

    def _ask_save_path(self, ordered_paths: list):
        first_dir = os.path.dirname(ordered_paths[0])
        dlg = Gtk.FileDialog(title=T["save_as"])
        dlg.set_initial_folder(Gio.File.new_for_path(first_dir))
        dlg.set_initial_name(T["output_name"])
        dlg.save(_nautilus_window(), None, self._on_save_response, ordered_paths)

    def _on_save_response(self, dlg, result, ordered_paths):
        try:
            gfile = dlg.save_finish(result)
            dst   = gfile.get_path()
        except Exception:
            return  # annulé

        def on_done(success):
            if success:
                _show_message(T["done_msg"])

        MergeProgressDialog(ordered_paths, dst, done_callback=on_done).present()
