# 🎵 Blind Test

Application multi-joueurs sur réseau local. Itération 1 : lobby + pseudo.

- **Backend** : FastAPI + WebSockets ([backend/](backend/))
- **Frontend** : React + Vite + TypeScript ([frontend/](frontend/))
- **Architecture** : un seul serveur par partie, hébergé par le créateur du salon. Tout est en mémoire.

## Pré-requis

- Python 3.10+
- Node.js 18+
- Les joueurs doivent être sur le même réseau Wi-Fi/LAN que toi

## Démarrer une partie (mode démo)

```bash
./scripts/serve.sh
```

Ce script :
1. installe les dépendances (Python et Node) si besoin (premier lancement uniquement),
2. build le front,
3. lance FastAPI sur `0.0.0.0:8000`.

À l'écran tu verras quelque chose comme :

```
============================================================
🎵  Blind Test server running
   Host link (pour toi)     : http://192.168.1.42:8000/?host=AbCdEfGh
   Player link (à partager) : http://192.168.1.42:8000/
============================================================
```

### Comment rejoindre

1. **Toi (l'hôte)** : ouvre le **Host link** (avec `?host=…`) dans ton navigateur, entre ton pseudo. Tu apparais avec un badge "Hôte".
2. **Tes invités** : sur leur téléphone/PC, ils ouvrent le **Player link** (URL simple, sans `?host=…`) et entrent leur pseudo. Ils apparaissent en temps réel dans ton salon.

Quand tu fermes le serveur (`Ctrl+C`), le salon disparaît.

### Bonnes pratiques réseau

- Pare-feu : autorise le port 8000 en entrée si nécessaire (sous Ubuntu : `sudo ufw allow 8000`).
- Si l'IP affichée ne fonctionne pas pour tes invités, vérifie ton IP locale avec `hostname -I`.
- Le **host token** change à chaque redémarrage du serveur — c'est volontaire (sécurité minimale).

## Mode développement

Pour itérer sur le code avec hot-reload :

```bash
./scripts/dev.sh
```

Cela lance Vite (port 5173, hot reload) et FastAPI (port 8000, `--reload`). Tu ouvres `http://localhost:5173` ; Vite proxy les appels `/api` et `/ws` vers FastAPI.

## Hors-scope (itération 1)

Le bouton **"Démarrer la partie"** est visible pour l'hôte mais désactivé. La logique de jeu (Spotify, chrono 60s, indices, scoring, animations) viendra dans une itération suivante — voir [specs.txt](specs.txt).
