import gi
gi.require_version('Nautilus', '4.0')
gi.require_version('Gtk', '4.0')
from gi.repository import Nautilus, GObject, Gtk, GLib

PARENT_TYPES = ['ViewCell', 'FlowBoxChild', 'GridCell', 'Thumbnail', 'CanvasItem']
CUT_OPACITY = 0.3

def walk_and_dim_cut(widget):
    if isinstance(widget, Gtk.Picture):
        ctx = widget.get_style_context()
        is_cut = ctx.has_class('cut')
        parent = widget.get_parent()
        for _ in range(10):
            if parent is None:
                break
            if any(x in type(parent).__name__ for x in PARENT_TYPES):
                parent.set_opacity(CUT_OPACITY if is_cut else 1.0)
                break
            parent = parent.get_parent()

    child = widget.get_first_child()
    while child:
        walk_and_dim_cut(child)
        child = child.get_next_sibling()

class CutItemDimmer(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        GLib.timeout_add(300, self._tick)

    def _tick(self):
        for window in Gtk.Window.list_toplevels():
            if 'Nautilus' in type(window).__name__:
                walk_and_dim_cut(window)
        return True

    def get_file_items(self, files):
        return []

    def get_background_items(self, folder):
        return []
