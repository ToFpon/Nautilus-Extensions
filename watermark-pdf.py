#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Watermark PDF – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), ghostscript, python3-gi, gir1.2-adw-1
# INSTALL:
#   cp watermark-pdf.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import shutil
import subprocess
import threading
import locale

import tempfile
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
        "menu_label":     "Ajouter un filigrane…",
        "dialog_title":   "Filigrane PDF",
        "text_label":     "Texte du filigrane",
        "text_hint":      "Ex : CONFIDENTIEL, NE PAS DIFFUSER…",
        "opacity_label":  "Opacité",
        "angle_label":    "Angle",
        "size_label":     "Taille de police",
        "color_label":    "Couleur",
        "position_label": "Position",
        "pos_center":     "Centre",
        "pos_diagonal":   "Diagonale répétée",
        "save_as":        "Enregistrer sous…",
        "processing":     "Application du filigrane…",
        "done_title":     "Filigrane ajouté",
        "done_msg":       "{name} a été traité avec succès.",
        "err_gs":         "ghostscript est introuvable. Veuillez l'installer.",
        "err_empty":      "Le texte du filigrane ne peut pas être vide.",
        "err_failed":     "L'opération a échoué (code {code}).",
        "cancel":         "Annuler",
        "ok":             "Appliquer",
        "postpend":       "-filigrané",
        "colors": [
            ("Rouge",   "1 0 0"),
            ("Gris",    "0.5 0.5 0.5"),
            ("Bleu",    "0 0 0.8"),
            ("Noir",    "0 0 0"),
        ],
    }
else:
    T = {
        "menu_label":     "Add Watermark…",
        "dialog_title":   "PDF Watermark",
        "text_label":     "Watermark text",
        "text_hint":      "E.g. CONFIDENTIAL, DO NOT SHARE…",
        "opacity_label":  "Opacity",
        "angle_label":    "Angle",
        "size_label":     "Font size",
        "color_label":    "Color",
        "position_label": "Position",
        "pos_center":     "Center",
        "pos_diagonal":   "Diagonal repeat",
        "save_as":        "Save as…",
        "processing":     "Applying watermark…",
        "done_title":     "Watermark applied",
        "done_msg":       "{name} has been successfully watermarked.",
        "err_gs":         "ghostscript is not installed. Please install it first.",
        "err_empty":      "Watermark text cannot be empty.",
        "err_failed":     "Operation failed (exit code {code}).",
        "cancel":         "Cancel",
        "ok":             "Apply",
        "postpend":       "-watermarked",
        "colors": [
            ("Red",   "1 0 0"),
            ("Gray",  "0.5 0.5 0.5"),
            ("Blue",  "0 0 0.8"),
            ("Black", "0 0 0"),
        ],
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
    Gtk.AlertDialog(message=msg).show(_nautilus_window())

def _suggest_output(path: str) -> str:
    base, ext = os.path.splitext(path)
    return f"{base}{T['postpend']}{ext}"

def _build_watermark_pdf(text, opacity, angle_deg, font_size, color_rgb, diagonal,
                          page_w=595, page_h=842):
    """Génère un PDF de filigrane en Python pur.
    Transparence réelle via ExtGState (/ca /CA) — PDF 1.4 standard, sans GS."""
    import math
    r, g, b   = [float(x) for x in color_rgb.split()]
    angle_rad = math.radians(angle_deg)
    cos_a     = math.cos(angle_rad)
    sin_a     = math.sin(angle_rad)
    cx, cy    = page_w / 2, page_h / 2
    tw        = len(text) * font_size * 0.55
    th        = font_size * 0.35

    ps_text = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")

    def tm_line(tx_local, ty_local):
        ex = cx + tx_local * cos_a - ty_local * sin_a
        ey = cy + tx_local * sin_a + ty_local * cos_a
        return "{:.6f} {:.6f} {:.6f} {:.6f} {:.2f} {:.2f} Tm ({}) Tj".format(
            cos_a, sin_a, -sin_a, cos_a, ex, ey, ps_text)

    # Step basé sur la largeur réelle du texte + marge de 20%
    step  = max(int(tw * 1.2), int(font_size * 2))
    lines = [
        "q",
        # Clipping rectangle = exactement la page, rien ne dépasse
        "0 0 {:.2f} {:.2f} re W n".format(page_w, page_h),
        "/GS1 gs",
        "{:.3f} {:.3f} {:.3f} rg".format(r, g, b),
        "BT", "/F1 {} Tf".format(font_size),
    ]
    if diagonal:
        rng = range(-step * 3, step * 3 + 1, step)
        for ty in rng:
            for tx in rng:
                lines.append(tm_line(tx, ty))
    else:
        lines.append(tm_line(-tw / 2, -th / 2))
    lines  += ["ET", "Q"]
    stream  = "\n".join(lines).encode("latin-1")
    slen    = len(stream)

    o = []
    o.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    o.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    o.append((
        "3 0 obj\n<< /Type /Page /Parent 2 0 R "
        "/MediaBox [0 0 {:.2f} {:.2f}] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> /ExtGState << /GS1 6 0 R >> >> "
        ">>\nendobj\n".format(page_w, page_h)
    ).encode("latin-1"))
    o.append(
        "4 0 obj\n<< /Length {} >>\nstream\n".format(slen).encode("latin-1")
        + stream + b"\nendstream\nendobj\n"
    )
    o.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 "
             b"/BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n")
    o.append((
        "6 0 obj\n<< /Type /ExtGState /ca {:.3f} /CA {:.3f} >>\nendobj\n"
        .format(opacity, opacity)
    ).encode("latin-1"))

    pdf     = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = []
    pos     = len(pdf)
    for chunk in o:
        offsets.append(pos)
        pdf += chunk
        pos += len(chunk)

    xref_pos = pos
    xref     = b"xref\n0 7\n0000000000 65535 f \n"
    for off in offsets:
        xref += "{:010d} 00000 n \n".format(off).encode()
    trailer  = "trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{}\n%%EOF\n".format(
        xref_pos).encode("latin-1")
    return pdf + xref + trailer


class WatermarkDialog(Adw.Window):
    __gtype_name__ = "WatermarkPDFSettingsDialog"

    def __init__(self, callback):
        super().__init__(title=T["dialog_title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_default_size(420, -1)
        self._callback = callback

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_margin_top(16)
        outer.set_margin_bottom(16)
        outer.set_margin_start(18)
        outer.set_margin_end(18)

        # -- Texte --
        outer.append(self._section_label(T["text_label"]))
        self._text_entry = Gtk.Entry()
        self._text_entry.set_placeholder_text(T["text_hint"])
        self._text_entry.set_text("CONFIDENTIEL" if _lang.startswith("fr") else "CONFIDENTIAL")
        outer.append(self._text_entry)

        # -- Taille police --
        outer.append(self._section_label(f"{T['size_label']} : "))
        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._size_spin = Gtk.SpinButton.new_with_range(10, 200, 5)
        self._size_spin.set_value(25)
        self._size_label = Gtk.Label(label="25 pt")
        self._size_spin.connect("value-changed", lambda s: self._size_label.set_text(f"{int(s.get_value())} pt"))
        size_box.append(self._size_spin)
        size_box.append(self._size_label)
        outer.append(size_box)

        # -- Opacité --
        outer.append(self._section_label(f"{T['opacity_label']} : "))
        opacity_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._opacity_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.05, 1.0, 0.05)
        self._opacity_scale.set_value(0.15)
        self._opacity_scale.set_hexpand(True)
        self._opacity_scale.set_draw_value(False)
        self._opacity_lbl = Gtk.Label(label="15%")
        self._opacity_scale.connect("value-changed", lambda s: self._opacity_lbl.set_text(f"{int(s.get_value()*100)}%"))
        opacity_box.append(self._opacity_scale)
        opacity_box.append(self._opacity_lbl)
        outer.append(opacity_box)

        # -- Angle --
        outer.append(self._section_label(f"{T['angle_label']} : "))
        angle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._angle_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -90, 90, 5)
        self._angle_scale.set_value(45)
        self._angle_scale.set_hexpand(True)
        self._angle_scale.set_draw_value(False)
        self._angle_lbl = Gtk.Label(label="45°")
        self._angle_scale.connect("value-changed", lambda s: self._angle_lbl.set_text(f"{int(s.get_value())}°"))
        angle_box.append(self._angle_scale)
        angle_box.append(self._angle_lbl)
        outer.append(angle_box)

        # -- Couleur --
        outer.append(self._section_label(T["color_label"]))
        color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._color_buttons = []
        group = None
        for name, rgb in T["colors"]:
            btn = Gtk.CheckButton(label=name)
            btn.rgb = rgb
            if group is None:
                group = btn
                btn.set_active(True)
            else:
                btn.set_group(group)
            color_box.append(btn)
            self._color_buttons.append(btn)
        outer.append(color_box)

        # -- Position --
        outer.append(self._section_label(T["position_label"]))
        pos_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._pos_center = Gtk.CheckButton(label=T["pos_center"])
#        self._pos_center.set_active(True)
        self._pos_diagonal = Gtk.CheckButton(label=T["pos_diagonal"])
        self._pos_diagonal.set_active(True)
        self._pos_diagonal.set_group(self._pos_center)
        pos_box.append(self._pos_center)
        pos_box.append(self._pos_diagonal)
        outer.append(pos_box)

        # -- Flatten --
        outer.append(self._section_label("Aplatir (Flatten)"))
        flatten_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self._flatten_check = Gtk.CheckButton(
            label="Fusionner en image (recommandé pour documents sensibles)")
        self._flatten_check.set_active(True)
        flatten_box.append(self._flatten_check)
        outer.append(flatten_box)

        # -- DPI (visible uniquement si flatten activé) --
        dpi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        dpi_lbl = Gtk.Label(label="Résolution :")
        dpi_lbl.set_halign(Gtk.Align.START)
        self._dpi_spin = Gtk.SpinButton.new_with_range(72, 300, 25)
        self._dpi_spin.set_value(200)
        self._dpi_value_lbl = Gtk.Label(label="200 DPI")
        self._dpi_spin.connect("value-changed",
            lambda s: self._dpi_value_lbl.set_text(f"{int(s.get_value())} DPI"))
        dpi_box.append(dpi_lbl)
        dpi_box.append(self._dpi_spin)
        dpi_box.append(self._dpi_value_lbl)
        outer.append(dpi_box)

        # Lier la sensibilité du spinner à la checkbox
        self._flatten_check.connect("toggled",
            lambda btn: dpi_box.set_sensitive(btn.get_active()))

        # -- Boutons --
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(6)

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

    def _section_label(self, text):
        lbl = Gtk.Label(label=f"<b>{text}</b>")
        lbl.set_use_markup(True)
        lbl.set_halign(Gtk.Align.START)
        return lbl

    def _get_color(self):
        for btn in self._color_buttons:
            if btn.get_active():
                return btn.rgb
        return "1 0 0"

    def _respond(self, ok: bool):
        if not ok:
            self._callback(None)
            self.destroy()
            return

        text = self._text_entry.get_text().strip()
        if not text:
            Gtk.AlertDialog(message=T["err_empty"]).show(self)
            return

        self._callback({
            "text":     text,
            "opacity":  self._opacity_scale.get_value(),
            "angle":    self._angle_scale.get_value(),
            "size":     int(self._size_spin.get_value()),
            "color":    self._get_color(),
            "diagonal": self._pos_diagonal.get_active(),
            "flatten":  self._flatten_check.get_active(),
            "dpi":      int(self._dpi_spin.get_value()),
        })
        self.destroy()


# ---------------------------------------------------------------------------
# Progress dialog
# ---------------------------------------------------------------------------

class WatermarkProgressDialog(Adw.Window):
    __gtype_name__ = "WatermarkPDFProgressDialog"

    def __init__(self, src: str, dst: str, settings: dict, done_callback):
        super().__init__(title=T["dialog_title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_deletable(False)
        self.set_default_size(340, -1)

        self._src      = src
        self._dst      = dst
        self._settings = settings
        self._tmp      = dst + ".tmp_wm.pdf"
        self._process  = None
        self._ps_tmp   = None
        self._wm_tmp   = None
        self._flat_tmp = None
        self._done_cb  = done_callback

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        box.append(Gtk.Label(label=T["processing"]))

        self._bar = Gtk.ProgressBar()
        self._bar.set_pulse_step(0.05)
        box.append(self._bar)

        cancel_btn = Gtk.Button(label=T["cancel"])
        cancel_btn.connect("clicked", self._on_cancel)
        box.append(cancel_btn)

        toolbar_view.set_content(box)
        self.set_content(toolbar_view)

        self._thread = threading.Thread(target=self._apply, daemon=True)
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
        self._cleanup()
        self._done_cb(False)
        self.destroy()

    def _cleanup(self):
        for f in [getattr(self, "_tmp", None),
                  getattr(self, "_ps_tmp", None),
                  getattr(self, "_wm_tmp", None),
                  getattr(self, "_flat_tmp", None)]:
            if f:
                try: os.remove(f)
                except FileNotFoundError: pass

    def _apply(self):
        import tempfile, shutil
        s = self._settings
        # Étape 1 : générer le PDF de filigrane
        # Tous les tmp dans le même dossier que la destination → pas de cross-filesystem
        dst_dir = os.path.dirname(self._dst)
        try:
            wm_fd, self._wm_tmp = tempfile.mkstemp(suffix=".pdf", dir=dst_dir)
            os.close(wm_fd)
            out_fd, self._tmp   = tempfile.mkstemp(suffix=".pdf", dir=dst_dir)
            os.close(out_fd)
        except Exception as exc:
            GObject.idle_add(self._finish_error, str(exc))
            return

        # Génération du PDF de filigrane en Python pur (plus de GS ici)
        try:
            wm_pdf = _build_watermark_pdf(
                text=s["text"], opacity=s["opacity"], angle_deg=s["angle"],
                font_size=s["size"], color_rgb=s["color"], diagonal=s["diagonal"]
            )
            with open(self._wm_tmp, "wb") as f:
                f.write(wm_pdf)
        except Exception as exc:
            GObject.idle_add(self._finish_error, str(exc))
            return

        # Étape 2 : pypdf stampe le filigrane sur chaque page source
        try:
            from pypdf import PdfReader, PdfWriter, Transformation
        except ImportError:
            self._cleanup()
            GObject.idle_add(self._finish_error,
                "pypdf est requis. Installez-le avec :\n"
                "sudo apt install python3-pypdf")
            return

        try:
            wm_reader  = PdfReader(self._wm_tmp)
            wm_page    = wm_reader.pages[0]
            wm_w = float(wm_page.mediabox.width)
            wm_h = float(wm_page.mediabox.height)

            src_reader = PdfReader(self._src)
            writer     = PdfWriter()

            for page in src_reader.pages:
                pw = float(page.mediabox.width)
                ph = float(page.mediabox.height)
                # Adapter le filigrane aux dimensions de chaque page
                t = Transformation().scale(pw / wm_w, ph / wm_h)
                page.merge_transformed_page(wm_page, t)
                writer.add_page(page)

            with open(self._tmp, "wb") as out:
                writer.write(out)

        except Exception as exc:
            self._cleanup()
            GObject.idle_add(self._finish_error, str(exc))
            return
        finally:
            try: os.remove(self._wm_tmp)
            except FileNotFoundError: pass

        # Étape 3 optionnelle : flatten (rasterisation via GS)
        if s.get("flatten", False):
            flat_fd, self._flat_tmp = tempfile.mkstemp(suffix=".pdf", dir=dst_dir)
            os.close(flat_fd)
            cmd_flat = [
                GS_BIN,
                "-sDEVICE=pdfimage24",
                f"-r{s.get('dpi', 200)}",
                "-dNOPAUSE", "-dQUIET", "-dBATCH",
                f"-sOutputFile={self._flat_tmp}",
                self._tmp,
            ]
            try:
                rc_flat = subprocess.run(cmd_flat).returncode
            except Exception as exc:
                GObject.idle_add(self._finish_error, str(exc))
                return
            if rc_flat != 0:
                self._cleanup()
                GObject.idle_add(self._finish_error, T["err_failed"].format(code=rc_flat))
                return
            src_for_dst = self._flat_tmp
        else:
            src_for_dst = self._tmp

        try:
            shutil.copy2(src_for_dst, self._dst)
            # Nettoyer tous les fichiers temporaires
            for f in [self._tmp, self._wm_tmp, self._flat_tmp]:
                if f and os.path.exists(f):
                    try: os.remove(f)
                    except OSError: pass
        except OSError as exc:
            GObject.idle_add(self._finish_error, str(exc))
            return

        GObject.idle_add(self._finish_ok)

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

class WatermarkPDFExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "WatermarkPDFExtension"

    def get_file_items(self, files):
        pdfs = [
            f for f in files
            if f.get_uri_scheme() == "file"
            and f.get_mime_type() == "application/pdf"
        ]
        if not pdfs:
            return []

        item = Nautilus.MenuItem(
            name="WatermarkPDF::Watermark",
            label=T["menu_label"],
            tip="Add a text watermark to the selected PDF file(s)",
        )
        item.connect("activate", self._on_activate, pdfs)
        return [item]

    def get_background_items(self, folder):
        return []

    def _on_activate(self, _item, pdf_items):
        if not os.path.isfile(GS_BIN) or not os.access(GS_BIN, os.X_OK):
            _show_message(T["err_gs"])
            return

        def on_settings(settings):
            if settings is None:
                return
            self._process_files(pdf_items, settings)

        WatermarkDialog(callback=on_settings).present()

    def _process_files(self, pdf_items, settings, index=0):
        if index >= len(pdf_items):
            return

        src = pdf_items[index].get_location().get_path()

        def do_watermark(dst):
            if dst is None:
                return

            def on_done(success):
                if success:
                    _show_message(T["done_msg"].format(name=os.path.basename(src)))
                self._process_files(pdf_items, settings, index + 1)

            WatermarkProgressDialog(src, dst, settings, done_callback=on_done).present()

        if len(pdf_items) == 1:
            dlg = Gtk.FileDialog(title=T["save_as"])
            dlg.set_initial_folder(Gio.File.new_for_path(os.path.dirname(src)))
            dlg.set_initial_name(os.path.basename(_suggest_output(src)))
            dlg.save(_nautilus_window(), None, self._on_save_response, do_watermark)
        else:
            do_watermark(_suggest_output(src))

    def _on_save_response(self, dlg, result, callback):
        try:
            callback(dlg.save_finish(result).get_path())
        except Exception:
            callback(None)
