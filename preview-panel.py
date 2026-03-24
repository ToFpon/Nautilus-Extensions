#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Preview Panel – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), python3-gi, gir1.2-adw-1,
#            ffmpegthumbnailer, poppler-utils (pdftoppm), libreoffice,
#            wmctrl, xdotool
# INSTALL:
#   cp preview-panel.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import re
import stat
import time
import hashlib
import mimetypes
import subprocess
import threading
import tempfile
import locale
import urllib.parse

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gdk, Gio, GLib, Nautilus, Pango

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "title":       "Prévisualisation",
        "menu_label":  "Prévisualiser",
        "no_preview":  "Pas de prévisualisation disponible",
        "file_info":   "Informations",
        "size":        "Taille",
        "modified":    "Modifié",
        "permissions": "Droits",
        "mime":        "Type",
        "dimensions":  "Dimensions",
        "duration":    "Durée",
        "pages":       "Pages",
        "lines":       "Lignes",
        "title_meta":  "Titre",
        "subject":     "Sujet",
        "exif_make":   "Appareil",
        "exif_model":  "Modèle",
        "exif_date":   "Date prise",
        "exif_focal":  "Focale",
        "exif_iso":    "ISO",
        "exif_shutter":"Vitesse",
        "exif_aperture":"Ouverture",
        "loading":     "Chargement…",
    }
else:
    T = {
        "title":       "Preview",
        "menu_label":  "Preview",
        "no_preview":  "No preview available",
        "file_info":   "File info",
        "size":        "Size",
        "modified":    "Modified",
        "permissions": "Permissions",
        "mime":        "Type",
        "dimensions":  "Dimensions",
        "duration":    "Duration",
        "pages":       "Pages",
        "lines":       "Lines",
        "title_meta":  "Title",
        "subject":     "Subject",
        "exif_make":   "Camera make",
        "exif_model":  "Camera model",
        "exif_date":   "Date taken",
        "exif_focal":  "Focal length",
        "exif_iso":    "ISO",
        "exif_shutter":"Shutter speed",
        "exif_aperture":"Aperture",
        "loading":     "Loading…",
    }

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"}
TEXT_EXTS  = {
    ".py", ".js", ".ts", ".sh", ".md", ".txt", ".json", ".xml",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".css", ".html",
    ".htm", ".c", ".cpp", ".h", ".rs", ".go", ".rb", ".php",
    ".java", ".kt", ".swift", ".bash", ".zsh", ".fish", ".sql",
}
OFFICE_EXTS = {
    ".docx", ".doc", ".docm", ".xlsx", ".xls", ".xlsm",
    ".pptx", ".ppt", ".pptm", ".odt", ".ods", ".odp", ".odg", ".rtf",
}

THUMB_DIR   = os.path.expanduser("~/.cache/thumbnails/large")
TRACKER_BIN = "/usr/bin/tracker3"
TRACKER_SVC = "org.freedesktop.Tracker3.Miner.Files"
PDFTOPPM    = "/usr/bin/pdftoppm"
LO_BIN      = "/usr/bin/libreoffice"
XDOTOOL     = "/usr/bin/xdotool"
WMCTRL      = "/usr/bin/wmctrl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    win = app.get_active_window()
    return win or (app.get_windows()[0] if app.get_windows() else None)

def _fmt_size(n):
    for u in ["B","KB","MB","GB","TB"]:
        if n < 1024: return f"{n:.0f} {u}" if u=="B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def _fmt_date(ts):
    return time.strftime("%Y-%m-%d  %H:%M:%S", time.localtime(ts))

def _fmt_perms(mode):
    bits = "d" if stat.S_ISDIR(mode) else "-"
    for r,w,x in [(stat.S_IRUSR,stat.S_IWUSR,stat.S_IXUSR),
                  (stat.S_IRGRP,stat.S_IWGRP,stat.S_IXGRP),
                  (stat.S_IROTH,stat.S_IWOTH,stat.S_IXOTH)]:
        bits += ("r" if mode&r else "-") + ("w" if mode&w else "-") + ("x" if mode&x else "-")
    return bits

def _fmt_duration(s):
    s = int(float(s)); h,r = divmod(s,3600); m,s = divmod(r,60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def _get_mime(path):
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        try:
            info = Gio.File.new_for_path(path).query_info("standard::content-type", 0, None)
            mime = info.get_content_type()
        except Exception:
            pass
    return mime or "application/octet-stream"

def _path_to_uri(path):
    return "file://" + urllib.parse.quote(path)

def _thumb_cached(path):
    """Retourne le chemin du thumbnail GNOME si déjà en cache."""
    h   = hashlib.md5(_path_to_uri(path).encode()).hexdigest()
    dst = os.path.join(THUMB_DIR, h + ".png")
    return dst if os.path.exists(dst) and os.path.getsize(dst) > 0 else None

def _save_to_cache(src_png, path):
    """Copie src_png dans le cache GNOME thumbnails."""
    import shutil
    h   = hashlib.md5(_path_to_uri(path).encode()).hexdigest()
    dst = os.path.join(THUMB_DIR, h + ".png")
    os.makedirs(THUMB_DIR, exist_ok=True)
    shutil.copy2(src_png, dst)
    return dst

# ---------------------------------------------------------------------------
# Pixbuf loader — utilisé pour afficher sans bug de teinte GTK4
# ---------------------------------------------------------------------------

def _load_pixbuf(path, max_w=390, max_h=340):
    """Charge une image en GdkPixbuf redimensionnée à max_w x max_h.
    Agrandit les petits thumbnails pour remplir le panneau."""
    from gi.repository import GdkPixbuf
    try:
        pb    = GdkPixbuf.Pixbuf.new_from_file(path)
        w, h  = pb.get_width(), pb.get_height()
        scale = min(max_w / w, max_h / h)  # pas de limite 1.0 → agrandit si nécessaire
        dst_w = max(int(w * scale), 1)
        dst_h = max(int(h * scale), 1)
        if dst_w != w or dst_h != h:
            pb = pb.scale_simple(dst_w, dst_h, GdkPixbuf.InterpType.BILINEAR)
        return pb
    except Exception as e:
        import sys
        print(f"[preview] pixbuf error: {e}", file=sys.stderr)
        return None

# ---------------------------------------------------------------------------
# Thumbnail generators
# ---------------------------------------------------------------------------

def _thumb_image(path):
    """Images : cache GNOME ou génération via ffmpegthumbnailer."""
    cached = _thumb_cached(path)
    if cached:
        return cached
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".svg":
            from gi.repository import GdkPixbuf
            fd, tmp = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 512, 512, True)
            pb.savev(tmp, "png", [], [])
            dst = _save_to_cache(tmp, path)
            os.remove(tmp)
            return dst
        # Pour les vraies images on retourne directement le path source
        # (on chargera via GdkPixbuf dans _apply_result)
        return path
    except Exception:
        return None

def _thumb_video(path):
    """Vidéos : cache GNOME ou ffmpegthumbnailer."""
    cached = _thumb_cached(path)
    if cached:
        return cached
    try:
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        subprocess.run(
            ["ffmpegthumbnailer", "-i", path, "-o", tmp, "-s", "512", "-q", "5"],
            capture_output=True, timeout=10)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            dst = _save_to_cache(tmp, path)
            os.remove(tmp)
            return dst
    except Exception:
        pass
    return None

def _thumb_pdf(path):
    """PDF : cache GNOME ou pdftoppm (Poppler)."""
    cached = _thumb_cached(path)
    if cached:
        return cached
    if not os.path.isfile(PDFTOPPM):
        return None
    try:
        tmp_dir  = tempfile.mkdtemp()
        out_base = os.path.join(tmp_dir, "page")
        subprocess.run(
            [PDFTOPPM, "-png", "-f", "1", "-l", "1",
             "-scale-to", "1024", path, out_base],
            capture_output=True, timeout=10)
        pngs = sorted([os.path.join(tmp_dir, f)
                       for f in os.listdir(tmp_dir) if f.endswith(".png")])
        if pngs and os.path.getsize(pngs[0]) > 0:
            dst = _save_to_cache(pngs[0], path)
            import shutil; shutil.rmtree(tmp_dir, ignore_errors=True)
            return dst
        import shutil; shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
    return None

def _thumb_office(path):
    """Office/LibreOffice : cache GNOME ou LO headless."""
    cached = _thumb_cached(path)
    if cached:
        return cached
    if not os.path.isfile(LO_BIN):
        return None
    try:
        import shutil
        tmp_dir = tempfile.mkdtemp()
        subprocess.run(
            [LO_BIN, "--headless", "--norestore",
             "--convert-to", "png", "--outdir", tmp_dir, path],
            capture_output=True, timeout=30)
        pngs = [os.path.join(tmp_dir, f)
                for f in os.listdir(tmp_dir) if f.lower().endswith(".png")]
        if pngs and os.path.getsize(pngs[0]) > 0:
            dst = _save_to_cache(pngs[0], path)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return dst
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Tracker3 metadata
# ---------------------------------------------------------------------------

def _tracker_query(file_uri):
    query = f"""
SELECT ?mime ?width ?height ?duration ?pages ?title ?subject
       ?created ?make ?model ?focal ?iso ?shutter ?aperture
WHERE {{
  ?f nie:isStoredAs ?s . ?s nie:url '{file_uri}' .
  OPTIONAL {{ ?f nie:mimeType ?mime }}
  OPTIONAL {{ ?f nfo:width ?width }}
  OPTIONAL {{ ?f nfo:height ?height }}
  OPTIONAL {{ ?f nfo:duration ?duration }}
  OPTIONAL {{ ?f nfo:pageCount ?pages }}
  OPTIONAL {{ ?f nie:title ?title }}
  OPTIONAL {{ ?f nie:subject ?subject }}
  OPTIONAL {{ ?f nie:contentCreated ?created }}
  OPTIONAL {{ ?f nmm:make ?make }}
  OPTIONAL {{ ?f nmm:model ?model }}
  OPTIONAL {{ ?f nmm:focalLength ?focal }}
  OPTIONAL {{ ?f nmm:iso ?iso }}
  OPTIONAL {{ ?f nmm:exposureTime ?shutter }}
  OPTIONAL {{ ?f nmm:fnumber ?aperture }}
}} LIMIT 1"""
    try:
        result = subprocess.run(
            [TRACKER_BIN, "sparql", f"--dbus-service={TRACKER_SVC}", "-q", query],
            capture_output=True, text=True, timeout=2)
        lines = [l.strip() for l in result.stdout.splitlines()
                 if l.strip() and not l.startswith("Results:")]
        if not lines:
            return {}
        parts = [p.strip() for p in lines[0].split(", ")]
        keys  = ["mime","width","height","duration","pages","title_meta",
                 "subject","exif_date","exif_make","exif_model","exif_focal",
                 "exif_iso","exif_shutter","exif_aperture"]
        return {k: v for k, v in zip(keys, parts) if v and v != "(null)"}
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# Info grid
# ---------------------------------------------------------------------------

def _make_info_grid(rows):
    grid = Gtk.Grid()
    grid.set_column_spacing(12)
    grid.set_row_spacing(3)
    grid.set_margin_start(10)
    grid.set_margin_end(10)
    grid.set_margin_top(6)
    grid.set_margin_bottom(6)
    for i, (key, val) in enumerate(rows):
        k = Gtk.Label(label=f"{key} :")
        k.set_halign(Gtk.Align.END)
        k.add_css_class("dim-label")
        v = Gtk.Label(label=str(val))
        v.set_halign(Gtk.Align.START)
        v.set_selectable(True)
        v.set_wrap(True)
        v.set_max_width_chars(32)
        v.set_ellipsize(Pango.EllipsizeMode.END)
        grid.attach(k, 0, i, 1, 1)
        grid.attach(v, 1, i, 1, 1)
    return grid

# ---------------------------------------------------------------------------
# X11 window positioning — dock beside the Nautilus window we care about
# ---------------------------------------------------------------------------

_target_nautilus_wid_dec = None

WMCTRL_GEOMETRY_RE = re.compile(
    r"^(0x[0-9a-f]+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(\d+)\s+(\d+)\s+",
    re.I,
)

PREVIEW_WIDTH_RATIO = float(os.environ.get("NAUTILUS_PREVIEW_WIDTH_RATIO", "0.34"))
PREVIEW_WIDTH_MIN = int(os.environ.get("NAUTILUS_PREVIEW_WIDTH_MIN", "280"))
PREVIEW_WIDTH_MAX = int(os.environ.get("NAUTILUS_PREVIEW_WIDTH_MAX", "640"))
PREVIEW_SYNC_MS = int(os.environ.get("NAUTILUS_PREVIEW_SYNC_MS", "80"))

# Stacking: after each click in Nautilus, Mutter raises the file manager and the
# preview sinks behind. "1" = wmctrl add,above on the preview (stays visible).
PREVIEW_ALWAYS_ABOVE = os.environ.get("NAUTILUS_PREVIEW_ALWAYS_ABOVE", "1").lower() not in (
    "0", "false", "no", "off",
)

def _capture_nautilus_wid():
    global _target_nautilus_wid_dec
    try:
        wid = subprocess.run(
            [XDOTOOL, "getactivewindow"],
            capture_output=True, text=True, timeout=2).stdout.strip()
        if wid.isdigit():
            _target_nautilus_wid_dec = wid
    except Exception:
        pass

def _wmctrl_line_geometry(line):
    m = WMCTRL_GEOMETRY_RE.match(line.strip())
    if not m:
        return None
    wid_s, _desk, x, y, w, h = m.groups()
    # Compare IDs as int — wmctrl uses 0x-padded hex strings that never match Python hex().
    wid_i = int(wid_s, 16)
    return wid_i, int(x), int(y), int(w), int(h)

def _wmctrl_list_geometry():
    try:
        r = subprocess.run(
            [WMCTRL, "-lG"], capture_output=True, text=True, timeout=2)
        out = []
        for line in r.stdout.splitlines():
            g = _wmctrl_line_geometry(line)
            if g:
                out.append(g)
        return out
    except Exception:
        return []

def _geometry_for_wid_int(wid_i):
    if wid_i is None:
        return None
    for row_wid, x, y, w, h in _wmctrl_list_geometry():
        if row_wid == wid_i and w >= 200 and h >= 200:
            return x, y, w, h
    return None

def _xdotool_window_geometry(wid_dec):
    """Absolute position + inner geometry from xdotool (decimal window id)."""
    if not wid_dec or not str(wid_dec).strip().isdigit():
        return None
    try:
        r = subprocess.run(
            [XDOTOOL, "getwindowgeometry", "--shell", str(wid_dec).strip()],
            capture_output=True, text=True, timeout=2)
        d = {}
        for line in r.stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                d[k.strip()] = v.strip()
        if {"X", "Y", "WIDTH", "HEIGHT"}.issubset(d.keys()):
            return (
                int(d["X"]),
                int(d["Y"]),
                int(d["WIDTH"]),
                int(d["HEIGHT"]),
            )
        txt = r.stdout + getattr(r, "stderr", "")
        m = re.search(r"Position:\s*(\d+)\s*,\s*(\d+)", txt)
        gm = re.search(r"Geometry:\s*(\d+)\s*x\s*(\d+)", txt, re.I)
        if m and gm:
            return int(m.group(1)), int(m.group(2)), int(gm.group(1)), int(gm.group(2))
    except Exception:
        pass
    return None

def _geometry_best_nautilus_fallback():
    try:
        id_lines = subprocess.run(
            [XDOTOOL, "search", "--classname", "nautilus"],
            capture_output=True, text=True, timeout=2).stdout.strip().splitlines()
        if not id_lines:
            return None
        candidates = set()
        for w in id_lines:
            w = w.strip()
            if not w.isdigit():
                continue
            candidates.add(int(w))
        if not candidates:
            return None
        best = None
        for wid_i, x, y, bw, bh in _wmctrl_list_geometry():
            if wid_i not in candidates:
                continue
            if bw < 320:
                continue
            area = bw * bh
            if best is None or area > best[0]:
                best = (area, (x, y, bw, bh))
        return best[1] if best else None
    except Exception:
        return None

def _get_target_nautilus_geometry():
    if _target_nautilus_wid_dec and str(_target_nautilus_wid_dec).strip().isdigit():
        tid = int(str(_target_nautilus_wid_dec).strip())
        geo = _xdotool_window_geometry(str(tid))
        if geo:
            return geo
        geo = _geometry_for_wid_int(tid)
        if geo:
            return geo
    return _geometry_best_nautilus_fallback()

def _screen_dimensions():
    try:
        res = subprocess.run(
            ["xdpyinfo"], capture_output=True, text=True, timeout=2)
        m = re.search(r"dimensions:\s+(\d+)x(\d+)", res.stdout)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 1920, 1080

def _compute_panel_rect(nau_x, nau_y, nau_w, nau_h):
    panel_w = int(nau_w * PREVIEW_WIDTH_RATIO)
    panel_w = max(PREVIEW_WIDTH_MIN, min(PREVIEW_WIDTH_MAX, panel_w))
    max_w = max(PREVIEW_WIDTH_MIN, nau_w - 48)
    panel_w = min(panel_w, max_w)
    panel_h = nau_h
    screen_w, screen_h = _screen_dimensions()
    x = nau_x + nau_w - panel_w
    y = nau_y
    if x + panel_w > screen_w - 4:
        x = max(0, nau_x - panel_w + 72)
    x = max(0, min(x, max(0, screen_w - panel_w)))
    y = max(0, min(y, max(0, screen_h - panel_h)))
    return x, y, panel_w, panel_h

def _preview_window_dec_str(win):
    """Decimal X11 id for xdotool (must match getactivewindow)."""
    try:
        if not win.get_realized():
            win.realize()
        surf = win.get_surface()
        if surf is None or not hasattr(surf, "get_xid"):
            return None
        xid = surf.get_xid()
        return str(int(xid)) if xid else None
    except Exception:
        return None

def _xdotool_move_resize(wid_dec, x, y, w, h):
    if not wid_dec:
        return False
    w = max(int(w), 120)
    h = max(int(h), 120)
    try:
        subprocess.run(
            [XDOTOOL, "windowmove", "--sync", wid_dec, str(int(x)), str(int(y))],
            capture_output=True, text=True, timeout=5)
        subprocess.run(
            [XDOTOOL, "windowsize", "--sync", wid_dec, str(w), str(h)],
            capture_output=True, text=True, timeout=5)
        return True
    except Exception:
        return False

def _wmctrl_move_resize_decimal(wid_dec, x, y, w, h):
    if not wid_dec:
        return False
    try:
        subprocess.run(
            [WMCTRL, "-i", "-r", wid_dec, "-e", f"1,{int(x)},{int(y)},{int(w)},{int(h)}"],
            capture_output=True, text=True, timeout=3)
        return True
    except Exception:
        return False

def _wmctrl_stack_above(wid_dec, enable):
    """Toggle _NET_WM_STATE_ABOVE so preview stays on top of Nautilus."""
    if not wid_dec or not str(wid_dec).strip().isdigit():
        return
    flg = "add,above" if enable else "rem,above"
    try:
        subprocess.run(
            [WMCTRL, "-i", "-r", str(wid_dec).strip(), "-b", flg],
            capture_output=True, text=True, timeout=2)
    except Exception:
        pass

def _xdotool_windowraise(panel):
    """Raise preview in the stack (~never steals keyboard vs windowactivate)."""
    wid = _preview_window_dec_str(panel)
    if not wid:
        return
    try:
        subprocess.run(
            [XDOTOOL, "windowraise", wid],
            capture_output=True, text=True, timeout=2)
    except Exception:
        pass

def schedule_preview_raise(panel):
    """After Nautilus handles selection, bump preview above it (often needs a short delay)."""

    def bump(*_b):
        _xdotool_windowraise(panel)
        return False

    GLib.idle_add(bump)
    for ms in (35, 100, 250):
        GLib.timeout_add(ms, bump)

def snap_preview_panel_to_nautilus(panel):
    """Resize/move only the preview window from live Nautilus geometry + ratio."""
    wid = _preview_window_dec_str(panel)
    if not wid:
        return False
    geo = _get_target_nautilus_geometry()
    if not geo:
        return False
    nau_x, nau_y, nau_w, nau_h = geo
    x, y, pw, ph = _compute_panel_rect(nau_x, nau_y, nau_w, nau_h)
    sig = (x, y, pw, ph)
    if getattr(panel, "_last_snap_sig", None) == sig:
        w = getattr(panel, "_above_wid", None) or wid
        if PREVIEW_ALWAYS_ABOVE:
            _wmctrl_stack_above(w, True)
        else:
            _xdotool_windowraise(panel)
        return True
    panel._last_snap_sig = sig
    panel.set_default_size(pw, ph)
    ok = False
    if _xdotool_move_resize(wid, x, y, pw, ph):
        ok = True
    else:
        ok = _wmctrl_move_resize_decimal(wid, x, y, pw, ph)
    if ok:
        panel._above_wid = wid
        if PREVIEW_ALWAYS_ABOVE:
            _wmctrl_stack_above(wid, True)
        else:
            _xdotool_windowraise(panel)
    return ok

# ---------------------------------------------------------------------------
# Preview Panel Window
# ---------------------------------------------------------------------------

class PreviewPanel(Gtk.Window):
    __gtype_name__ = "PreviewPanelWindow"

    def __init__(self):
        super().__init__(title=T["title"])
        self.set_default_size(420, 600)
        self.set_resizable(True)
        self.set_application(Gtk.Application.get_default())

        self._current_path  = None
        self._loading_token = 0
        self._cache         = {}
        self._cache_order   = []
        self._debounce_id   = None
        self._is_open       = True
        self._last_snap_sig = None
        self._snap_timer_id = None
        self._above_wid = None

        # No set_transient_for: Mutter often pins/syncs transient children and ignores xdotool geometry.

        # Header
        header = Gtk.HeaderBar()
        header.set_decoration_layout(":close")
        self._title_lbl = Gtk.Label(label=T["title"])
        self._title_lbl.add_css_class("heading")
        self._title_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._title_lbl.set_max_width_chars(30)
        header.set_title_widget(self._title_lbl)
        self.set_titlebar(header)

        # Content
        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self._content_box)
        self.set_child(scroll)

        self.connect("close-request", self._on_close)
        self.connect("map", self._on_mapped)
        self.connect("unmap", self._on_unmapped)

        # Escape
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        t = Gtk.ShortcutTrigger.parse_string("Escape")
        a = Gtk.CallbackAction.new(lambda *_: self.close() or True)
        ctrl.add_shortcut(Gtk.Shortcut.new(t, a))
        self.add_controller(ctrl)

    def _on_mapped(self, *_):
        self._last_snap_sig = None

        def snap_once(*_):
            snap_preview_panel_to_nautilus(self)
            if PREVIEW_ALWAYS_ABOVE:
                w = _preview_window_dec_str(self)
                if w:
                    self._above_wid = w
                    _wmctrl_stack_above(w, True)
            return False

        GLib.idle_add(snap_once)
        for ms in (30, 80, 160, 400, 900):
            GLib.timeout_add(ms, snap_once)
        self._start_snap_timer()

    def _on_unmapped(self, *_):
        self._stop_snap_timer()

    def _start_snap_timer(self):
        if self._snap_timer_id is not None:
            return

        def tick():
            if not self._is_open or not self.get_mapped():
                self._snap_timer_id = None
                return False
            snap_preview_panel_to_nautilus(self)
            if PREVIEW_ALWAYS_ABOVE and self._above_wid:
                _wmctrl_stack_above(self._above_wid, True)
            return True

        self._snap_timer_id = GLib.timeout_add(PREVIEW_SYNC_MS, tick)

    def _stop_snap_timer(self):
        if self._snap_timer_id is not None:
            GLib.source_remove(self._snap_timer_id)
            self._snap_timer_id = None

    def _on_close(self, *_):
        self._stop_snap_timer()
        w = self._above_wid or _preview_window_dec_str(self)
        if w and PREVIEW_ALWAYS_ABOVE:
            _wmctrl_stack_above(w, False)
        self._above_wid = None
        self._is_open = False
        return False

    # -- Update avec debounce + cache ----------------------------------------

    def update(self, path):
        if path == self._current_path:
            return
        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
            self._debounce_id = None

        if path in self._cache:
            self._current_path = path
            self._loading_token += 1
            self._title_lbl.set_text(os.path.basename(path))
            thumb, text_data, rows = self._cache[path]
            GObject.idle_add(self._apply, self._loading_token, thumb, text_data, rows, path)
            schedule_preview_raise(self)
            if PREVIEW_ALWAYS_ABOVE:
                w = self._above_wid or _preview_window_dec_str(self)
                if w:
                    self._above_wid = w
                    _wmctrl_stack_above(w, True)
            return

        schedule_preview_raise(self)
        if PREVIEW_ALWAYS_ABOVE:
            w = self._above_wid or _preview_window_dec_str(self)
            if w:
                self._above_wid = w
                _wmctrl_stack_above(w, True)

        self._debounce_id = GLib.timeout_add(250, self._load, path)

    def _load(self, path):
        self._debounce_id    = None
        self._current_path   = path
        self._loading_token += 1
        token = self._loading_token
        self._clear()
        self._title_lbl.set_text(os.path.basename(path))
        lbl = Gtk.Label(label=T["loading"])
        lbl.set_margin_top(40)
        lbl.add_css_class("dim-label")
        self._content_box.append(lbl)
        threading.Thread(target=self._build, args=(path, token), daemon=True).start()
        return False

    # -- Build ---------------------------------------------------------------

    def _build(self, path, token):
        import sys
        print(f"[preview] build start: {os.path.basename(path)}", file=sys.stderr)
        mime = _get_mime(path)
        cat  = mime.split("/")[0]
        ext  = os.path.splitext(path)[1].lower()
        print(f"[preview] mime={mime} cat={cat} ext={ext}", file=sys.stderr)

        # Thumbnail
        thumb = None
        if cat == "image" or ext in IMAGE_EXTS:
            thumb = _thumb_image(path)
            print(f"[preview] thumb_image={thumb}", file=sys.stderr)
        elif cat == "video":
            thumb = _thumb_video(path)
        elif mime == "application/pdf" or ext == ".pdf":
            thumb = _thumb_pdf(path)
        elif ext in OFFICE_EXTS:
            thumb = _thumb_office(path)

        # Text preview data
        text_data = None
        if cat == "text" or ext in TEXT_EXTS:
            try:
                with open(path, "r", errors="replace") as f:
                    lines = f.readlines()[:100]
                text_data = "".join(lines)
                if len(lines) == 100:
                    text_data += "\n…"
            except Exception:
                pass

        # Metadata rows
        rows = []
        try:
            s = os.stat(path)
            rows = [
                (T["size"],        _fmt_size(s.st_size)),
                (T["mime"],        mime),
                (T["modified"],    _fmt_date(s.st_mtime)),
                (T["permissions"], _fmt_perms(s.st_mode)),
            ]
        except Exception:
            pass

        tracker = _tracker_query(_path_to_uri(path))
        if "width" in tracker and "height" in tracker:
            rows.append((T["dimensions"], f"{tracker['width']} × {tracker['height']} px"))
        for key, tkey in [
            ("duration","duration"), ("pages","pages"),
            ("title_meta","title_meta"), ("subject","subject"),
            ("exif_make","exif_make"), ("exif_model","exif_model"),
            ("exif_date","exif_date"), ("exif_iso","exif_iso"),
            ("exif_focal","exif_focal"), ("exif_shutter","exif_shutter"),
            ("exif_aperture","exif_aperture"),
        ]:
            if key in tracker:
                val = tracker[key]
                if key == "duration":
                    try: val = _fmt_duration(val)
                    except Exception: pass
                rows.append((T[tkey], val))

        if text_data:
            rows.append((T["lines"], str(text_data.count("\n"))))

        GObject.idle_add(self._apply, token, thumb, text_data, rows, path)

    # -- Apply ---------------------------------------------------------------

    def _apply(self, token, thumb, text_data, rows, path):
        import sys
        print(f"[preview] apply: thumb={thumb} text={bool(text_data)}", file=sys.stderr)
        if token != self._loading_token:
            print("[preview] token obsolète, ignoré", file=sys.stderr)
            return False

        # Cache LRU 15
        if path and path not in self._cache:
            self._cache[path] = (thumb, text_data, rows)
            self._cache_order.append(path)
            if len(self._cache_order) > 15:
                self._cache.pop(self._cache_order.pop(0), None)

        self._clear()
        ext = os.path.splitext(path)[1].lower() if path else ""
        mime = _get_mime(path) if path else ""
        cat  = mime.split("/")[0]
        is_img = cat == "image" or ext in IMAGE_EXTS

        # Preview visuelle via GdkPixbuf (pas de Gtk.Picture → pas de teinte GTK4)
        if thumb and os.path.exists(thumb):
            import sys
            src = path if is_img and path and os.path.exists(path) else thumb
            max_w = 390 if is_img else 400
            max_h = 340 if is_img else 720
            pb  = _load_pixbuf(src, max_w, max_h)
            if pb:
                img = Gtk.Image.new_from_pixbuf(pb)
                img.set_pixel_size(pb.get_width())
                img.set_halign(Gtk.Align.CENTER)
                img.set_valign(Gtk.Align.CENTER)
                img.set_margin_top(12)
                img.set_margin_bottom(8)
                self._content_box.append(img)
            else:
                self._no_preview()
        elif text_data:
            tv = Gtk.TextView()
            tv.set_editable(False)
            tv.set_cursor_visible(False)
            tv.set_monospace(True)
            tv.set_wrap_mode(Gtk.WrapMode.NONE)
            tv.get_buffer().set_text(text_data)
            tv.set_margin_start(8)
            tv.set_margin_end(8)
            tv.set_margin_top(8)
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(False)
            scroll.set_size_request(-1, 280)
            scroll.set_child(tv)
            self._content_box.append(scroll)
        else:
            self._no_preview()

        # Infos
        sep = Gtk.Separator()
        sep.set_margin_top(6)
        self._content_box.append(sep)
        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{T['file_info']}</b>")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_start(10)
        lbl.set_margin_top(6)
        self._content_box.append(lbl)
        if rows:
            self._content_box.append(_make_info_grid(rows))

        schedule_preview_raise(self)
        if PREVIEW_ALWAYS_ABOVE:
            w = self._above_wid or _preview_window_dec_str(self)
            if w:
                self._above_wid = w
                _wmctrl_stack_above(w, True)

        return False

    def _no_preview(self):
        lbl = Gtk.Label(label=T["no_preview"])
        lbl.set_margin_top(30)
        lbl.add_css_class("dim-label")
        self._content_box.append(lbl)

    def _clear(self):
        while True:
            child = self._content_box.get_first_child()
            if child is None:
                break
            self._content_box.remove(child)

# ---------------------------------------------------------------------------
# Nautilus extension
# ---------------------------------------------------------------------------

class PreviewPanelExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "PreviewPanelExtension"

    def __init__(self):
        super().__init__()
        self._panel     = None
        self._hooked    = set()
        self._last_path = None
        GLib.timeout_add(600, self._hook_windows)

    def _hook_windows(self):
        app = Gtk.Application.get_default()
        if app:
            for win in app.get_windows():
                wid = id(win)
                if wid not in self._hooked and isinstance(win, Gtk.ApplicationWindow):
                    self._attach_f4(win)
                    self._hooked.add(wid)
        return True

    def _attach_f4(self, window):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        t = Gtk.ShortcutTrigger.parse_string("F4")
        a = Gtk.CallbackAction.new(lambda *_: self._toggle() or True)
        ctrl.add_shortcut(Gtk.Shortcut.new(t, a))
        window.add_controller(ctrl)

    def _toggle(self):
        if self._panel and self._panel.get_mapped():
            self._panel.close()
        else:
            _capture_nautilus_wid()
            self._ensure(self._last_path)

    def _ensure(self, path=None):
        if self._panel is None or not self._panel._is_open:
            self._panel = PreviewPanel()
        self._panel.present()
        if path:
            self._panel.update(path)

    def get_file_items(self, files):
        single = [f for f in files
                  if f.get_uri_scheme() == "file" and not f.is_directory()]
        if len(single) == 1:
            self._last_path = single[0].get_location().get_path()
            _capture_nautilus_wid()
            if self._panel and self._panel._is_open:
                self._panel.update(self._last_path)
        if not single:
            return []
        item = Nautilus.MenuItem(
            name="PreviewPanel::Preview",
            label=T["menu_label"],
            tip="Open preview panel",
            icon="view-preview-symbolic",
        )
        item.connect("activate", self._on_activate, single[0])
        return [item]

    def get_background_items(self, folder):
        return []

    def _on_activate(self, _item, nfile):
        path = nfile.get_location().get_path()
        self._last_path = path
        _capture_nautilus_wid()
        self._ensure(path)
