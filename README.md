# SuperTuxKart — Contrôleur Multi-Interface (Smartphone, Visage, Voix & Arduino)

Système complet et modulaire pour piloter **SuperTuxKart** combinant l'orientation d'un smartphone (volant analogique), des expressions faciales et mouvements de tête (webcam), la reconnaissance vocale (microphone) et un capteur physique (Arduino Wi-Fi).

Le système repose sur une architecture découplée : un **serveur d'entrée UDP** crée une manette virtuelle Xbox 360 (via `evdev`/`uinput`) pour offrir une **direction analogique continue et fluide**, tout en émulant les touches du clavier (via `pynput`) pour l'ensemble des autres actions sans conflit.

---

## Sommaire

- [Fonctionnement](#fonctionnement)
- [Architecture du système](#architecture-du-système)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration de SuperTuxKart](#configuration-de-supertuxkart)
- [Lancement](#lancement)
- [Structure du dépôt](#structure-du-dépôt)
- [Réglages et calibration](#réglages-et-calibration)
- [Dépannage](#dépannage)

---

## Fonctionnement

| Interface | Geste / Action | Type | Action en jeu | Canal / Touche |
|---|---|---|---|---|
| **Smartphone** | Inclinaison latérale (*pitch* en mode paysage) | Continu | **Direction (Volante)** | Espace analogique `ABS_X` (Xbox 360) |
| **Smartphone** | Toucher la moitié droite de l'écran | Continu | **Accélérer** | Touche `Haut` (↑) |
| **Smartphone** | Toucher la moitié gauche de l'écran | Continu | **Freiner / Marche arrière** | Touche `Bas` (↓) |
| **Smartphone** | Toucher avec 2 doigts (ou touche Entrée PC) | Impulsion | **Recalibrer le centre** | Centrage immédiat du volant |
| **Webcam** | Sourcils levés | Continu | **Regarder en arrière** | Touche `B` |
| **Webcam** | Incliner la tête de côté (*roulis* / oreille vers l'épaule) | Continu | **Dérapage (Drift)** | Touche `V` |
| **Webcam** | Hochement de tête rapide vers le bas (*pitch*) | Impulsion | **Sauvetage (Rescue)** | Touche `Retour arrière` |
| **Microphone** | Crier « **turbo** » | Impulsion | **Nitro** | Touche `N` |
| **Microphone** | Crier « **fire** » | Impulsion | **Tirer (Item)** | Touche `Espace` |
| **Arduino** *(opt.)* | Toucher le capteur tactile Grove | Continu | **Dérapage (Drift)** | Touche `V` |

> [!NOTE]
> **Sécurité anti-conflit tête** : Pendant que la tête est inclinée sur le côté pour maintenir un dérapage (*drift*), la détection du sauvetage (*rescue*) est automatiquement verrouillée pour éviter tout déclenchement intempestif.

---

## Architecture du système

```
  📱 Smartphone (MultiSense OSC :8000)   ──┐
                                           │
  📷 Webcam (MediaPipe Face Mesh)        ──┼──> [run_all.py] (Client UDP)
                                           │          │
  🎤 Microphone (Vosk Speech Recog)      ──┘          │  Paquets UDP
                                                      │  (port 6006)
  🕹️ Arduino UNO R4 / ESP32 (drift.ino) ─────────────┼──────────────┐
                                                      ▼              ▼
                                          [STK_input_server_v2.py] (Hub UDP)
                                             ├── Manette Xbox 360 (evdev/uinput) -> Axe ABS_X
                                             └── Clavier virtuel (pynput)        -> Touches STK
                                                      │
                                                      ▼
                                                [SuperTuxKart]
```

---

## Prérequis

- **Système d'exploitation** : Linux (requis pour le support de `/dev/uinput` et `evdev`)
- **Python** : 3.9 ou supérieur
- **Matériel** :
  - Une webcam fonctionnelle (détection faciale et de tête)
  - Un microphone fonctionnel (détection vocale)
  - Un smartphone avec l'application **MultiSense** (envoi OSC via Wi-Fi)
  - *(Optionnel)* Une carte Arduino UNO R4 WiFi ou ESP32 avec capteur tactile
- **Jeu** : SuperTuxKart installé
- **Espace disque** : ~75 Mo pour les modèles de machine learning

---

## Installation

### 1. Permissions Linux (`uinput`)

Pour permettre au serveur de créer la manette Xbox 360 virtuelle sans accès root à chaque exécution :

```bash
sudo chmod 666 /dev/uinput
```

*(Pour rendre ce réglage permanent, ajoutez la règle udev : `echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules && sudo udevadm trigger`)*

### 2. Dépendances Python

Créez un environnement virtuel et installez les bibliothèques requises :

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Modèles de Machine Learning

Téléchargez les deux modèles requis et placez-les dans le dossier `models/` :

| Modèle | Rôle | Taille | Lien de téléchargement | Emplacement cible |
|---|---|---|---|---|
| `face_landmarker.task` | Détection visage & tête (MediaPipe) | ~4 Mo | [Télécharger](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task) | `models/face_landmarker.task` |
| `vosk-model-small-en-us-0.15` | Reconnaissance vocale (Vosk) | ~70 Mo | [Télécharger](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip) | `models/vosk-model-small-en-us-0.15/` *(dézippé)* |

L'arborescence doit être la suivante :
```
models/
├── .gitkeep
├── face_landmarker.task
└── vosk-model-small-en-us-0.15/
    ├── am/
    ├── conf/
    └── ...
```

---

## Configuration de SuperTuxKart

1. Lancez le serveur d'entrée dans un terminal :
   ```bash
   python3 STK_input_server_v2.py -d
   ```
2. Ouvrez **SuperTuxKart** et rendez-vous dans **Options** > **Contrôles**.
3. Le jeu détectera automatiquement le **"Xbox 360 Controller"**.
4. Configurez les commandes :
   - **Tourner à gauche / Tourner à droite** : Assignez à l'axe analogique du contrôleur Xbox 360.
   - **Accélérer, Freiner, Tirer, Nitro, Regarder en arrière, Sauvetage, Dérapage** : Laissez-les assignés aux **touches du clavier** (`Haut`, `Bas`, `Espace`, `N`, `B`, `Retour arrière`, `V`).

---

## Lancement

### Étape 1 : Configuration du smartphone
Dans l'application **MultiSense** sur votre smartphone :
- Cible IP : L'adresse IP locale de votre ordinateur.
- Port cible : `8000`.
- Activez la transmission **Orientation** et le widget **Pad**.

### Étape 2 : Démarrage des modules

Ouvrez deux terminaux (avec l'environnement virtuel activé) :

* **Terminal 1 — Hub Serveur d'Entrée :**
  ```bash
  python3 STK_input_server_v2.py -d
  ```

* **Terminal 2 — Contrôleur Unifié :**
  ```bash
  python3 run_all.py
  ```

Pour quitter à tout moment proprement et sans laisser de touches enfoncées, appuyez sur `Ctrl+C` dans le terminal ou sur la touche `q` sur la fenêtre vidéo de debug.

---

## Structure du dépôt

```
.
├── STK_input_server_v2.py  # Hub serveur UDP (crée le gamepad Xbox 360 + clavier pynput)
├── run_all.py              # Script principal lançant Steer, Face et Voice ensemble
├── steer_module.py         # Récepteur OSC smartphone (volant analogique + pad accélérateur/frein)
├── face_module.py          # Vision par webcam (sourcils -> regard arrière, inclinaison -> drift, aceno -> rescue)
├── voice_module.py         # Reconnaissance vocale continue ("turbo" et "fire")
├── config.py               # Configuration centrale (touches, seuils d'angles, adresses)
├── drift.ino               # Firmware Arduino / ESP (dérapage via capteur tactile en Wi-Fi)
├── steer.py                # Script autonome de test pour le smartphone
├── requirements.txt        # Liste des dépendances Python
├── models/                 # Dossier des modèles d'IA (non versionné sur Git)
│   └── .gitkeep
└── README.md
```

---

## Réglages et calibration

Tous les réglages de sensibilité se trouvent dans [`config.py`](config.py) :

- **Direction** :
  - `DEAD_ZONE` : Zone morte en degrés au centre (stabilité en ligne droite).
  - `MAX_STEER_ANGLE` : Angle d'inclinaison pour atteindre 100 % de braquage (par défaut 30°).
  - `EXPO_GAMMA` : Courbe exponentielle (1.4 : centre précis et doux, virages fermes aux extrémités).
- **Visage & Tête** :
  - `EYEBROW_ENGAGE` / `EYEBROW_RELEASE` : Seuils d'activation/relâchement du regard arrière par les sourcils.
  - `DRIFT_ROLL_ENGAGE` / `DRIFT_ROLL_RELEASE` : Degrés d'inclinaison latérale pour activer/désactiver le dérapage.
  - `NOD_PITCH_DIP_DEG` : Amplitude en degrés vers le bas pour valider un sauvetage.
- **Fenêtre de débogage** :
  - `DEBUG_WINDOW = True` affiche en direct sur le flux vidéo les angles d'inclinaison et les statuts des commandes en temps réel.

---

## Dépannage

- **Erreur `/dev/uinput` permission denied** : Exécutez `sudo chmod 666 /dev/uinput` pour autoriser la création de la manette virtuelle.
- **La direction ne répond pas dans le jeu** : Vérifiez que `STK_input_server_v2.py` est bien lancé avant SuperTuxKart et que l'axe analogique est correctement assigné dans le menu Contrôles.
- **La voix ne réagit pas** : Vérifiez que le microphone est bien configuré par défaut dans le système d'exploitation et que le dossier Vosk dans `models/` est bien extrait.
- **Le dérapage ne s'arrête pas** : Veillez à ramener la tête bien droite (< 10° d'inclinaison) pour envoyer la commande de relâchement et déclencher le mini-turbo.
