#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Extract Here – Nautilus Python Extension
# REQUIRES: python3-nautilus (>= 4.0), p7zip-full, python3-gi, gir1.2-adw-1
# INSTALL:
#   cp extract-here.py ~/.local/share/nautilus-python/extensions/
#   rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
#   nautilus -q

import os
import re
import time
import shutil
import subprocess
import threading
import locale
import tempfile

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Gtk, Adw, Gio, GLib, Nautilus

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
_lang = locale.getlocale()[0] or ""

if _lang.startswith("fr"):
    T = {
        "menu_label":     "Extraire ici…",
        "menu_label_vol": "Extraire le volume ici…",
        "title":          "Extraction",
        "extracting":     "Extraction en cours…",
        "done_msg":       "Extrait dans : {dst}",
        "err_7z":         "p7zip est introuvable.\nInstallez-le avec :\nsudo apt install p7zip-full",
        "err_failed":     "L'extraction a échoué (code {code})",
        "err_password":   "Mot de passe incorrect ou archive corrompue.",
        "password_label": "Mot de passe (laisser vide si aucun) :",
        "volumes_found":  "{n} partie(s) détectée(s) — extraction automatique.",
        "cancel":         "Annuler",
        "ok":             "Extraire",
    }
else:
    T = {
        "menu_label":     "Extract here…",
        "menu_label_vol": "Extract volume here…",
        "title":          "Extraction",
        "extracting":     "Extracting…",
        "done_msg":       "Extracted to: {dst}",
        "err_7z":         "p7zip not found.\nInstall it with:\nsudo apt install p7zip-full",
        "err_failed":     "Extraction failed (exit code {code})",
        "err_password":   "Wrong password or corrupted archive.",
        "password_label": "Password (leave empty if none):",
        "volumes_found":  "{n} part(s) found — extracting automatically.",
        "cancel":         "Cancel",
        "ok":             "Extract",
    }

SZ_BIN   = shutil.which("7z") or shutil.which("7za") or "/usr/bin/7z"
UNRAR_BIN = shutil.which("unrar") or "/usr/bin/unrar"

DOUBLE_EXTS = {
    ".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst",
    ".tar.lz4", ".tar.lzma", ".tar.lz",
}

SINGLE_EXTS = {
    ".7z", ".zip", ".rar", ".gz", ".bz2", ".xz", ".zst",
    ".tar", ".tgz", ".tbz2", ".txz", ".lzma", ".lz", ".lz4",
    ".cab", ".iso", ".arj", ".z", ".cpio", ".deb", ".rpm",
    ".dmg", ".wim", ".vhd", ".vhdx",
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

def _get_ext(path):
    name = os.path.basename(path).lower()
    for d in DOUBLE_EXTS:
        if name.endswith(d):
            return d
    _, ext = os.path.splitext(name)
    return ext

def _is_archive(path):
    ext = _get_ext(path)
    return ext in SINGLE_EXTS or ext in DOUBLE_EXTS

def _is_double(path):
    name  = os.path.basename(path).lower()
    stem  = _archive_stem(path).lower()
    return any(name.endswith(d) for d in DOUBLE_EXTS) or stem.endswith(".tar")

def _archive_stem(path):
    name = os.path.basename(path)
    name = re.sub(r'\.(part\d+\.rar|\d{3}|z\d+|r\d+)$', '', name, flags=re.IGNORECASE)
    name_lower = name.lower()
    for d in DOUBLE_EXTS:
        if name_lower.endswith(d):
            return name[:-len(d)]
    root, ext = os.path.splitext(name)
    root2, ext2 = os.path.splitext(root)
    if ext2.lower() in SINGLE_EXTS:
        return root2
    return root

def _detect_volume(path):
    name    = os.path.basename(path)
    dirpath = os.path.dirname(path)
    patterns = [
        (r'^(.+\.7z)\.\d+$',      lambda s, d: _glob(s, d, r'\.7z\.\d+$')),
        (r'^(.+)\.part\d+\.rar$', lambda s, d: _glob(s, d, r'\.part\d+\.rar$')),
        (r'^(.+)\.\d{3}$',        lambda s, d: _glob(s, d, r'\.\d{3}$')),
        (r'^(.+)\.z\d+$',         lambda s, d: _glob(s, d, r'\.(z\d+|zip)$')),
        (r'^(.+)\.(r\d+|rar)$',   lambda s, d: _glob(s, d, r'\.(r\d+|rar)$')),
    ]
    for pattern, finder in patterns:
        m = re.match(pattern, name, re.IGNORECASE)
        if m:
            parts = finder(m.group(1), dirpath)
            if len(parts) > 1:
                parts.sort()
                return parts[0], parts
    return path, [path]

def _glob(stem, dirpath, suffix_re):
    parts = []
    for f in os.listdir(dirpath):
        if re.match(re.escape(stem) + suffix_re, f, re.IGNORECASE):
            parts.append(os.path.join(dirpath, f))
    return parts


# ---------------------------------------------------------------------------
# Détection mot de passe
# ---------------------------------------------------------------------------

def _is_encrypted(path: str) -> bool:
    """Teste si l'archive est protégée par mot de passe via 7z.
    Utilise -p"" pour éviter le blocage sur les archives chiffrées."""
    try:
        result = subprocess.run(
            [SZ_BIN, "l", "-slt", '-p""', path],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout + result.stderr
        # Seul "Encrypted = +" indique un chiffrement réel
        # "Encrypted = -" signifie non chiffré
        if "Encrypted = +" in output:
            return True
        # 7z chiffré — "Cannot open encrypted archive"
        if "Cannot open encrypted archive" in output or            "Wrong password" in output or            "wrong password" in output.lower():
            return True
        # Méthode AES explicite
        if "Method = AES" in output:
            return True
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Password dialog
# ---------------------------------------------------------------------------

class ExtractDialog(Adw.Window):
    __gtype_name__ = "ExtractDialog"

    def __init__(self, first_part, all_parts, callback):
        super().__init__(title=T["title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_default_size(400, -1)
        self._callback = callback
        self._done     = False   # garde contre double appel

        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)

        # Info
        info = Gtk.Label()
        info.set_markup(
            f"<b>{os.path.basename(first_part)}</b>\n"
            + (f"<small>{T['volumes_found'].format(n=len(all_parts))}</small>"
               if len(all_parts) > 1 else "")
        )
        info.set_wrap(True)
        info.set_halign(Gtk.Align.START)
        box.append(info)

        # Mot de passe
        box.append(Gtk.Label(label=T["password_label"]))
        self._pwd = Gtk.PasswordEntry()
        self._pwd.set_show_peek_icon(True)
        box.append(self._pwd)

        # Boutons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(8)

        cancel_btn = Gtk.Button(label=T["cancel"])
        cancel_btn.connect("clicked", self._on_cancel)
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=T["ok"])
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", self._on_ok)
        self._pwd.connect("activate", self._on_ok)
        btn_box.append(ok_btn)

        box.append(btn_box)
        tv.set_content(box)
        self.set_content(tv)

    def _on_ok(self, *_):
        if self._done:
            return
        self._done = True
        pwd = self._pwd.get_text()
        self.destroy()
        self._callback(pwd)

    def _on_cancel(self, *_):
        if self._done:
            return
        self._done = True
        self.destroy()
        self._callback(None)


# ---------------------------------------------------------------------------
# Progress dialog
# ---------------------------------------------------------------------------

class ExtractProgressDialog(Adw.Window):
    __gtype_name__ = "ExtractProgressDialog"

    def __init__(self, first_part, dst_dir, password, done_callback):
        super().__init__(title=T["title"])
        self.set_modal(True)
        self.set_transient_for(_nautilus_window())
        self.set_deletable(False)
        self.set_default_size(380, -1)

        self._first_part = first_part
        self._dst_dir    = dst_dir
        self._password   = password
        self._done_cb    = done_callback
        self._process    = None
        self._cancelled  = False
        self._start_time = time.time()

        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)

        lbl = Gtk.Label()
        lbl.set_markup(
            f"<b>{T['extracting']}</b>\n"
            f"<small>{os.path.basename(first_part)}</small>"
        )
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        # Ligne timer + %
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._timer_lbl = Gtk.Label(label="⏱ 00:00")
        self._timer_lbl.set_halign(Gtk.Align.START)
        self._timer_lbl.set_hexpand(True)
        self._timer_lbl.add_css_class("dim-label")
        self._pct_lbl = Gtk.Label(label="")
        self._pct_lbl.set_halign(Gtk.Align.END)
        self._pct_lbl.add_css_class("dim-label")
        info_box.append(self._timer_lbl)
        info_box.append(self._pct_lbl)
        box.append(info_box)

        self._bar = Gtk.ProgressBar()
        self._bar.set_hexpand(True)
        self._bar.set_pulse_step(0.04)
        box.append(self._bar)

        cancel_btn = Gtk.Button(label=T["cancel"])
        cancel_btn.connect("clicked", self._on_cancel)
        box.append(cancel_btn)

        tv.set_content(box)
        self.set_content(tv)

        self._thread = threading.Thread(target=self._extract, daemon=True)
        self._thread.start()
        GObject.timeout_add(100, self._tick)

    # -- UI ------------------------------------------------------------------

    def _tick(self):
        if not self._thread.is_alive():
            return False
        elapsed = int(time.time() - self._start_time)
        m, s    = divmod(elapsed, 60)
        self._timer_lbl.set_text(f"⏱ {m:02d}:{s:02d}")
        return True

    def _set_progress(self, pct):
        self._bar.set_fraction(pct / 100)
        self._pct_lbl.set_text(f"{pct}%")
        return False  # idle_add one-shot

    def _on_cancel(self, _btn):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.kill()

    # -- Extraction ----------------------------------------------------------

    def _run_7z(self, archive, out_dir, password):
        """Lance 7z et retourne (returncode, error_output).
        Parse la progression depuis stdout via les backspaces."""
        cmd = [SZ_BIN, "x", archive, f"-o{out_dir}", "-y", "-bsp1", "-bso0"]
        if password:
            cmd.append(f"-p{password}")
        # Ne pas ajouter -p sans mot de passe — cause des problèmes avec les RAR

        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        BS = bytes([8])   # backspace — séparateur 7z

        def _parse_stdout():
            buf = b""
            while True:
                ch = self._process.stdout.read(1)
                if not ch:
                    break
                if ch == BS:
                    seg = buf.decode("utf-8", errors="replace").strip()
                    buf = b""
                    if seg:
                        m = re.search(r"(\d{1,3})\s*%", seg)
                        if m:
                            pct = int(m.group(1))
                            if 0 <= pct <= 100:
                                GObject.idle_add(self._set_progress, pct)
                else:
                    buf += ch

        t = threading.Thread(target=_parse_stdout, daemon=True)
        t.start()
        stderr_out = self._process.stderr.read()
        t.join()
        self._process.wait()
        return self._process.returncode, stderr_out.decode("utf-8", errors="replace")

    def _extract(self):
        try:
            if _is_double(self._first_part):
                # Passe 1 : bzip2/gz/xz → .tar
                tmp_dir = tempfile.mkdtemp(
                    dir=os.path.dirname(self._dst_dir), prefix=".7z_tmp_")
                try:
                    ext2 = os.path.splitext(self._first_part)[1].lower()
                    is_rar2 = ext2 in (".rar", ".r00", ".r01", ".r02") or                               re.search(r"\.part\d+\.rar$", self._first_part, re.IGNORECASE)
                    if is_rar2 and os.path.isfile(UNRAR_BIN):
                        rc, err = self._run_unrar(self._first_part, tmp_dir, self._password)
                    else:
                        rc, err = self._run_7z(self._first_part, tmp_dir, self._password)
                    if rc != 0:
                        raise RuntimeError(err)
                    tar_files = [os.path.join(tmp_dir, f)
                                 for f in os.listdir(tmp_dir)
                                 if f.lower().endswith(".tar")]
                    if not tar_files:
                        raise RuntimeError("No .tar found after first pass")
                    # Passe 2 : .tar → fichiers finaux
                    rc, err = self._run_7z(tar_files[0], self._dst_dir, "")
                    if rc != 0:
                        raise RuntimeError(err)
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
            else:
                ext = os.path.splitext(self._first_part)[1].lower()
                is_rar = ext in (".rar", ".r00", ".r01", ".r02") or                          re.search(r"\.part\d+\.rar$", self._first_part, re.IGNORECASE)
                if is_rar and os.path.isfile(UNRAR_BIN):
                    rc, err = self._run_unrar(self._first_part, self._dst_dir, self._password)
                else:
                    rc, err = self._run_7z(self._first_part, self._dst_dir, self._password)
                if rc != 0:
                    raise RuntimeError(err)

        except RuntimeError as exc:
            if not self._cancelled:
                msg = str(exc)
                if "password" in msg.lower() or "Wrong password" in msg:
                    GObject.idle_add(self._on_error, T["err_password"])
                else:
                    GObject.idle_add(self._on_error, T["err_failed"].format(code="?"))
            else:
                GObject.idle_add(self._on_finish, False)
            return
        except Exception as exc:
            GObject.idle_add(self._on_error, str(exc))
            return

        GObject.idle_add(self._on_finish, True)

    def _run_unrar(self, archive, out_dir, password):
        """Extrait un RAR via unrar — supporte RAR5.
        Progression basée sur le nombre de fichiers extraits."""
        # Compter le total de fichiers dans l'archive
        total = 0
        try:
            r = subprocess.run(
                [UNRAR_BIN, "l", archive],
                capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if line.strip().startswith("Extracting") or                    (len(line) > 50 and not line.startswith(" ---")):
                    total += 1
        except Exception:
            pass
        if total == 0:
            total = 100  # fallback

        cmd = [UNRAR_BIN, "x", "-y", archive, out_dir + "/"]
        if password:
            cmd.insert(2, f"-p{password}")
        else:
            cmd.insert(2, "-p-")

        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)

        extracted = 0
        stderr_lines = []

        def _parse_stdout():
            nonlocal extracted
            for line in self._process.stdout:
                line = line.strip()
                if line.startswith("Extracting") and "OK" in line:
                    extracted += 1
                    pct = min(int(extracted / total * 100), 99)
                    GObject.idle_add(self._set_progress, pct)

        t = threading.Thread(target=_parse_stdout, daemon=True)
        t.start()
        stderr_out = self._process.stderr.read()
        t.join()
        self._process.wait()
        GObject.idle_add(self._set_progress, 100)
        return self._process.returncode, stderr_out

    def _on_error(self, msg):
        Gtk.AlertDialog(message=msg).show(_nautilus_window())
        self._on_finish(False)

    def _on_finish(self, success):
        self._bar.set_fraction(1.0)
        self._pct_lbl.set_text("100%")
        elapsed = int(time.time() - self._start_time)
        m, s    = divmod(elapsed, 60)
        self._timer_lbl.set_text(f"⏱ {m:02d}:{s:02d} ✓")
        dst = self._dst_dir if success else ""
        # Fermer proprement puis notifier
        self.set_modal(False)
        self.set_transient_for(None)
        self.destroy()
        self._done_cb(success, dst)


# ---------------------------------------------------------------------------
# Nautilus extension
# ---------------------------------------------------------------------------

class ExtractHereExtension(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "ExtractHereExtension"

    def get_file_items(self, files):
        archives = [
            f for f in files
            if f.get_uri_scheme() == "file"
            and _is_archive(f.get_location().get_path())
        ]
        if not archives:
            return []

        paths     = [f.get_location().get_path() for f in archives]
        is_volume = len(archives) == 1 and len(_detect_volume(paths[0])[1]) > 1
        label     = T["menu_label_vol"] if is_volume else T["menu_label"]

        item = Nautilus.MenuItem(
            name="ExtractHere::Extract",
            label=label,
            tip="Extract archive(s) using 7zip",
            icon="archive-extract",
        )
        item.connect("activate", self._on_activate, archives)
        return [item]

    def get_background_items(self, folder):
        return []

    def _on_activate(self, _item, archives):
        if not os.path.isfile(SZ_BIN) or not os.access(SZ_BIN, os.X_OK):
            Gtk.AlertDialog(message=T["err_7z"]).show(_nautilus_window())
            return
        groups = self._group_volumes(
            [f.get_location().get_path() for f in archives])
        self._process_groups(groups, index=0)

    def _group_volumes(self, paths):
        seen, groups = set(), []
        for path in sorted(paths):
            if path in seen:
                continue
            first, parts = _detect_volume(path)
            for p in parts:
                seen.add(p)
            groups.append((first, parts))
        return groups

    def _process_groups(self, groups, index):
        if index >= len(groups):
            return
        first, parts = groups[index]
        dirpath      = os.path.dirname(first)
        stem         = _archive_stem(first)
        dst_dir      = os.path.join(dirpath, stem)
        if os.path.exists(dst_dir):
            dst_dir += "_extracted"

        def do_extract(password=""):
            prog = ExtractProgressDialog(
                first_part=first,
                dst_dir=dst_dir,
                password=password,
                done_callback=lambda ok, dst: self._on_done(ok, dst, groups, index),
            )
            prog.present()

        # Détecter si l'archive est protégée par mot de passe
        if _is_encrypted(first):
            def on_pwd(password):
                if password is None:
                    return
                do_extract(password)
            ExtractDialog(first, parts, callback=on_pwd).present()
        else:
            # Pas de mot de passe — extraction directe
            do_extract()

    def _on_done(self, success, dst, groups, index):
        # Silence = succès, on continue simplement
        self._process_groups(groups, index + 1)
