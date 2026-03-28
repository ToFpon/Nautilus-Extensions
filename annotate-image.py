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
# NAME: Annotate Image – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), python3-gi, gir1.2-adw-1, python3-cairo
# INSTALL:
#   cp annotate-image.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import math
import locale
import cairo

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gdk, Gio, Nautilus

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":   "Annoter l'image…",
        "title":        "Annoter l'image",
        "tool_rect":    "Rectangle",
        "tool_ellipse": "Ellipse",
        "tool_arrow":   "Flèche",
        "tool_text":    "Texte",
        "undo":         "Annuler",
        "redo":         "Rétablir",
        "save":         "Enregistrer",
        "save_as":      "Enregistrer sous…",
        "thickness":    "Épaisseur",
        "opacity":      "Opacité",
        "color":        "Couleur",
        "text_prompt":  "Saisir le texte",
        "text_ok":      "OK",
        "text_cancel":  "Annuler",
        "saved":        "Image enregistrée.",
        "postpend":     "-annoté",
    }
else:
    T = {
        "menu_label":   "Annotate image…",
        "title":        "Annotate image",
        "tool_rect":    "Rectangle",
        "tool_ellipse": "Ellipse",
        "tool_arrow":   "Arrow",
        "tool_text":    "Text",
        "undo":         "Undo",
        "redo":         "Redo",
        "save":         "Save",
        "save_as":      "Save as…",
        "thickness":    "Thickness",
        "opacity":      "Opacity",
        "color":        "Color",
        "text_prompt":  "Enter text",
        "text_ok":      "OK",
        "text_cancel":  "Cancel",
        "saved":        "Image saved.",
        "postpend":     "-annotated",
    }

TOOLS = ["rect", "ellipse", "arrow", "text"]
TOOL_ICONS = {
    "rect":    "draw-rectangle-symbolic",
    "ellipse": "draw-ellipse-symbolic",
    "arrow":   "go-up-symbolic",
    "text":    "format-text-bold-symbolic",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    win = app.get_active_window()
    return win or (app.get_windows()[0] if app.get_windows() else None)


# ---------------------------------------------------------------------------
# Annotation model
# ---------------------------------------------------------------------------

class Annotation:
    def __init__(self, tool, x1, y1, x2, y2, color, opacity, thickness, text=""):
        self.tool      = tool
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2
        self.color     = color      # (r, g, b) floats 0-1
        self.opacity   = opacity    # float 0-1
        self.thickness = thickness  # int pts
        self.text      = text


def _draw_annotation(ctx, ann, scale=1.0):
    """Dessine une annotation sur un contexte Cairo (coords image × scale)."""
    r, g, b = ann.color
    ctx.set_source_rgba(r, g, b, ann.opacity)
    lw = max(ann.thickness * scale, 1.0)
    ctx.set_line_width(lw)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    x1 = ann.x1 * scale
    y1 = ann.y1 * scale
    x2 = ann.x2 * scale
    y2 = ann.y2 * scale

    if ann.tool == "rect":
        ctx.rectangle(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        ctx.stroke()

    elif ann.tool == "ellipse":
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        rw, rh = abs(x2 - x1) / 2, abs(y2 - y1) / 2
        if rw > 0 and rh > 0:
            ctx.save()
            ctx.translate(cx, cy)
            ctx.scale(rw, rh)
            ctx.arc(0, 0, 1, 0, 2 * math.pi)
            ctx.restore()
            ctx.stroke()

    elif ann.tool == "arrow":
        # Corps de la flèche
        ctx.move_to(x1, y1)
        ctx.line_to(x2, y2)
        ctx.stroke()
        # Pointe
        angle     = math.atan2(y2 - y1, x2 - x1)
        arr_len   = max(20 * scale, lw * 4)
        arr_angle = math.pi / 6
        for side in (-1, 1):
            ctx.move_to(x2, y2)
            ctx.line_to(
                x2 - arr_len * math.cos(angle - side * arr_angle),
                y2 - arr_len * math.sin(angle - side * arr_angle),
            )
        ctx.stroke()

    elif ann.tool == "text":
        font_size = max(12.0, ann.thickness * 7.0) * scale
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(font_size)
        ctx.move_to(x1, y1)
        ctx.show_text(ann.text)


# ---------------------------------------------------------------------------
# Editor window
# ---------------------------------------------------------------------------

class AnnotatorWindow(Adw.Window):
    __gtype_name__ = "AnnotateImageWindow"

    def __init__(self, image_path: str):
        super().__init__(title=T["title"])
        self.set_default_size(1100, 750)
        self.set_transient_for(_nautilus_window())

        self._path         = image_path
        self._annotations  = []
        self._redo_stack   = []
        self._tool         = "rect"
        self._color        = (1.0, 0.0, 0.0)
        self._opacity      = 0.85
        self._thickness    = 3
        self._drawing      = False
        self._drag_start_w = (0.0, 0.0)  # widget coords du début du drag
        self._current_ann  = None
        self._scale        = 1.0
        self._offset_x     = 0.0
        self._offset_y     = 0.0

        self._surface = cairo.ImageSurface.create_from_png(image_path)
        self._img_w   = self._surface.get_width()
        self._img_h   = self._surface.get_height()

        self._build_ui()

    # -- Construction UI -----------------------------------------------------

    def _build_ui(self):
        tv = Adw.ToolbarView()

        # HeaderBar
        header = Adw.HeaderBar()

        undo_btn = Gtk.Button(icon_name="edit-undo-symbolic")
        undo_btn.set_tooltip_text(T["undo"])
        undo_btn.connect("clicked", lambda _: self._undo())
        header.pack_start(undo_btn)

        redo_btn = Gtk.Button(icon_name="edit-redo-symbolic")
        redo_btn.set_tooltip_text(T["redo"])
        redo_btn.connect("clicked", lambda _: self._redo())
        header.pack_start(redo_btn)

        save_btn = Gtk.Button(label=T["save"])
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self._save(self._path))
        header.pack_end(save_btn)

        saveas_btn = Gtk.Button(icon_name="document-save-as-symbolic")
        saveas_btn.set_tooltip_text(T["save_as"])
        saveas_btn.connect("clicked", self._save_as)
        header.pack_end(saveas_btn)

        tv.add_top_bar(header)

        # Toolbar outils
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tb.set_margin_top(6)
        tb.set_margin_bottom(6)
        tb.set_margin_start(10)
        tb.set_margin_end(10)

        # Boutons outils (radio)
        self._tool_btns = {}
        group = None
        for tool in TOOLS:
            btn = Gtk.ToggleButton()
            btn.set_icon_name(TOOL_ICONS[tool])
            btn.set_tooltip_text(T[f"tool_{tool}"])
            btn.tool_id = tool
            if group is None:
                group = btn
                btn.set_active(True)
            else:
                btn.set_group(group)
            btn.connect("toggled", self._on_tool_toggled)
            tb.append(btn)
            self._tool_btns[tool] = btn

        tb.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Couleur
        self._color_btn = Gtk.ColorButton()
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue, rgba.alpha = 1.0, 0.0, 0.0, 1.0
        self._color_btn.set_rgba(rgba)
        self._color_btn.set_tooltip_text(T["color"])
        self._color_btn.connect("color-set", self._on_color_set)
        tb.append(self._color_btn)

        tb.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Épaisseur
        tb.append(Gtk.Label(label=f"{T['thickness']} :"))
        self._thick_spin = Gtk.SpinButton.new_with_range(1, 20, 1)
        self._thick_spin.set_value(3)
        self._thick_spin.connect("value-changed",
            lambda s: setattr(self, "_thickness", int(s.get_value())))
        tb.append(self._thick_spin)

        tb.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Opacité
        tb.append(Gtk.Label(label=f"{T['opacity']} :"))
        self._op_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.05)
        self._op_scale.set_value(0.85)
        self._op_scale.set_size_request(120, -1)
        self._op_scale.set_draw_value(False)
        self._op_scale.connect("value-changed",
            lambda s: setattr(self, "_opacity", s.get_value()))
        tb.append(self._op_scale)

        tv.add_top_bar(tb)

        # Canvas
        self._canvas = Gtk.DrawingArea()
        self._canvas.set_vexpand(True)
        self._canvas.set_hexpand(True)
        self._canvas.set_draw_func(self._on_draw)

        # Curseur croix sur le canvas
        crosshair = Gdk.Cursor.new_from_name("crosshair")
        self._canvas.set_cursor(crosshair)

        # Drag gesture
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin",  self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end",    self._drag_end)
        self._canvas.add_controller(drag)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_child(self._canvas)

        tv.set_content(scroll)
        self.set_content(tv)
        self.connect("map", self._on_map)

    # -- Map / scale ---------------------------------------------------------

    def _on_map(self, *_):
        self._recalc_scale()
        self._canvas.set_content_width(int(self._img_w * self._scale + 40))
        self._canvas.set_content_height(int(self._img_h * self._scale + 40))

    def _recalc_scale(self):
        cw = self._canvas.get_width()  or (self.get_width()  - 20)
        ch = self._canvas.get_height() or (self.get_height() - 130)
        if cw > 0 and ch > 0:
            self._scale = min(cw / self._img_w, ch / self._img_h, 2.0)

    # -- Draw ----------------------------------------------------------------

    def _on_draw(self, area, ctx, w, h):
        self._recalc_scale()
        s  = self._scale
        ox = (w - self._img_w * s) / 2
        oy = (h - self._img_h * s) / 2
        self._offset_x = ox
        self._offset_y = oy

        # Fond foncé
        ctx.set_source_rgb(0.13, 0.13, 0.13)
        ctx.paint()

        # Image source
        ctx.save()
        ctx.translate(ox, oy)
        ctx.scale(s, s)
        ctx.set_source_surface(self._surface, 0, 0)
        ctx.paint()
        ctx.restore()

        # Annotations
        ctx.save()
        ctx.translate(ox, oy)
        for ann in self._annotations:
            _draw_annotation(ctx, ann, scale=s)
        if self._current_ann:
            _draw_annotation(ctx, self._current_ann, scale=s)
        ctx.restore()

    # -- Coord conversion ----------------------------------------------------

    def _to_img(self, wx, wy):
        s = self._scale
        return (wx - self._offset_x) / s, (wy - self._offset_y) / s

    # -- Drag events ---------------------------------------------------------

    def _drag_begin(self, gesture, x, y):
        self._drag_start_w = (x, y)
        ix, iy = self._to_img(x, y)

        if self._tool == "text":
            self._ask_text(ix, iy)
            return

        self._drawing = True
        self._current_ann = Annotation(
            self._tool, ix, iy, ix, iy,
            self._color, self._opacity, self._thickness,
        )

    def _drag_update(self, gesture, dx, dy):
        if not self._drawing or not self._current_ann:
            return
        wx = self._drag_start_w[0] + dx
        wy = self._drag_start_w[1] + dy
        ix, iy = self._to_img(wx, wy)
        self._current_ann.x2 = ix
        self._current_ann.y2 = iy
        self._canvas.queue_draw()

    def _drag_end(self, gesture, dx, dy):
        if not self._drawing or not self._current_ann:
            return
        ann = self._current_ann
        if abs(ann.x2 - ann.x1) > 2 or abs(ann.y2 - ann.y1) > 2:
            self._annotations.append(ann)
            self._redo_stack.clear()
        self._current_ann = None
        self._drawing     = False
        self._canvas.queue_draw()

    # -- Text tool -----------------------------------------------------------

    def _ask_text(self, ix, iy):
        dlg = Adw.Window(title=T["text_prompt"])
        dlg.set_modal(True)
        dlg.set_transient_for(self)
        dlg.set_default_size(340, -1)

        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        entry = Gtk.Entry()
        entry.set_placeholder_text(T["text_prompt"])
        box.append(entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=T["text_cancel"])
        cancel_btn.connect("clicked", lambda _: dlg.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=T["text_ok"])
        ok_btn.add_css_class("suggested-action")
        box.append(btn_box)

        def on_ok(_):
            text = entry.get_text().strip()
            if text:
                ann = Annotation(
                    "text", ix, iy, ix, iy,
                    self._color, self._opacity, self._thickness, text,
                )
                self._annotations.append(ann)
                self._redo_stack.clear()
                self._canvas.queue_draw()
            dlg.destroy()

        ok_btn.connect("clicked", on_ok)
        entry.connect("activate", on_ok)
        btn_box.append(ok_btn)

        tv.set_content(box)
        dlg.set_content(tv)
        dlg.present()
        entry.grab_focus()

    # -- Undo / Redo ---------------------------------------------------------

    def _undo(self):
        if self._annotations:
            self._redo_stack.append(self._annotations.pop())
            self._canvas.queue_draw()

    def _redo(self):
        if self._redo_stack:
            self._annotations.append(self._redo_stack.pop())
            self._canvas.queue_draw()

    # -- Tools / settings ----------------------------------------------------

    def _on_tool_toggled(self, btn):
        if btn.get_active():
            self._tool = btn.tool_id

    def _on_color_set(self, btn):
        rgba = btn.get_rgba()
        self._color = (rgba.red, rgba.green, rgba.blue)

    # -- Save ----------------------------------------------------------------

    def _render(self):
        """Rend image + annotations dans une ImageSurface Cairo à résolution native."""
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, self._img_w, self._img_h)
        ctx = cairo.Context(out)
        ctx.set_source_surface(self._surface, 0, 0)
        ctx.paint()
        for ann in self._annotations:
            _draw_annotation(ctx, ann, scale=1.0)
        return out

    def _save(self, path: str):
        self._render().write_to_png(path)
        Gtk.AlertDialog(message=f"✓  {os.path.basename(path)}").show(self)

    def _save_as(self, *_):
        base, _ = os.path.splitext(os.path.basename(self._path))
        dlg = Gtk.FileDialog(title=T["save_as"])
        dlg.set_initial_folder(Gio.File.new_for_path(os.path.dirname(self._path)))
        dlg.set_initial_name(f"{base}{T['postpend']}.png")
        dlg.save(self, None, self._on_save_as_done)

    def _on_save_as_done(self, dlg, result):
        try:
            path = dlg.save_finish(result).get_path()
            self._save(path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Nautilus extension
# ---------------------------------------------------------------------------

class AnnotateImageExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "AnnotateImageExtension"

    def get_file_items(self, files):
        pngs = [
            f for f in files
            if f.get_uri_scheme() == "file"
            and f.get_mime_type() == "image/png"
        ]
        if len(pngs) != 1:
            return []

        item = Nautilus.MenuItem(
            name="AnnotateImage::Annotate",
            label=T["menu_label"],
            tip="Open annotation editor for this image",
        )
        item.connect("activate", self._on_activate, pngs[0])
        return [item]

    def get_background_items(self, folder):
        return []

    def _on_activate(self, _item, nfile):
        AnnotatorWindow(nfile.get_location().get_path()).present()
