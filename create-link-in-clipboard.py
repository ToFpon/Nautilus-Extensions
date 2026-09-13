#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# NAME: Create Link in Clipboard — Nautilus Python Extension
# AUTHOR: aaronhall
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
# NAME: Create Link in Clipboard
# DESC: Create absolute symlinks for the selection and put them on the
#   clipboard as a COPY operation, so pasting copies the links (repeatable)
# REQUIRES: python3-nautilus
# INSTALL:
#   cp create-link-in-clipboard.py ~/.local/share/nautilus-python/extensions/
#   nautilus -q
#
# For each selected file/dir, create an absolute symlink inside a fresh
# staging dir (/tmp/nautilus-links-XXXXXX), then place those symlinks on
# the clipboard as a COPY operation. Pasting (Ctrl+V) copies the link
# file to the destination, and paste can be repeated.
#
# Staging dirs are pruned on each run when older than 7 days (symlinks
# only; non-symlink contents are left alone and block dir removal).

import os
import tempfile
import time

import gi
# Prefer Nautilus 4.0, but accept what the host already loaded: newer
# Nautilus (4.1 on GNOME 48+) preloads its namespace before extensions
# import, and re-pinning it then raises ValueError and kills the load.
try:
    gi.require_version("Nautilus", "4.0")
except ValueError:
    pass
gi.require_version("Gtk", "4.0")
from gi.repository import Nautilus, GObject, Gdk, GLib, Gio

STAGING_PREFIX = "nautilus-links-"
STAGING_PARENT = tempfile.gettempdir()  # /tmp
MAX_STAGING_AGE_SECS = 7 * 24 * 3600

MIME_COPIED_FILES = "x-special/gnome-copied-files"
MIME_NAUTILUS_CLIPBOARD = "x-special/nautilus-clipboard"
MIME_URI_LIST = "text/uri-list"

# Keep-alive refs for clipboard content providers. The clipboard serves data
# lazily at paste time, so the provider must stay alive until then.
_LIVE_CLIPBOARD_CONTENT = []


def _notify(summary, body=""):
    try:
        argv = (
            ["notify-send", "--app-name=Nautilus", summary, body]
            if body
            else ["notify-send", "--app-name=Nautilus", summary]
        )
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
    except Exception:
        pass


def _prune_old_staging_dirs():
    now = time.time()
    try:
        names = os.listdir(STAGING_PARENT)
    except OSError:
        return
    for name in names:
        if not name.startswith(STAGING_PREFIX):
            continue
        path = os.path.join(STAGING_PARENT, name)
        try:
            if not os.path.isdir(path) or os.path.islink(path):
                continue
            if now - os.path.getmtime(path) < MAX_STAGING_AGE_SECS:
                continue
            for entry in os.listdir(path):
                entry_path = os.path.join(path, entry)
                if os.path.islink(entry_path):
                    os.unlink(entry_path)
            if not os.listdir(path):
                os.rmdir(path)
        except OSError:
            continue


def _unique_link_path(staging_dir, base):
    candidate = os.path.join(staging_dir, "Link to {}".format(base))
    if not os.path.lexists(candidate):
        return candidate
    n = 2
    while True:
        candidate = os.path.join(staging_dir, "Link to {} ({})".format(base, n))
        if not os.path.lexists(candidate):
            return candidate
        n += 1


def _copy_uris_to_clipboard(uris):
    display = Gdk.Display.get_default()
    if display is None:
        return False
    clipboard = display.get_clipboard()
    # NOTE: no trailing newline — Nautilus rejects empty lines in this format
    # (nautilus_clipboard_from_string: "must not have empty lines").
    copied_payload = ("copy\n" + "\n".join(uris)).encode("utf-8")
    uri_list_payload = ("\r\n".join(uris) + "\r\n").encode("utf-8")
    providers = [
        Gdk.ContentProvider.new_for_bytes(
            MIME_COPIED_FILES, GLib.Bytes.new(copied_payload)
        ),
        Gdk.ContentProvider.new_for_bytes(
            MIME_NAUTILUS_CLIPBOARD, GLib.Bytes.new(copied_payload)
        ),
        Gdk.ContentProvider.new_for_bytes(
            MIME_URI_LIST, GLib.Bytes.new(uri_list_payload)
        ),
    ]
    union = Gdk.ContentProvider.new_union(providers)
    _LIVE_CLIPBOARD_CONTENT.append(union)
    del _LIVE_CLIPBOARD_CONTENT[:-8]
    # Return the real result so callers report failure honestly.
    return bool(clipboard.set_content(union))


def _create_link_in_clipboard_activated(_menu_item, files):
    _prune_old_staging_dirs()
    sources = []
    for f in files:
        loc = f.get_location()
        path = loc.get_path() if loc is not None else None
        if path:
            sources.append(path)
    if not sources:
        _notify("Create Link in Clipboard", "No local files selected.")
        return
    try:
        staging = tempfile.mkdtemp(prefix=STAGING_PREFIX)
    except OSError as e:
        _notify("Create Link in Clipboard failed", str(e))
        return
    links = []
    for src in sources:
        base = os.path.basename(os.path.abspath(src))
        link_path = _unique_link_path(staging, base)
        try:
            os.symlink(os.path.abspath(src), link_path)
            links.append(link_path)
        except OSError as e:
            _notify("Link failed", "{}: {}".format(src, e))
    if not links:
        return
    uris = []
    for link_path in links:
        try:
            uris.append(GLib.filename_to_uri(link_path))
        except Exception:
            continue
    if uris and _copy_uris_to_clipboard(uris):
        _notify(
            "{} link(s) in clipboard".format(len(uris)),
            "Paste to copy the link here.",
        )
    else:
        _notify("Create Link in Clipboard failed", "Could not set clipboard.")


class CreateLinkInClipboardProvider(GObject.GObject, Nautilus.MenuProvider):
    __gtype_name__ = "CreateLinkInClipboardProvider"

    def get_file_items(self, files):
        if not files:
            return []
        item = Nautilus.MenuItem(
            name="CreateLinkInClipboard::Create",
            label="Create Link in Clipboard",
            tip="Create absolute symlinks and copy them to the clipboard",
        )
        item.connect("activate", _create_link_in_clipboard_activated, files)
        return [item]
