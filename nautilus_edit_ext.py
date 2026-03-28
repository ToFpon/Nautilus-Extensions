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

from gi.repository import Nautilus, GObject
import subprocess
import os

class EditFileExtension(GObject.GObject, Nautilus.MenuProvider):
    """Extension Nautilus minimaliste pour éditer plusieurs fichiers à la fois"""
    
    def __init__(self):
        super().__init__()
        # Ton éditeur préféré
        self.editor = "gedit"
        # Les extensions que tu souhaites gérer
        self.extensions = ('.py', '.sh', '.txt', '.md', '.json', '.yml', '.conf')
    
    def get_file_items(self, files):
        """Vérifie la sélection et retourne l'élément de menu"""
        
        if not files:
            return []
        
        # On s'assure que TOUS les fichiers sélectionnés sont éditables
        for file in files:
            # Vérifie que c'est un fichier local
            if file.get_uri_scheme() != 'file':
                return []
            
            # Vérifie que ce n'est pas un dossier et que l'extension matche
            filename = file.get_name().lower()
            if file.is_directory() or not filename.endswith(self.extensions):
                return []
        
        # Créer l'élément de menu (Label fixe comme demandé)
        item = Nautilus.MenuItem(
            name='EditFileExtension::EditFile',
            label=f'Ouvrir avec Gedit',
            tip=f'Ouvrir la sélection dans {self.editor}'
        )
        
        # On connecte en passant la liste complète des fichiers
        item.connect('activate', self.menu_activate_cb, files)
        
        return [item]
    
    def menu_activate_cb(self, menu, files):
        """Lance l'éditeur avec tous les chemins en arguments"""
        
        # Récupération de tous les chemins de fichiers
        filepaths = [f.get_location().get_path() for f in files]
        
        try:
            # subprocess.Popen supporte une liste : [commande, arg1, arg2, ...]
            subprocess.Popen([self.editor] + filepaths)
        except Exception as e:
            print(f"Erreur lors de l'ouverture des fichiers: {e}")
