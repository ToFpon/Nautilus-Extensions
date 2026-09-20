import gi
gi.require_version('Nautilus', '4.0')
gi.require_version('Gtk', '4.0')
from gi.repository import Nautilus, GObject, Gtk, GLib

# Types de cellule confirmés (via dim-incomplete-downloads.py, même
# technique de marche d'arbre) : NautilusGridCell (vue grille) et
# NautilusNameCell (vue liste) englobent TOUJOURS icône + label ensemble --
# les assombrir directement couvre les deux d'un coup, pas besoin de
# chercher le label séparément.
CELL_TYPES = ['NautilusGridCell', 'NautilusNameCell']
# Repli pour d'anciennes versions de Nautilus dont les noms de classes
# internes différaient (l'ancienne liste de cut-dim.py -- gardée au cas où
# certains utilisateurs seraient encore sur une version plus ancienne).
LEGACY_CELL_TYPES = ['ViewCell', 'FlowBoxChild', 'GridCell', 'Thumbnail', 'CanvasItem']
CUT_OPACITY = 0.3
MAX_ANCESTOR_CLIMB = 12


def _find_cut_cell(widget):
    """Remonte depuis le Gtk.Picture jusqu'à la cellule complète (icône +
    label). Priorité aux types confirmés ; repli sur les anciens noms si
    non trouvés en route (Nautilus plus ancien)."""
    node = widget
    legacy_fallback = None
    for _ in range(MAX_ANCESTOR_CLIMB):
        if node is None:
            break
        name = type(node).__name__
        if any(t in name for t in CELL_TYPES):
            return node
        if legacy_fallback is None and any(t in name for t in LEGACY_CELL_TYPES):
            legacy_fallback = node
        node = node.get_parent()
    return legacy_fallback


def walk_and_dim_cut(widget):
    if isinstance(widget, Gtk.Picture):
        ctx = widget.get_style_context()
        is_cut = ctx.has_class('cut')
        cell = _find_cut_cell(widget)
        if cell is not None:
            cell.set_opacity(CUT_OPACITY if is_cut else 1.0)

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
