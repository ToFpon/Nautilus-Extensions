# Generic Nautilus IDE Extension - Modified for Kate
# Place me in ~/.local/share/nautilus-python/extensions/
# Restart Nautilus with 'nautilus -q' to apply changes.

import os
import shlex
import subprocess
from gi.repository import GObject, Nautilus

IDE_ID = "kate"
IDE_LABEL = "Kate"
IDE_COMMAND = "flatpak run org.kde.kate"

class KateExtension(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        super().__init__()
        # Liste des extensions autorisées
        self.extensions = ('.py', '.sh', '.txt', '.md', '.json', '.yml', '.conf')

    def _build_command(self, files):
        filepaths = []
        for file_ in files:
            filepath = file_.get_location().get_path()
            if filepath:
                filepaths.append(filepath)

        if not filepaths:
            return None

        command = shlex.split(IDE_COMMAND)
        command.extend(filepaths)
        return command

    def launch_ide(self, menu, files):
        command = self._build_command(files)
        if command:
            subprocess.Popen(command)

    def get_file_items(self, *args):
        # Récupération des fichiers (compatible avec différentes versions de l'API)
        files = args[-1]
        
        if not files:
            return []

        # Vérification des conditions : uniquement fichiers, locaux, avec la bonne extension
        for file_ in files:
            # 1. Vérifie que c'est un fichier local
            if file_.get_uri_scheme() != 'file':
                return []
            
            # 2. Vérifie que ce n'est pas un dossier
            if file_.is_directory():
                return []
            
            # 3. Vérifie l'extension
            filename = file_.get_name().lower()
            if not filename.endswith(self.extensions):
                return []

        # Si on arrive ici, toute la sélection est valide
        item = Nautilus.MenuItem(
            name=f"{IDE_ID}Open",
            label=f"Ouvrir avec {IDE_LABEL}",
            tip=f"Ouvre la sélection avec {IDE_LABEL}",
        )
        item.connect("activate", self.launch_ide, files)
        return [item]

    # On ne définit pas get_background_items pour ne pas apparaître sur les dossiers