# 🐚 Nautilus Python Extensions

> A collection of productivity-focused Python extensions for **Nautilus (GNOME Files)**, adding powerful tools directly into the right-click context menu.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![GTK](https://img.shields.io/badge/GTK-4.0-4A86CF?style=flat-square&logo=gtk&logoColor=white)
![Libadwaita](https://img.shields.io/badge/Libadwaita-1.x-78ACD8?style=flat-square)
![GNOME](https://img.shields.io/badge/Nautilus-46+-4A86CF?style=flat-square&logo=gnome&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-green?style=flat-square)

---

## 📦 Extensions

| Extension | Fichier | Description |
|---|---|---|
| 🎨 Annotate Image | `annotate-image.py` | Éditeur d'annotations sur images PNG |
| 🗜️ Compress PDF | `compress-pdf.py` | Compression de PDF via Ghostscript |
| ⏱️ Media Duration | `duration-column.py` | Colonne durée pour fichiers audio/vidéo |
| 👁️ Hidden Files Dimmer | `hidden-dim-*.py` | Atténuation visuelle des fichiers cachés |
| 🔗 Merge PDF | `merge-pdf.py` | Fusion de plusieurs PDF en un seul |
| ✏️ Quick Edit | `nautilus_edit_ext.py` | Ouverture rapide dans un éditeur de texte |
| 🔏 Watermark PDF | `watermark-pdf.py` | Filigrane sécurisé avec aplatissement |

---

## ⚙️ Installation

### Prérequis

```bash
sudo apt install \
  python3-nautilus \
  python3-gi \
  gir1.2-gtk-4.0 \
  gir1.2-adw-1 \
  ghostscript \
  ffmpeg \
  python3-pypdf \
  python3-cairo
```

### Installation d'une extension

```bash
# Créer le dossier si nécessaire
mkdir -p ~/.local/share/nautilus-python/extensions/

# Copier l'extension
cp extension-name.py ~/.local/share/nautilus-python/extensions/

# Redémarrer Nautilus
nautilus -q
```

> ⚠️ Toujours supprimer le cache après installation ou mise à jour :
> ```bash
> rm -rf ~/.local/share/nautilus-python/extensions/__pycache__
> ```

---

## 🔍 Description des extensions

### 🎨 Annotate Image — `annotate-image.py`

Ouvre un éditeur d'annotations complet directement depuis le clic droit sur un PNG.

**Outils disponibles :**
- Rectangle, ellipse, flèche avec pointe
- Texte libre positionnable
- Choix de couleur, épaisseur (1→20) et opacité (10%→100%)
- Undo / Redo illimité
- Curseur crosshair professionnel
- Enregistrement natif à la résolution originale

**Dépendances :** `python3-nautilus` `python3-gi` `gir1.2-adw-1` `python3-cairo`

---

### 🗜️ Compress PDF — `compress-pdf.py`

Réduit la taille des fichiers PDF via les niveaux d'optimisation Ghostscript.

**Niveaux disponibles :**
| Niveau | Usage |
|---|---|
| Défaut | Optimisation standard |
| Affichage écran | Résolution réduite pour lecture |
| Basse qualité | Compression maximale |
| Haute qualité | Impression laser |
| Haute qualité (couleurs) | Impression prépresse |

**Dépendances :** `python3-nautilus` `ghostscript` `python3-gi` `gir1.2-gtk-4.0`

---

### ⏱️ Media Duration Column — `duration-column.py`

Ajoute une colonne **Durée** en vue liste pour les fichiers audio et vidéo. Utilise un cache local pour des performances optimales.

**Dépendances :** `python3-nautilus` `ffmpeg` `python3-gi`

---

### 👁️ Hidden Files Dimmer — `hidden-dim-all.py` / `hidden-dim-icon.py`

Distingue visuellement les fichiers cachés (préfixe `.`) en réduisant leur opacité, facilitant la navigation dans le système de fichiers.

- `hidden-dim-all.py` — atténue icônes **et** labels
- `hidden-dim-icon.py` — atténue uniquement les icônes

**Dépendances :** `python3-nautilus` `python3-gi` `gir1.2-gtk-4.0`

---

### 🔗 Merge PDF — `merge-pdf.py`

Fusionne plusieurs fichiers PDF en un seul document. Disponible uniquement quand **2 fichiers PDF ou plus** sont sélectionnés.

**Fonctionnalités :**
- Dialog de réordonnancement avec boutons ↑ ↓
- Nom de sortie suggéré automatiquement (`fusion.pdf`)
- Barre de progression avec annulation

**Dépendances :** `python3-nautilus` `ghostscript` `python3-gi` `gir1.2-adw-1`

---

### ✏️ Quick Edit — `nautilus_edit_ext.py`

Ouvre les fichiers texte (`.py`, `.sh`, `.txt`, `.md`, etc.) directement dans un éditeur depuis le clic droit.

**Dépendances :** `python3-nautilus` `python3-gi` `gedit` *(ou éditeur de votre choix)*

---

### 🔏 Watermark PDF — `watermark-pdf.py`

Ajoute un filigrane textuel personnalisé à des fichiers PDF, conçu pour **protéger les documents sensibles** contre l'usurpation d'identité.

**Options :**
- Texte libre, taille de police, angle (-90°→+90°)
- Opacité réglable, choix de couleur
- Mode **centré** ou **diagonale répétée**
- ✅ **Flatten (aplatissement)** — fusionne le filigrane dans une image raster infalsifiable, avec résolution réglable (72→300 DPI)

> 💡 **Conseil sécurité :** Utilisez le flatten à 200 DPI puis compressez le résultat avec *Compress PDF* pour un document léger et sécurisé.

**Dépendances :** `python3-nautilus` `ghostscript` `python3-pypdf` `python3-gi` `gir1.2-adw-1`

---

## 🌍 Internationalisation

Toutes les extensions détectent automatiquement la langue du système et sont disponibles en **français** et **anglais**.

---

## 🖥️ Compatibilité

| Composant | Version requise |
|---|---|
| Nautilus | 43+ (API 4.0) |
| Python | 3.10+ |
| GTK | 4.0 |
| Libadwaita | 1.x |
| Ubuntu / Debian | 23.04+ |

---

## 📄 Licence

Ce projet est distribué sous licence **GNU GPL v3**.
Basé sur le script original *Compress PDF* de Ricardo Ferreira.
