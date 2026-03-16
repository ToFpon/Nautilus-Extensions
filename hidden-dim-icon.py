import gi
gi.require_version('Nautilus', '4.0')
gi.require_version('Gtk', '4.0')
from gi.repository import Nautilus, GObject, Gtk, GLib

def find_label_text(widget):
    if isinstance(widget, Gtk.Label):
        return widget.get_text()
    child = widget.get_first_child()
    while child:
        result = find_label_text(child)
        if result:
            return result
        child = child.get_next_sibling()
    return None

def find_picture(widget):
    if isinstance(widget, Gtk.Picture):
        return widget
    child = widget.get_first_child()
    while child:
        result = find_picture(child)
        if result:
            return result
        child = child.get_next_sibling()
    return None

def walk_and_dim(widget):
    name = type(widget).__name__

    if name in ('NautilusNameCell', 'NautilusGridCell'):
        label_text = find_label_text(widget)
        if label_text and label_text.startswith('.') and len(label_text) > 1:
            picture = find_picture(widget)
            if picture:
                picture.set_opacity(0.35)
        return

    child = widget.get_first_child()
    while child:
        walk_and_dim(child)
        child = child.get_next_sibling()

class HiddenFileDimmer(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        GLib.timeout_add(500, self._tick)

    def _tick(self):
        for window in Gtk.Window.list_toplevels():
            if 'Nautilus' in type(window).__name__:
                walk_and_dim(window)
        return True

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        return []
