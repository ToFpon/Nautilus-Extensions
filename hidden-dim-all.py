import gi
gi.require_version('Nautilus', '4.0')
gi.require_version('Gtk', '4.0')
from gi.repository import Nautilus, GObject, Gtk, GLib

def walk_and_dim(widget):
    if isinstance(widget, Gtk.Label):
        text = widget.get_text()
        if text.startswith('.') and len(text) > 1:
            # Couleur orange sur le label
            widget.set_markup(f'<span foreground="#c0bfbc">{GLib.markup_escape_text(text)}</span>')
            # Opacité sur le parent cell (icône + label)
            parent = widget.get_parent()
            for _ in range(10):
                if parent is None:
                    break
                parent_name = type(parent).__name__
                if any(x in parent_name for x in ['ViewCell', 'FlowBoxChild', 'GridCell', 'Thumbnail', 'CanvasItem']):
                    parent.set_opacity(0.6)
                    break
                parent = parent.get_parent()

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
