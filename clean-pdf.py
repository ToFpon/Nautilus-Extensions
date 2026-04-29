#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Clean PDF — Nautilus Python Extension
# DESC: Clean scanned PDFs + OCR (searchable text layer)
# REQUIRES: python3-nautilus, python3-gi, gir1.2-adw-1,
#            poppler-utils, imagemagick, unpaper, img2pdf, tesseract-ocr
# INSTALL:
#   cp clean-pdf.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q

import os
import shutil
import subprocess
import tempfile
import threading
import locale

import gi
gi.require_version("Gtk",      "4.0")
gi.require_version("Adw",      "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gio, GLib, Nautilus, Pango

# ---------------------------------------------------------------------------
# Binaires
# ---------------------------------------------------------------------------
PDFTOPPM_BIN  = shutil.which("pdftoppm")  or "/usr/bin/pdftoppm"
CONVERT_BIN   = shutil.which("convert")   or "/usr/bin/convert"
TESSERACT_BIN = shutil.which("tesseract") or "/usr/bin/tesseract"
IMG2PDF_BIN   = shutil.which("img2pdf")   or "/usr/bin/img2pdf"

# Langues Tesseract disponibles
def _available_langs():
    try:
        r = subprocess.run([TESSERACT_BIN, "--list-langs"],
                           capture_output=True, text=True)
        # Tesseract écrit sur stderr, certaines versions sur stdout
        output = r.stderr + r.stdout
        langs = [l.strip() for l in output.splitlines()
                 if l.strip()
                 and not l.startswith("List")
                 and not l.startswith("Tesseract")
                 and "/" not in l]
        return [l for l in langs if l not in ("osd", "")]
    except Exception:
        return ["eng"]

AVAILABLE_LANGS = _available_langs()

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":       "Nettoyer / OCR le PDF scanné",
        "title":            "Nettoyage PDF scanné",
        "section_clean":    "Nettoyage de l'image",
        "whiten":           "Blanchir le fond",
        "whiten_hint":      "Supprime le gris de fond des scans.",
        "white_threshold":  "Seuil de blanc (%)",
        "white_hint":       "Plus bas = plus de pixels blanchis. Défaut : 80%.",
        "erode_dilate":     "Réduire le bruit (érosion/dilatation)",
        "erode_hint":       "Atténue les artéfacts sans toucher au texte.",
        "section_ocr":      "OCR — Couche texte",
        "ocr_enable":       "Activer l'OCR",
        "ocr_hint":         "Ajoute une couche texte invisible — PDF cherchable et copiable.",
        "ocr_lang":         "Langue",
        "ocr_mode":         "Mode de sortie",
        "ocr_image_text":   "Image + texte invisible (recommandé)",
        "ocr_text_only":    "Texte seul (léger)",
        "section_dpi":      "Résolution",
        "dpi_label":        "DPI",
        "dpi_hint":         "300 dpi recommandé pour l'OCR.",
        "section_deskew":   "Redressement",
        "deskew":           "Redresser les pages (deskew)",
        "deskew_hint":      "Corrige l'inclinaison des pages scannées.",
        "section_output":   "Sortie",
        "suffix":           "Suffixe",
        "clean_btn":        "Nettoyer",
        "step_convert":     "Conversion PDF → images…",
        "step_clean":       "Nettoyage page {page}/{total}…",
        "step_ocr":         "OCR page {page}/{total}…",
        "step_assemble":    "Assemblage du PDF…",
        "err_title":        "Erreur",
        "ok":               "OK",
        "lang_fra":         "Français",
        "lang_eng":         "Anglais",
        "lang_deu":         "Allemand",
    }
else:
    T = {
        "menu_label":       "Clean / OCR scanned PDF",
        "title":            "Clean Scanned PDF",
        "section_clean":    "Image cleaning",
        "whiten":           "Whiten background",
        "whiten_hint":      "Removes gray background from scans.",
        "white_threshold":  "White threshold (%)",
        "white_hint":       "Lower = more pixels whitened. Default: 80%.",
        "erode_dilate":     "Reduce noise (erode/dilate)",
        "erode_hint":       "Smooths scan artifacts without touching text.",
        "section_ocr":      "OCR — Text layer",
        "ocr_enable":       "Enable OCR",
        "ocr_hint":         "Adds invisible text layer — searchable and copyable PDF.",
        "ocr_lang":         "Language",
        "ocr_mode":         "Output mode",
        "ocr_image_text":   "Image + invisible text (recommended)",
        "ocr_text_only":    "Text only (lightweight)",
        "section_dpi":      "Resolution",
        "dpi_label":        "DPI",
        "dpi_hint":         "300 dpi recommended for OCR.",
        "section_deskew":   "Straightening",
        "deskew":           "Deskew pages",
        "deskew_hint":      "Corrects page tilt from scanning.",
        "section_output":   "Output",
        "suffix":           "Suffix",
        "clean_btn":        "Clean",
        "step_convert":     "Converting PDF to images…",
        "step_clean":       "Cleaning page {page}/{total}…",
        "step_ocr":         "OCR page {page}/{total}…",
        "step_assemble":    "Assembling PDF…",
        "err_title":        "Error",
        "ok":               "OK",
        "lang_fra":         "French",
        "lang_eng":         "English",
        "lang_deu":         "German",
    }

LANG_LABELS = {"fra": T["lang_fra"], "eng": T["lang_eng"], "deu": T["lang_deu"]}

# ---------------------------------------------------------------------------
# Helpers UI
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    return app.get_active_window() if app else None

def _section(title):
    lbl = Gtk.Label()
    lbl.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
    lbl.set_halign(Gtk.Align.START)
    lbl.set_margin_top(14)
    lbl.set_margin_bottom(2)
    return lbl

def _hint(text):
    lbl = Gtk.Label(label=text)
    lbl.set_halign(Gtk.Align.START)
    lbl.set_wrap(True)
    lbl.set_max_width_chars(52)
    lbl.add_css_class("dim-label")
    lbl.add_css_class("caption")
    lbl.set_margin_bottom(2)
    return lbl

def _switch_row(label, active=True):
    box = Gtk.Box(spacing=12)
    lbl = Gtk.Label(label=label)
    lbl.set_halign(Gtk.Align.START)
    lbl.set_hexpand(True)
    sw  = Gtk.Switch()
    sw.set_active(active)
    sw.set_valign(Gtk.Align.CENTER)
    box.append(lbl)
    box.append(sw)
    return box, sw

def _spin_row(label, min_v, max_v, step, value):
    box  = Gtk.Box(spacing=12)
    lbl  = Gtk.Label(label=label)
    lbl.set_halign(Gtk.Align.START)
    lbl.set_hexpand(True)
    adj  = Gtk.Adjustment(value=value, lower=min_v, upper=max_v,
                          step_increment=step, page_increment=step * 5)
    spin = Gtk.SpinButton(adjustment=adj)
    spin.set_valign(Gtk.Align.CENTER)
    box.append(lbl)
    box.append(spin)
    return box, spin

def _combo_row(label, items):
    box = Gtk.Box(spacing=12)
    lbl = Gtk.Label(label=label)
    lbl.set_halign(Gtk.Align.START)
    lbl.set_hexpand(True)
    combo = Gtk.DropDown.new_from_strings(items)
    combo.set_valign(Gtk.Align.CENTER)
    box.append(lbl)
    box.append(combo)
    return box, combo

# ---------------------------------------------------------------------------
# Clean PDF Window
# ---------------------------------------------------------------------------

class CleanPDFWindow(Adw.Window):
    __gtype_name__ = "CleanPDFWindow"

    def __init__(self, pdf_path):
        super().__init__()
        self._pdf = pdf_path
        self.set_default_size(500, 830)
        self.set_resizable(True)
        self.set_transient_for(_nautilus_window())
        self.set_title(T["title"])

        tv  = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_decoration_layout(":close")
        hdr.set_title_widget(Gtk.Label(label=T["title"]))
        tv.add_top_bar(hdr)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(18); box.set_margin_end(18)
        box.set_margin_top(8);    box.set_margin_bottom(18)

        # Fichier source
        src_lbl = Gtk.Label()
        src_lbl.set_markup(
            f"<b>{GLib.markup_escape_text(os.path.basename(pdf_path))}</b>")
        src_lbl.set_halign(Gtk.Align.START)
        src_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        src_lbl.set_max_width_chars(50)
        box.append(src_lbl)
        box.append(Gtk.Separator(margin_top=6, margin_bottom=2))

        # ── Résolution ──────────────────────────────────────────────────────
        box.append(_section(T["section_dpi"]))
        dpi_row, self._dpi = _spin_row(T["dpi_label"], 72, 600, 10, 300)
        box.append(dpi_row)
        box.append(_hint(T["dpi_hint"]))

        # ── Nettoyage fond ──────────────────────────────────────────────────
        box.append(_section(T["section_clean"]))

        whiten_row, self._whiten = _switch_row(T["whiten"], active=True)
        box.append(whiten_row)
        box.append(_hint(T["whiten_hint"]))

        wt_row, self._white_threshold = _spin_row(
            T["white_threshold"], 50, 95, 5, 80)
        box.append(wt_row)
        box.append(_hint(T["white_hint"]))

        erode_row, self._erode = _switch_row(T["erode_dilate"], active=True)
        box.append(erode_row)
        box.append(_hint(T["erode_hint"]))

        # ── Redressement ────────────────────────────────────────────────────
        box.append(_section(T["section_deskew"]))
        deskew_row, self._deskew = _switch_row(T["deskew"], active=True)
        box.append(deskew_row)
        box.append(_hint(T["deskew_hint"]))

        # ── OCR ─────────────────────────────────────────────────────────────
        box.append(_section(T["section_ocr"]))

        ocr_row, self._ocr_enable = _switch_row(T["ocr_enable"], active=True)
        box.append(ocr_row)
        box.append(_hint(T["ocr_hint"]))

        # Langue
        lang_labels = [LANG_LABELS.get(l, l) for l in AVAILABLE_LANGS]
        lang_row, self._lang_combo = _combo_row(T["ocr_lang"], lang_labels)
        box.append(lang_row)

        # Sélectionner français par défaut si dispo
        if "fra" in AVAILABLE_LANGS:
            self._lang_combo.set_selected(AVAILABLE_LANGS.index("fra"))

        # Mode sortie
        modes = [T["ocr_image_text"], T["ocr_text_only"]]
        mode_row, self._mode_combo = _combo_row(T["ocr_mode"], modes)
        box.append(mode_row)

        # Griser les options OCR si désactivé
        def _on_ocr_toggle(sw, _):
            active = sw.get_active()
            lang_row.set_sensitive(active)
            mode_row.set_sensitive(active)
        self._ocr_enable.connect("notify::active", _on_ocr_toggle)

        # ── Sortie ──────────────────────────────────────────────────────────
        box.append(_section(T["section_output"]))
        suf_box = Gtk.Box(spacing=12)
        suf_lbl = Gtk.Label(label=T["suffix"])
        suf_lbl.set_halign(Gtk.Align.START)
        suf_lbl.set_hexpand(True)
        self._suffix = Gtk.Entry()
        self._suffix.set_text("-cleaned")
        self._suffix.set_width_chars(12)
        suf_box.append(suf_lbl)
        suf_box.append(self._suffix)
        box.append(suf_box)

        box.append(Gtk.Separator(margin_top=10, margin_bottom=2))

        # ── Bouton + progression ─────────────────────────────────────────────
        self._clean_btn = Gtk.Button(label=T["clean_btn"])
        self._clean_btn.add_css_class("suggested-action")
        self._clean_btn.connect("clicked", self._on_clean)
        box.append(self._clean_btn)

        self._prog = Gtk.ProgressBar()
        self._prog.set_visible(False)
        self._prog.set_margin_top(8)
        box.append(self._prog)

        self._status = Gtk.Label()
        self._status.set_visible(False)
        self._status.add_css_class("dim-label")
        self._status.add_css_class("caption")
        box.append(self._status)

        scroll.set_child(box)
        tv.set_content(scroll)
        self.set_content(tv)

        sc = Gtk.ShortcutController()
        sc.set_scope(Gtk.ShortcutScope.MANAGED)
        sc.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("Escape"),
            Gtk.CallbackAction.new(lambda *_: self.close() or True)))
        self.add_controller(sc)

    # -- Pipeline -------------------------------------------------------------

    def _on_clean(self, _):
        self._clean_btn.set_sensitive(False)
        self._prog.set_visible(True)
        self._prog.set_fraction(0.0)
        self._status.set_visible(True)
        threading.Thread(target=self._do_clean, daemon=True).start()

    def _do_clean(self):
        pdf     = self._pdf
        dpi     = int(self._dpi.get_value())
        suffix  = self._suffix.get_text().strip() or "-cleaned"
        base    = os.path.splitext(pdf)[0]
        out_pdf = base + suffix + ".pdf"
        tmp_dir = tempfile.mkdtemp(prefix="clean_pdf_")

        do_ocr      = self._ocr_enable.get_active()
        lang_idx    = self._lang_combo.get_selected()
        ocr_lang    = AVAILABLE_LANGS[lang_idx] if lang_idx < len(AVAILABLE_LANGS) else "eng"
        text_only   = self._mode_combo.get_selected() == 1

        try:
            # ── Étape 1 : PDF → PPM ─────────────────────────────────────────
            GLib.idle_add(self._set_status, T["step_convert"])
            r = subprocess.run(
                [PDFTOPPM_BIN, "-r", str(dpi), pdf,
                 os.path.join(tmp_dir, "page")],
                capture_output=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.decode())

            pages = sorted([f for f in os.listdir(tmp_dir)
                            if f.endswith(".ppm")])
            total = len(pages)
            if total == 0:
                raise RuntimeError("No pages found in PDF")

            pdf_pages = []  # PDFs par page à assembler

            for i, page in enumerate(pages, 1):
                src = os.path.join(tmp_dir, page)

                # ── Étape 2 : ImageMagick — deskew + nettoyage fond ─────────
                GLib.idle_add(self._set_progress, i / total / 2,
                              T["step_clean"].format(page=i, total=total))

                cleaned = src
                if (self._whiten.get_active() or self._erode.get_active()
                        or self._deskew.get_active()):
                    dst_im = os.path.join(tmp_dir, f"clean_{i}.ppm")
                    cmd_im = [CONVERT_BIN, src]
                    if self._deskew.get_active():
                        cmd_im += ["-deskew", "40%"]
                    if self._erode.get_active():
                        cmd_im += ["-morphology", "Erode",  "Disk:1",
                                   "-morphology", "Dilate", "Disk:1"]
                    if self._whiten.get_active():
                        wt = int(self._white_threshold.get_value())
                        cmd_im += ["-white-threshold", f"{wt}%"]
                    cmd_im.append(dst_im)
                    r = subprocess.run(cmd_im, capture_output=True)
                    if r.returncode == 0 and os.path.exists(dst_im):
                        cleaned = dst_im

                # ── Étape 3 : Tesseract OCR ──────────────────────────────────
                if do_ocr:
                    GLib.idle_add(self._set_progress,
                                  0.5 + i / total / 2,
                                  T["step_ocr"].format(page=i, total=total))

                    page_pdf = os.path.join(tmp_dir, f"ocr_{i}")

                    if text_only:
                        # PDF texte seul
                        cmd_tess = [TESSERACT_BIN, cleaned, page_pdf,
                                    "-l", ocr_lang, "pdf"]
                        subprocess.run(cmd_tess, capture_output=True)
                        pdf_pages.append(page_pdf + ".pdf")
                    else:
                        # PDF avec image + texte invisible
                        # Tesseract génère un PDF/A avec image+texte
                        cmd_tess = [TESSERACT_BIN, cleaned, page_pdf,
                                    "-l", ocr_lang,
                                    "--dpi", str(dpi),
                                    "pdf"]
                        subprocess.run(cmd_tess, capture_output=True)
                        pdf_pages.append(page_pdf + ".pdf")
                else:
                    pdf_pages.append(cleaned)

            # ── Étape 4 : Assemblage PDF final ───────────────────────────────
            GLib.idle_add(self._set_status, T["step_assemble"])

            if do_ocr:
                # Fusionner les PDFs tesseract avec pdfunite ou gs
                pdfunite = shutil.which("pdfunite")
                if pdfunite and len(pdf_pages) > 1:
                    r = subprocess.run(
                        [pdfunite] + pdf_pages + [out_pdf],
                        capture_output=True)
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr.decode())
                elif len(pdf_pages) == 1:
                    shutil.copy2(pdf_pages[0], out_pdf)
                else:
                    # Fallback img2pdf si pdfunite absent
                    r = subprocess.run(
                        [IMG2PDF_BIN, "--output", out_pdf] + pdf_pages,
                        capture_output=True)
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr.decode())
            else:
                # Pas d'OCR — assembler les images nettoyées
                r = subprocess.run(
                    [IMG2PDF_BIN, "--output", out_pdf] + pdf_pages,
                    capture_output=True)
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.decode())

            GLib.idle_add(self._on_done, out_pdf, None)

        except Exception as e:
            GLib.idle_add(self._on_done, None, str(e))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _set_progress(self, fraction, status):
        self._prog.set_fraction(fraction)
        self._status.set_text(status)
        return False

    def _set_status(self, text):
        self._status.set_text(text)
        return False

    def _on_done(self, out_path, error):
        self._prog.set_visible(False)
        self._status.set_visible(False)
        self._clean_btn.set_sensitive(True)
        if error:
            dlg = Adw.MessageDialog(transient_for=self,
                heading=T["err_title"], body=error)
            dlg.add_response("ok", T["ok"])
            dlg.present()
        else:
            try:
                Gio.AppInfo.launch_default_for_uri(
                    Gio.File.new_for_path(
                        os.path.dirname(out_path)).get_uri(), None)
            except Exception:
                pass
            self.close()
        return False

# ---------------------------------------------------------------------------
# Extension Nautilus
# ---------------------------------------------------------------------------

class CleanPDFExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "CleanPDFExtension"

    def get_file_items(self, files):
        pdfs = [f for f in files
                if f.get_uri_scheme() == "file"
                and not f.is_directory()
                and f.get_name().lower().endswith(".pdf")]
        if len(pdfs) != 1:
            return []
        path = pdfs[0].get_location().get_path()
        item = Nautilus.MenuItem(
            name  = "CleanPDF::Clean",
            label = T["menu_label"],
            tip   = "Clean and OCR scanned PDF",
            icon  = "document-edit-symbolic",
        )
        item.connect("activate", lambda *_: CleanPDFWindow(path).present())
        return [item]

    def get_background_items(self, folder):
        return []
