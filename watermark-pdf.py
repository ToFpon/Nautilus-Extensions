#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Watermark PDF – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), imagemagick, python3-gi, gir1.2-adw-1
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
        "err_gs":         "imagemagick est introuvable. Veuillez l'installer.",
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
        "err_gs":         "imagemagick is not installed. Please install it first.",
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

CONVERT_BIN = shutil.which("convert") or "/usr/bin/convert"
STAMP_TIMEOUT_S = int(os.environ.get("WATERMARK_STAMP_TIMEOUT_S", "180"))
WATERMARK_DIAG_LAND_STEPX_MUL = float(os.environ.get("WATERMARK_DIAG_LAND_STEPX_MUL", "0.78"))
WATERMARK_DIAG_LAND_STEPY_MUL = float(os.environ.get("WATERMARK_DIAG_LAND_STEPY_MUL", "1.18"))
WATERMARK_DIAG_POR_STEPX_MUL  = float(os.environ.get("WATERMARK_DIAG_POR_STEPX_MUL",  "0.92"))
WATERMARK_DIAG_POR_STEPY_MUL  = float(os.environ.get("WATERMARK_DIAG_POR_STEPY_MUL",  "0.92"))
WATERMARK_DIAG_MASTER_STEPX_MUL = float(os.environ.get("WATERMARK_DIAG_MASTER_STEPX_MUL", "0.92"))
WATERMARK_DIAG_MASTER_STEPY_MUL = float(os.environ.get("WATERMARK_DIAG_MASTER_STEPY_MUL", "0.92"))


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

def _build_watermark_pdf(text, opacity, angle_deg, font_size, color_rgb,
                          diagonal, page_w=595, page_h=842):
    """Génère un PDF filigrane 1-page via PNG alpha (ImageMagick) puis embarquement SMask (maison via PIL)."""
    import tempfile, subprocess, zlib

    r, g, b = [float(x) for x in color_rgb.split()]
    fill    = "rgba({},{},{},{:.3f})".format(
                int(r*255), int(g*255), int(b*255), opacity)

    fd_png, tmp_png = tempfile.mkstemp(suffix=".png")
    os.close(fd_png)

    text_w = int(font_size * 0.65 * len(text))
    step_x = max(text_w + int(font_size * 3), int(page_w * 0.35))
    step_y = max(int(font_size * 3.5), int(page_h * 0.18))

    # Eviter le clipping des lettres (rotation + placement) :
    # on génère une toile un peu plus grande.
    page_wi = float(page_w)
    page_hi = float(page_h)
    expand = 1.0 + min(0.12, max(0.04, float(font_size) / 1200.0))

    # Pour la répétition diagonale, on génère un "masque master" carré.
    # Ensuite le stamping fait un scaling uniforme + centrage, ce qui rend
    # le motif plus identique entre portrait et paysage.
    if diagonal:
        master = max(page_wi, page_hi)
        work_w = int(master * expand + 0.5)
        work_h = work_w
        off_x  = 0.0
        off_y  = 0.0
    else:
        work_w = int(page_wi * expand + 0.5)
        work_h = int(page_hi * expand + 0.5)
        off_x  = (work_w - page_wi) / 2.0
        off_y  = (work_h - page_hi) / 2.0

    draws = []
    if diagonal:
        # Masque master : recalculer pas uniquement via une "taille effective"
        # (le plus petit côté) pour garder la même densité visuelle en portrait
        # et en paysage.
        effective = min(page_wi, page_hi)
        step_x = max(text_w + int(font_size * 3), int(effective * 0.35))
        step_y = max(int(font_size * 3.5), int(effective * 0.18))

        step_x = max(1, int(step_x * WATERMARK_DIAG_MASTER_STEPX_MUL))
        step_y = max(1, int(step_y * WATERMARK_DIAG_MASTER_STEPY_MUL))

        cx = work_w / 2.0
        cy = work_h / 2.0
        for ty in range(-int(work_h), int(work_h * 2), step_y):
            for tx in range(-int(work_w), int(work_w * 2), step_x):
                d = "translate {},{} rotate {} text 0,0 '{}'".format(
                    tx + cx, ty + cy, -angle_deg, text)
                draws += ["-draw", d]
    else:
        cx = int(page_w // 2 + off_x)
        cy = int(page_h // 2 + off_y)
        d = "translate {},{} rotate {} text 0,0 '{}'".format(
            cx, cy, -angle_deg, text)
        draws = ["-draw", d]

    cmd = [CONVERT_BIN,
           "-size", "{}x{}".format(work_w, work_h),
           "xc:none", "-font", "Arial",
           "-pointsize", str(font_size),
           "-fill", fill, "-gravity", "None",
           ] + draws + [tmp_png]

    # Timeout pour éviter les blocages si ImageMagick reste coincé
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        os.remove(tmp_png)
        raise RuntimeError(res.stderr)

    try:
        from PIL import Image
        img     = Image.open(tmp_png).convert("RGBA")
        w, h    = img.size
        rgb_c   = zlib.compress(img.convert("RGB").tobytes(), 6)
        alpha_c = zlib.compress(img.split()[3].tobytes(), 6)
        cont_c  = zlib.compress(
            "{} 0 0 {} 0 0 cm /Im1 Do".format(int(w), int(h)).encode(), 6)

        def mk(s):
            return s.encode() if isinstance(s, str) else s

        o1 = mk("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        o2 = mk("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
        o3 = mk("3 0 obj\n<< /Type /Page /Parent 2 0 R"
                " /MediaBox [0 0 {} {}] /Contents 4 0 R"
                " /Resources << /XObject << /Im1 5 0 R >> >>"
                " >>\nendobj\n".format(int(w), int(h)))
        o4 = (mk("4 0 obj\n<< /Length {} /Filter /FlateDecode >>\nstream\n"
                 .format(len(cont_c)))
              + cont_c + mk("\nendstream\nendobj\n"))
        o5 = (mk("5 0 obj\n<< /Type /XObject /Subtype /Image"
                 " /Width {} /Height {} /ColorSpace /DeviceRGB"
                 " /BitsPerComponent 8 /Filter /FlateDecode"
                 " /SMask 6 0 R /Length {} >>\nstream\n".format(w, h, len(rgb_c)))
              + rgb_c + mk("\nendstream\nendobj\n"))
        o6 = (mk("6 0 obj\n<< /Type /XObject /Subtype /Image"
                 " /Width {} /Height {} /ColorSpace /DeviceGray"
                 " /BitsPerComponent 8 /Filter /FlateDecode"
                 " /Length {} >>\nstream\n".format(w, h, len(alpha_c)))
              + alpha_c + mk("\nendstream\nendobj\n"))

        objs = [o1, o2, o3, o4, o5, o6]
        pdf  = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offs, pos = [], len(pdf)
        for chunk in objs:
            offs.append(pos); pdf += chunk; pos += len(chunk)
        n  = len(objs) + 1
        xp = pos
        xref = "xref\n0 {}\n0000000000 65535 f \n".format(n).encode()
        for off in offs:
            xref += "{:010d} 00000 n \n".format(off).encode()
        trailer = (
            "trailer\n<< /Size {} /Root 1 0 R >>\n"
            "startxref\n{}\n%%EOF\n".format(n, xp)
        ).encode()
        return pdf + xref + trailer
    finally:
        os.remove(tmp_png)

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
        self._size_spin.set_value(60)
        self._size_label = Gtk.Label(label="60 pt")
        self._size_spin.connect("value-changed", lambda s: self._size_label.set_text(f"{int(s.get_value())} pt"))
        size_box.append(self._size_spin)
        size_box.append(self._size_label)
        outer.append(size_box)

        # -- Opacité --
        outer.append(self._section_label(f"{T['opacity_label']} : "))
        opacity_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._opacity_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.05, 1.0, 0.05)
        self._opacity_scale.set_value(0.3)
        self._opacity_scale.set_hexpand(True)
        self._opacity_scale.set_draw_value(False)
        self._opacity_lbl = Gtk.Label(label="30%")
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
        self._pos_center.set_active(True)
        self._pos_diagonal = Gtk.CheckButton(label=T["pos_diagonal"])
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

        self._status_lbl = Gtk.Label(label="")
        self._status_lbl.add_css_class("dim-label")
        box.append(self._status_lbl)

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

    def _set_status(self, text: str):
        try:
            self._status_lbl.set_text(text)
        except Exception:
            pass

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
            GObject.idle_add(self._set_status, "Génération du filigrane…")
            # Générer le watermark avec les dimensions réelles d'au moins une
            # page pour que la répétition (mode diagonale) soit correcte en
            # paysage vs portrait.
            page_w = 595
            page_h = 842
            try:
                from pypdf import PdfReader as _PdfReader
                _src_reader = _PdfReader(self._src)
                if _src_reader.pages:
                    page_w = float(_src_reader.pages[0].mediabox.width)
                    page_h = float(_src_reader.pages[0].mediabox.height)
            except Exception:
                # Si on ne peut pas lire les dimensions, on retombe sur A4
                # par défaut (mieux que de planter).
                pass
            wm_pdf = _build_watermark_pdf(
                text=s["text"], opacity=s["opacity"], angle_deg=s["angle"],
                font_size=s["size"], color_rgb=s["color"], diagonal=s["diagonal"],
                page_w=page_w, page_h=page_h
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

            # Certaines PDFs peuvent provoquer un traitement très long/bloquant
            # côté pypdf pendant writer.write(). Pour éviter que ça reste figé
            # sans retour, on lance le stamping dans un sous-process avec timeout.
            GObject.idle_add(self._set_status, "Application… (filigrane sur pages)")
            GObject.idle_add(self._bar.set_fraction, 0.05)

            diagonal_flag = bool(s.get("diagonal", False))
            stamp_code = r'''
import sys
from pypdf import PdfReader, PdfWriter, Transformation

src = sys.argv[1]
wm  = sys.argv[2]
out = sys.argv[3]
diag = sys.argv[4].lower() in ("1","true","yes","on")

wm_reader  = PdfReader(wm)
wm_page    = wm_reader.pages[0]
wm_w = float(wm_page.mediabox.width)
wm_h = float(wm_page.mediabox.height)

src_reader = PdfReader(src)
writer     = PdfWriter()

for page in src_reader.pages:
    pw = float(page.mediabox.width)
    ph = float(page.mediabox.height)
    if diag:
        # Pour un masque "master" carré, on veut conserver la densité
        # visuelle portrait/paysage en scalant sur la dimension maximale
        # (crop sur l'autre dimension) et en ancrant en bas-gauche.
        s_scale = max(pw / wm_w, ph / wm_h)
        tx = 0
        ty = 0
    else:
        # Mode centre (non-diagonal) : fit complet et centrage.
        s_scale = min(pw / wm_w, ph / wm_h)
        tx = (pw - wm_w * s_scale) / 2
        ty = (ph - wm_h * s_scale) / 2
    t  = Transformation().scale(sx=s_scale, sy=s_scale).translate(tx=tx, ty=ty)
    page.merge_transformed_page(wm_page, t)
    writer.add_page(page)

with open(out, "wb") as f:
    writer.write(f)
'''

            import sys as _sys
            try:
                rc = subprocess.run(
                    [_sys.executable, "-c", stamp_code,
                     self._src, self._wm_tmp, self._tmp, "1" if diagonal_flag else "0"],
                    capture_output=True, text=True, timeout=STAMP_TIMEOUT_S
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError("Timeout while applying watermark (pypdf > 180s).")
            if rc.returncode != 0:
                raise RuntimeError(rc.stderr.strip() or f"pypdf stamp failed (code {rc.returncode})")

            GObject.idle_add(self._bar.set_fraction, 1.0)

        except Exception as exc:
            self._cleanup()
            GObject.idle_add(self._finish_error, str(exc))
            return
        finally:
            try: os.remove(self._wm_tmp)
            except FileNotFoundError: pass

        # Étape 3 optionnelle : flatten (rasterisation via ImageMagick)
        if s.get("flatten", False):
            flat_fd, self._flat_tmp = tempfile.mkstemp(suffix=".pdf", dir=dst_dir)
            os.close(flat_fd)
            dpi = s.get("dpi", 200)
            cmd_flat = [
                CONVERT_BIN,
                "-density", str(dpi),
                "-compress", "jpeg",
                "-quality", "92",
                self._tmp,
                self._flat_tmp,
            ]
            try:
                GObject.idle_add(self._set_status, "Flatten (rasterisation)…")
                rc_flat = subprocess.run(cmd_flat, capture_output=True, timeout=120).returncode
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
        if not os.path.isfile(CONVERT_BIN) or not os.access(CONVERT_BIN, os.X_OK):
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
