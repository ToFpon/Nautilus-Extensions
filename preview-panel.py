#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Preview Panel – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), python3-gi, gir1.2-adw-1,
#            ffmpegthumbnailer, gdk-pixbuf-thumbnailer
# INSTALL:
#   cp preview-panel.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
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
from gi.repository import GObject, Gtk, Adw, Gdk, Gio, GLib, Nautilus

# Backend X11 direct — bypass Mutter placement
try:
    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11
    HAS_GDK_X11 = True
except Exception:
    HAS_GDK_X11 = False

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "title":        "Prévisualisation",
        "menu_label":   "Prévisualiser",
        "no_preview":   "Pas de prévisualisation disponible",
        "file_info":    "Informations",
        "size":         "Taille",
        "modified":     "Modifié",
        "permissions":  "Droits",
        "mime":         "Type",
        "dimensions":   "Dimensions",
        "duration":     "Durée",
        "pages":        "Pages",
        "lines":        "Lignes",
        "title_meta":   "Titre",
        "subject":      "Sujet",
        "exif_make":    "Appareil",
        "exif_model":   "Modèle",
        "exif_date":    "Date prise",
        "exif_focal":   "Focale",
        "exif_iso":     "ISO",
        "exif_shutter": "Vitesse",
        "exif_aperture":"Ouverture",
        "loading":      "Chargement…",
    }
else:
    T = {
        "title":        "Preview",
        "menu_label":   "Preview",
        "no_preview":   "No preview available",
        "file_info":    "File info",
        "size":         "Size",
        "modified":     "Modified",
        "permissions":  "Permissions",
        "mime":         "Type",
        "dimensions":   "Dimensions",
        "duration":     "Duration",
        "pages":        "Pages",
        "lines":        "Lines",
        "title_meta":   "Title",
        "subject":      "Subject",
        "exif_make":    "Camera make",
        "exif_model":   "Camera model",
        "exif_date":    "Date taken",
        "exif_focal":   "Focal length",
        "exif_iso":     "ISO",
        "exif_shutter": "Shutter speed",
        "exif_aperture":"Aperture",
        "loading":      "Loading…",
    }

# ---------------------------------------------------------------------------
# X11 window anchoring
# ---------------------------------------------------------------------------

import shutil as _shutil
XDOTOOL = _shutil.which("xdotool")

# ID X11 de Nautilus mémorisé au moment du clic (quand Nautilus est actif)
_nautilus_wid = None

def _capture_nautilus_wid():
    """Mémorise l'ID X11 de la fenêtre active — appelé pendant get_file_items
    quand on sait que Nautilus est au premier plan."""
    global _nautilus_wid
    try:
        wid = subprocess.run(
            [XDOTOOL, "getactivewindow"],
            capture_output=True, text=True, timeout=2
        ).stdout.strip()
        if wid:
            _nautilus_wid = wid
    except Exception:
        pass

def _get_nautilus_geometry():
    """Récupère la géométrie de Nautilus via wmctrl -lG.
    Filtre les fenêtres trop petites (notre preview) et cherche
    la plus grande fenêtre de classe nautilus."""
    try:
        # Récupérer tous les IDs nautilus
        ids = subprocess.run(
            [XDOTOOL, "search", "--classname", "nautilus"],
            capture_output=True, text=True, timeout=2
        ).stdout.strip().splitlines()
        if not ids:
            return None

        # Récupérer la géométrie de toutes les fenêtres via wmctrl
        result = subprocess.run(
            ["wmctrl", "-lG"],
            capture_output=True, text=True, timeout=2
        )

        best = None
        for wid in ids:
            wid_hex = hex(int(wid))
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        if int(parts[0], 16) == int(wid_hex, 16):
                            w = int(parts[4])
                            h = int(parts[5])
                            # Ignorer notre preview (largeur ~420)
                            # et les petites fenêtres
                            if w > 600:
                                if best is None or w > best["WIDTH"]:
                                    best = {
                                        "X":      int(parts[2]),
                                        "Y":      int(parts[3]),
                                        "WIDTH":  w,
                                        "HEIGHT": h,
                                    }
                    except Exception:
                        continue
        return best
    except Exception:
        return None

def _snap_window_to_nautilus(our_window):
    """Positionne notre fenêtre via wmctrl juste à droite de Nautilus."""
    try:
        geo = _get_nautilus_geometry()
        if not geo:
            return

        nau_x   = geo.get("X", 0)
        nau_y   = geo.get("Y", 0)
        nau_w   = geo.get("WIDTH", 800)
        nau_h   = geo.get("HEIGHT", 600)
        panel_w = 420

        # Résolution écran
        try:
            import re
            res = subprocess.run(
                ["xdpyinfo"], capture_output=True, text=True, timeout=2)
            m = re.search(r"dimensions:\s+(\d+)x(\d+)", res.stdout)
            screen_w = int(m.group(1)) if m else 1920
        except Exception:
            screen_w = 1920

        # Position cible
        deco_w = 100
        if nau_x + nau_w + panel_w + 4 <= screen_w:
            x = nau_x + nau_w - deco_w
        else:
            x = max(0, nau_x - panel_w + deco_w)

        # nau_y=0 signifie Nautilus tout en haut — on laisse y=0
        # Le décalage vers le bas vient des décorations wmctrl
        y = nau_y + 5
        h = nau_h

        import sys
        print(f"[preview] snap → x={x} y={y} h={h}", file=sys.stderr)

        # Trouver l'ID wmctrl de notre fenêtre preview
        # On cherche la fenêtre la plus petite parmi les classes nautilus
        def _get_preview_wid_hex():
            ids = subprocess.run(
                [XDOTOOL, "search", "--classname", "nautilus"],
                capture_output=True, text=True, timeout=2
            ).stdout.strip().splitlines()
            if not ids:
                return None
            result = subprocess.run(
                ["wmctrl", "-lG"], capture_output=True, text=True, timeout=2)
            best_id  = None
            best_w   = 9999
            for wid in ids:
                wid_hex = hex(int(wid))
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            if int(parts[0], 16) == int(wid_hex, 16):
                                w = int(parts[4])
                                if w < best_w:
                                    best_w  = w
                                    best_id = wid_hex
                        except Exception:
                            continue
            return best_id

        def _do_move():
            wid_hex = _get_preview_wid_hex()
            if wid_hex:
                subprocess.run(
                    ["wmctrl", "-ir", wid_hex, "-e",
                     f"1,{x},{y},{panel_w},{h}"],
                    capture_output=True, timeout=2
                )
            return False

        GLib.timeout_add(500, _do_move)

    except Exception as e:
        import sys
        print(f"[preview] snap error: {e}", file=sys.stderr)

TEXT_EXTS = {
    ".py", ".js", ".ts", ".sh", ".md", ".txt", ".json", ".xml",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".css", ".html",
    ".htm", ".c", ".cpp", ".h", ".rs", ".go", ".rb", ".php",
    ".java", ".kt", ".swift", ".bash", ".zsh", ".fish", ".sql",
}

THUMB_DIR_LARGE  = os.path.expanduser("~/.cache/thumbnails/large")
THUMB_DIR_NORMAL = os.path.expanduser("~/.cache/thumbnails/normal")
TRACKER_BIN      = "/usr/bin/tracker3"
TRACKER_SVC      = "org.freedesktop.Tracker3.Miner.Files"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nautilus_window():
    app = Gtk.Application.get_default()
    if app is None:
        return None
    win = app.get_active_window()
    return win or (app.get_windows()[0] if app.get_windows() else None)

def _fmt_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def _fmt_date(ts):
    return time.strftime("%Y-%m-%d  %H:%M:%S", time.localtime(ts))

def _fmt_perms(mode):
    bits = "d" if stat.S_ISDIR(mode) else "-"
    for who in [(stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
                (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
                (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)]:
        bits += "r" if mode & who[0] else "-"
        bits += "w" if mode & who[1] else "-"
        bits += "x" if mode & who[2] else "-"
    return bits

def _get_mime(path):
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        try:
            gfile = Gio.File.new_for_path(path)
            info  = gfile.query_info("standard::content-type", 0, None)
            mime  = info.get_content_type()
        except Exception:
            pass
    return mime or "application/octet-stream"

def _fmt_duration(seconds):
    seconds = int(float(seconds))
    h, rem  = divmod(seconds, 3600)
    m, s    = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def _path_to_uri(path):
    return "file://" + urllib.parse.quote(path)

# ---------------------------------------------------------------------------
# Thumbnail cache (GNOME standard)
# ---------------------------------------------------------------------------

def _thumb_path(path):
    """Retourne le chemin du thumbnail GNOME pour ce fichier."""
    uri  = _path_to_uri(path)
    h    = hashlib.md5(uri.encode()).hexdigest()
    large  = os.path.join(THUMB_DIR_LARGE,  h + ".png")
    normal = os.path.join(THUMB_DIR_NORMAL, h + ".png")
    if os.path.exists(large):
        return large
    if os.path.exists(normal):
        return normal
    return None

def _generate_thumbnail(path, mime):
    """Génère un thumbnail via le thumbnailer système et le met en cache."""
    uri  = _path_to_uri(path)
    h    = hashlib.md5(uri.encode()).hexdigest()
    dst  = os.path.join(THUMB_DIR_LARGE, h + ".png")
    os.makedirs(THUMB_DIR_LARGE, exist_ok=True)

    cat = mime.split("/")[0]
    ext = os.path.splitext(path)[1].lower()

    try:
        if cat == "video":
            # ffmpegthumbnailer — rapide et supporte tous les formats
            subprocess.run(
                ["ffmpegthumbnailer", "-i", path, "-o", dst,
                 "-s", "256", "-q", "5"],
                capture_output=True, timeout=10
            )
        elif mime == "application/pdf":
            # gdk-pixbuf-thumbnailer via evince-thumbnailer si dispo
            import shutil as _sh
            evince = _sh.which("evince-thumbnailer")
            if evince:
                subprocess.run(
                    [evince, uri, dst],
                    capture_output=True, timeout=10
                )
            else:
                # Fallback GhostScript
                gs = _sh.which("gs") or _sh.which("ghostscript")
                if gs:
                    subprocess.run(
                        [gs, "-sDEVICE=pngalpha", "-dNOPAUSE", "-dBATCH",
                         "-dQUIET", "-dFirstPage=1", "-dLastPage=1",
                         "-dDEVICEWIDTH=256", "-dDEVICEHEIGHT=256",
                         "-dFitPage", f"-sOutputFile={dst}", path],
                        capture_output=True, timeout=15
                    )
        else:
            # Images et autres via gdk-pixbuf-thumbnailer
            subprocess.run(
                ["gdk-pixbuf-thumbnailer", "-s", "256", uri, dst],
                capture_output=True, timeout=8
            )
    except Exception:
        pass

    return dst if os.path.exists(dst) and os.path.getsize(dst) > 0 else None

def _build_pdf_direct(path, size=380):
    """Génère un PNG du PDF directement via GS — sans passer par le cache GNOME."""
    import sys
    # Forcer le chemin absolu — shutil.which peut échouer dans le contexte Nautilus
    for gs in ["/usr/bin/gs", "/usr/bin/ghostscript"]:
        if os.path.isfile(gs):
            break
    else:
        print("[preview] GS non trouvé", file=sys.stderr)
        return None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        result = subprocess.run(
            [gs, "-sDEVICE=png16m", "-dNOPAUSE", "-dBATCH", "-dQUIET",
             "-dFirstPage=1", "-dLastPage=1",
             f"-dDEVICEWIDTH={size}", f"-dDEVICEHEIGHT={size}",
             "-dFitPage", "-dBackgroundColor=16#e0e0e0",
             f"-sOutputFile={tmp}", path],
            capture_output=True, timeout=15
        )
        print(f"[preview] GS rc={result.rc if hasattr(result,'rc') else result.returncode} tmp={tmp} size={os.path.getsize(tmp) if os.path.exists(tmp) else 'ABSENT'}", file=sys.stderr)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            return tmp
        try: os.remove(tmp)
        except: pass
    except Exception as e:
        print(f"[preview] GS error: {e}", file=sys.stderr)
    return None


def _get_or_create_thumbnail(path, mime):
    """Retourne le thumbnail (depuis cache ou généré). Rapide si déjà en cache."""
    cached = _thumb_path(path)
    if cached:
        return cached
    return _generate_thumbnail(path, mime)

# ---------------------------------------------------------------------------
# Tracker3
# ---------------------------------------------------------------------------

def _tracker_query(file_uri):
    query = f"""
SELECT ?mime ?width ?height ?duration ?pages ?title ?subject
       ?created ?make ?model ?focal ?iso ?shutter ?aperture
WHERE {{
  ?f nie:isStoredAs ?stored .
  ?stored nie:url '{file_uri}' .
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
}}
LIMIT 1
"""
    try:
        result = subprocess.run(
            [TRACKER_BIN, "sparql",
             f"--dbus-service={TRACKER_SVC}", "-q", query],
            capture_output=True, text=True, timeout=2
        )
        lines = [l.strip() for l in result.stdout.splitlines()
                 if l.strip() and not l.startswith("Results:")]
        if not lines:
            return {}
        parts = [p.strip() for p in lines[0].split(", ")]
        keys  = ["mime", "width", "height", "duration", "pages",
                 "title_meta", "subject", "exif_date", "exif_make",
                 "exif_model", "exif_focal", "exif_iso",
                 "exif_shutter", "exif_aperture"]
        info  = {}
        for k, v in zip(keys, parts):
            if v and v != "(null)":
                info[k] = v
        return info
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# Text preview
# ---------------------------------------------------------------------------

def _build_text_widget(path, max_lines=100):
    try:
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()[:max_lines]
        content = "".join(lines)
        if len(lines) == max_lines:
            content += "\n…"
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_monospace(True)
        tv.set_wrap_mode(Gtk.WrapMode.NONE)
        tv.get_buffer().set_text(content)
        tv.set_margin_start(6)
        tv.set_margin_end(6)
        tv.set_margin_top(6)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_size_request(380, 320)
        scroll.set_child(tv)
        return scroll
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Info grid
# ---------------------------------------------------------------------------

def _make_info_grid(rows):
    grid = Gtk.Grid()
    grid.set_column_spacing(12)
    grid.set_row_spacing(3)
    grid.set_margin_start(8)
    grid.set_margin_end(8)
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
        v.set_max_width_chars(30)
        grid.attach(k, 0, i, 1, 1)
        grid.attach(v, 1, i, 1, 1)
    return grid

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

        header = Gtk.HeaderBar()
        # Garder uniquement le bouton fermer, pas minimize/maximize
        header.set_decoration_layout(":close")
        self._title_lbl = Gtk.Label(label=T["title"])
        self._title_lbl.add_css_class("heading")
        header.set_title_widget(self._title_lbl)
        self.set_titlebar(header)

        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._content_box.set_hexpand(False)
        self.connect("close-request", self._on_close_request)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(False)
        scroll.set_propagate_natural_width(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self._content_box)
        self.set_child(scroll)

        # Ancrer à droite de Nautilus après affichage
        self.connect("map", self._on_map)

        # Escape pour fermer
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        t = Gtk.ShortcutTrigger.parse_string("Escape")
        a = Gtk.CallbackAction.new(lambda *_: self.close() or True)
        ctrl.add_shortcut(Gtk.Shortcut.new(t, a))
        self.add_controller(ctrl)

    def _on_close_request(self, *_):
        self._is_open = False
        return False

    def _on_map(self, *_):
        # Lancer le snap — il gère ses propres délais en interne
        _snap_window_to_nautilus(self)

    # -- Update avec debounce + cache ----------------------------------------

    def update(self, path):
        if path == self._current_path:
            return

        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
            self._debounce_id = None

        # Cache hit → instantané
        if path in self._cache:
            self._current_path = path
            self._loading_token += 1
            self._title_lbl.set_text(os.path.basename(path))
            preview_path, rows = self._cache[path]
            GObject.idle_add(
                self._apply_result, self._loading_token,
                preview_path, None, rows, path)
            return

        # Debounce 250ms
        self._debounce_id = GLib.timeout_add(250, self._start_load, path)

    def _start_load(self, path):
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

        threading.Thread(
            target=self._build_async,
            args=(path, token),
            daemon=True
        ).start()
        return False

    # -- Build en arrière-plan -----------------------------------------------

    def _build_async(self, path, token):
        if not path or not os.path.isfile(path):
            return

        mime = _get_mime(path)
        cat  = mime.split("/")[0]
        ext  = os.path.splitext(path)[1].lower()

        # 1. Thumbnail (cache GNOME ou génération)
        # Pour les PDFs : génération directe via GS sans passer par le cache
        # (le cache GNOME cause des problèmes de transparence sur Nautilus 46)
        thumb_path = None
        if mime == "application/pdf" or ext == ".pdf":
            thumb_path = _build_pdf_direct(path)
        elif cat in ("image", "video") or ext == ".svg":
            thumb_path = _get_or_create_thumbnail(path, mime)

        # 2. Text preview
        text_widget_data = None
        if cat == "text" or ext in TEXT_EXTS:
            try:
                with open(path, "r", errors="replace") as f:
                    text_widget_data = "".join(f.readlines()[:100])
            except Exception:
                pass

        # 3. Métadonnées Tracker3 (instantané)
        tracker = _tracker_query(_path_to_uri(path))

        # 4. Construire les rows d'infos
        try:
            s = os.stat(path)
            rows = [
                (T["size"],        _fmt_size(s.st_size)),
                (T["mime"],        mime),
                (T["modified"],    _fmt_date(s.st_mtime)),
                (T["permissions"], _fmt_perms(s.st_mode)),
            ]
        except Exception:
            rows = []

        # Dimensions
        if "width" in tracker and "height" in tracker:
            rows.append((T["dimensions"],
                         f"{tracker['width']} × {tracker['height']} px"))

        for key, tkey in [
            ("duration",      "duration"),
            ("pages",         "pages"),
            ("title_meta",    "title_meta"),
            ("subject",       "subject"),
            ("exif_make",     "exif_make"),
            ("exif_model",    "exif_model"),
            ("exif_date",     "exif_date"),
            ("exif_iso",      "exif_iso"),
            ("exif_focal",    "exif_focal"),
            ("exif_shutter",  "exif_shutter"),
            ("exif_aperture", "exif_aperture"),
        ]:
            if key in tracker and tracker[key] != "(null)":
                val = tracker[key]
                if key == "duration":
                    try:
                        val = _fmt_duration(val)
                    except Exception:
                        pass
                rows.append((T[tkey], val))

        # Lignes pour les fichiers texte
        if text_widget_data is not None:
            rows.append((T["lines"],
                         str(text_widget_data.count("\n"))))

        # Mettre en cache et appliquer
        cache_val = (thumb_path, text_widget_data, rows)
        GObject.idle_add(
            self._apply_result, token, thumb_path,
            text_widget_data, rows, path, mime, ext)

    def _apply_result(self, token, thumb_path, text_data, rows, path=None, mime="", ext=""):
        if token != self._loading_token:
            return False

        # Cache LRU 15 entrées
        if path and path not in self._cache:
            self._cache[path] = (thumb_path, rows)
            self._cache_order.append(path)
            if len(self._cache_order) > 15:
                oldest = self._cache_order.pop(0)
                self._cache.pop(oldest, None)

        self._clear()

        # Preview visuelle
        if thumb_path and os.path.exists(thumb_path):
            try:
                tex = Gdk.Texture.new_from_filename(thumb_path)
                pic = Gtk.Picture.new_for_paintable(tex)
                pic.set_can_shrink(True)
                pic.set_content_fit(Gtk.ContentFit.CONTAIN)
                pic.set_valign(Gtk.Align.CENTER)
                pic.set_halign(Gtk.Align.CENTER)
                pic.set_vexpand(False)
                pic.set_hexpand(False)
                pic.set_size_request(-1, 260)
                frame = Gtk.Frame()
                frame.set_margin_top(10)
                frame.set_margin_start(10)
                frame.set_margin_end(10)
                frame.set_margin_bottom(6)
                frame.set_hexpand(False)

                # Fond blanc uniquement pour les PDFs
                if mime == "application/pdf" or ext == ".pdf":
                    css = Gtk.CssProvider()
                    css.load_from_data(b".preview-pdf-bg { background-color: #e0e0e0; }")
                    Gtk.StyleContext.add_provider_for_display(
                        Gdk.Display.get_default(), css,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                    box_bg = Gtk.Box()
                    box_bg.add_css_class("preview-pdf-bg")
                    box_bg.append(pic)
                    frame.set_child(box_bg)
                else:
                    frame.set_child(pic)

                self._content_box.append(frame)
            except Exception:
                pass
        elif text_data:
            # Texte
            tv = Gtk.TextView()
            tv.set_editable(False)
            tv.set_cursor_visible(False)
            tv.set_monospace(True)
            tv.set_wrap_mode(Gtk.WrapMode.NONE)
            tv.get_buffer().set_text(text_data)
            tv.set_margin_start(6)
            tv.set_margin_end(6)
            tv.set_margin_top(6)
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(False)
            scroll.set_size_request(380, 280)
            scroll.set_child(tv)
            frame = Gtk.Frame()
            frame.set_margin_top(10)
            frame.set_margin_start(10)
            frame.set_margin_end(10)
            frame.set_child(scroll)
            self._content_box.append(frame)
        else:
            lbl = Gtk.Label(label=T["no_preview"])
            lbl.set_margin_top(30)
            lbl.add_css_class("dim-label")
            self._content_box.append(lbl)

        # Infos
        sep = Gtk.Separator()
        sep.set_margin_top(6)
        self._content_box.append(sep)
        info_lbl = Gtk.Label()
        info_lbl.set_markup(f"<b>{T['file_info']}</b>")
        info_lbl.set_halign(Gtk.Align.START)
        info_lbl.set_margin_start(10)
        info_lbl.set_margin_top(6)
        self._content_box.append(info_lbl)
        if rows:
            self._content_box.append(_make_info_grid(rows))

        return False

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
        if app is None:
            return True
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
        a = Gtk.CallbackAction.new(lambda *_: self._toggle_panel() or True)
        ctrl.add_shortcut(Gtk.Shortcut.new(t, a))
        window.add_controller(ctrl)

    def _toggle_panel(self):
        if self._panel and self._panel.get_mapped():
            self._panel.close()
        else:
            _capture_nautilus_wid()
            self._ensure_panel(self._last_path)

    def _ensure_panel(self, path=None):
        if self._panel is None or not self._panel.get_mapped():
            self._panel = PreviewPanel()
        self._panel.present()
        if path:
            self._panel.update(path)
        elif self._last_path:
            self._panel.update(self._last_path)

    def get_file_items(self, files):
        single = [f for f in files
                  if f.get_uri_scheme() == "file"
                  and not f.is_directory()]

        if len(single) == 1:
            self._last_path = single[0].get_location().get_path()
            _capture_nautilus_wid()  # mémoriser l'ID Nautilus pendant qu'il est actif
            if self._panel and self._panel.get_visible():
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
        self._ensure_panel(path)
