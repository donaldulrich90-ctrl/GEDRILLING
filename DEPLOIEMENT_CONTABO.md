# Déploiement sur Contabo (GOOD ENGINEERS OS)

L’application utilise **SQLite** comme moteur de base de données : les fichiers `geo_data.db`, le dossier `tenant_data/`, `app_database.json`, sauvegardes et images sont stockés dans un répertoire persistant. Sur un VPS, il suffit de **sauvegarder ce dossier** (ou le volume Docker) pour ne pas perdre les données.

## Option A — VPS Contabo + Docker (recommandé)

1. **Serveur** : VPS Linux (Ubuntu 22.04 LTS par exemple) chez Contabo, avec un pare-feu ouvert sur le port **8501** (ou **80/443** si vous passez par un reverse proxy).

2. **Installer Docker** (sur le VPS) :
   - Suivre la documentation officielle Docker pour Ubuntu, ou les instructions Contabo pour Docker.

3. **Copier le projet** sur le VPS (Git, `scp`, etc.) dans un dossier, par exemple `/opt/good-engineers`.

4. **Lancer** :
   ```bash
   cd /opt/good-engineers
   docker compose up -d --build
   ```
   Les données sont dans le volume nommé `goodengineers_data` (répertoire interne `/data` dans le conteneur).

5. **Accès** : `http://IP_DU_VPS:8501`

6. **HTTPS et nom de domaine** : installer **Nginx** (ou Caddy) sur le VPS, configurer un **certificat Let’s Encrypt**, et faire un *proxy_pass* vers `http://127.0.0.1:8501`. Ne pas exposer le port 8501 publiquement si vous préférez tout passer par 443.

### Variable d’environnement

| Variable | Rôle |
|----------|------|
| `GOOD_ENGINEERS_DATA_DIR` | Répertoire absolu où sont stockés SQLite, JSON, logos, images, sauvegardes. Dans Docker Compose : `/data` (volume). Sans Docker : par ex. `/var/lib/good-engineers/data`. |

## Option B — VPS sans Docker

1. Python 3.11+, dépendances : `pip install -r requirements.txt`

2. Créer un répertoire de données et l’exporter :
   ```bash
   sudo mkdir -p /var/lib/good-engineers/data
   sudo chown $USER:$USER /var/lib/good-engineers/data
   export GOOD_ENGINEERS_DATA_DIR=/var/lib/good-engineers/data
   ```

3. Lancer Streamlit :
   ```bash
   streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
   ```

4. **Service systemd** : créer une unité `systemd` qui définit `Environment=GOOD_ENGINEERS_DATA_DIR=...` et lance la commande ci-dessus, avec `Restart=always`.

## PostgreSQL / MySQL sur Contabo

L’application **n’est pas** branchée sur PostgreSQL ou MySQL aujourd’hui : tout le SQL est écrit pour **SQLite**. Contabo peut tout à fait héberger une base PostgreSQL sur le même VPS pour d’autres projets, mais **passer cette app sur PostgreSQL** impliquerait une refonte importante (couche d’accès aux données, syntaxe SQL, migrations). Pour cette application, **SQLite + sauvegardes du dossier données** est le modèle prévu.

## Sauvegardes

- Sauvegarder régulièrement le contenu de `GOOD_ENGINEERS_DATA_DIR` (fichiers et sous-dossiers).
- En Docker : `docker run --rm -v good-engineers_goodengineers_data:/data -v $(pwd):/backup alpine tar czf /backup/good-engineers-data.tgz -C /data .`

## Sécurité (rappel)

- Protéger l’accès (HTTPS, mots de passe forts, pare-feu).
- Les mots de passe utilisateurs sont actuellement stockés en clair dans `app_database.json` : à traiter avant une mise en production sensible (hachage, secrets, etc.).
