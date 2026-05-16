# Runbook opérationnel

> Procédures pour opérer le système en production. À lire à 2h du matin quand quelque chose casse.
> Dernière mise à jour : 29 avril 2026 — version 1.0.

Ce document liste les procédures opérationnelles courantes. Chaque procédure suit la même structure : contexte, prérequis, étapes, vérification, troubleshooting.

## Sommaire

1. [Setup initial du serveur](#setup-initial-du-serveur)
2. [Déploiement d'une nouvelle version](#déploiement-dune-nouvelle-version)
3. [Backups et restauration](#backups-et-restauration)
4. [Monitoring et alerting](#monitoring-et-alerting)
5. [Procédures d'urgence](#procédures-durgence)
6. [Maintenance courante](#maintenance-courante)

## Setup initial du serveur

### Contexte

Préparer un VPS Hetzner fraîchement provisionné pour héberger l'application. À faire une seule fois lors de la mise en place.

### Prérequis

- VPS Ubuntu 24.04 LTS provisionné chez Hetzner (CPX11 minimum)
- Nom de domaine pointant vers l'IP du VPS (enregistrement A)
- Accès SSH par clé publique configuré (jamais par mot de passe)
- Compte Brevo créé avec une clé API SMTP
- Compte Backblaze B2 avec un bucket dédié et une application key

### Étapes

```bash
# 1. Mettre à jour le système
ssh root@<IP_VPS>
apt update && apt upgrade -y

# 2. Créer un utilisateur non-root
adduser pos
usermod -aG sudo pos
mkdir -p /home/pos/.ssh
cp ~/.ssh/authorized_keys /home/pos/.ssh/
chown -R pos:pos /home/pos/.ssh
chmod 700 /home/pos/.ssh
chmod 600 /home/pos/.ssh/authorized_keys

# 3. Désactiver le login root SSH
sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# 4. Configurer le firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw enable

# 5. Installer Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker pos

# 6. Cloner le repo
su - pos
git clone <URL_REPO> ~/pos-mobile
cd ~/pos-mobile

# 7. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec les vrais secrets (DB password, JWT secret, Brevo, B2)

# 8. Lancer le stack
docker compose up -d

# 9. Appliquer les migrations
docker compose exec api alembic upgrade head

# 10. Vérifier que tout tourne
curl https://<DOMAINE>/health
```

### Vérification

- `docker compose ps` montre 3 services en état `running` (caddy, api, postgres)
- `https://<DOMAINE>/health` répond `{"status": "ok"}`
- `https://<DOMAINE>/docs` affiche le Swagger UI
- `ufw status` montre uniquement les ports 22, 80, 443 ouverts

### Troubleshooting

- **Caddy n'arrive pas à obtenir un certificat TLS** : vérifier que le DNS pointe correctement et que les ports 80/443 sont accessibles depuis Internet (`curl -I http://<DOMAINE>` depuis ailleurs)
- **PostgreSQL ne démarre pas** : vérifier les permissions du volume Docker (`docker compose logs postgres`)
- **API renvoie 502** : vérifier que `api` est démarré et que Caddy le voit (`docker compose logs api` et `docker compose logs caddy`)

## Déploiement d'une nouvelle version

### Contexte

Déployer une nouvelle version du code en production. Procédure manuelle au MVP, à automatiser via GitHub Actions plus tard.

### Prérequis

- Tests locaux passants
- Migration testée sur un environnement de staging
- Backup récent (< 24h) confirmé

### Étapes (déploiement standard sans migration DB)

```bash
ssh pos@<IP_VPS>
cd ~/pos-mobile

# 1. Récupérer la nouvelle version
git pull origin main

# 2. Reconstruire les images Docker si le code a changé
docker compose build api

# 3. Redémarrer le service api uniquement
docker compose up -d api

# 4. Vérifier les logs pendant 30 secondes
docker compose logs -f api
```

### Étapes (déploiement avec migration DB)

```bash
# 1. Backup avant migration (sécurité)
./scripts/backup-now.sh

# 2. Récupérer la nouvelle version
git pull origin main

# 3. Reconstruire les images
docker compose build api

# 4. Lancer la migration
docker compose run --rm api alembic upgrade head

# 5. Redémarrer api avec la nouvelle version
docker compose up -d api

# 6. Vérifier
curl https://<DOMAINE>/health
```

### Vérification

- L'endpoint `/health` répond avec la nouvelle version (renvoyer la version dans le payload)
- Les logs ne contiennent pas d'erreurs au démarrage
- Un compte de test peut se connecter et faire une vente

### Rollback

Si quelque chose ne va pas après déploiement :

```bash
git log --oneline -5  # voir les 5 derniers commits
git reset --hard <SHA_VERSION_PRECEDENTE>
docker compose build api
docker compose up -d api
```

Si une migration a été appliquée et doit être annulée :

```bash
docker compose run --rm api alembic downgrade -1
```

**Attention** : les migrations qui suppriment des données ne sont pas reversibles automatiquement. Toujours backup avant.

## Backups et restauration

### Contexte

La base PostgreSQL contient toutes les données métier consolidées. Un backup quotidien chiffré est uploadé vers Backblaze B2.

### Procédure de backup automatique

Cron job configuré dans `/etc/cron.d/pos-backup` :

```cron
0 2 * * * pos /home/pos/pos-mobile-ci/scripts/backup-daily.sh >> /var/log/pos-backup.log 2>&1
```

Le script `backup-daily.sh` (à créer) :

1. Lance `pg_dump` du conteneur PostgreSQL
2. Compresse en gzip
3. Chiffre avec GPG (clé publique du mainteneur)
4. Upload vers Backblaze B2 avec rclone
5. Supprime les backups locaux > 7 jours
6. Vérifie que le backup uploaded est lisible (via `b2 ls`)

### Procédure de backup manuel

À faire avant toute opération risquée (migration, refactor, etc.) :

```bash
ssh pos@<IP_VPS>
cd ~/pos-mobile-ci
./scripts/backup-now.sh
```

Le backup est sauvegardé localement dans `~/backups/manual/` ET uploadé vers B2.

### Procédure de restauration

```bash
# 1. Récupérer le backup depuis B2
rclone copy b2:pos-backups/2026-04-29.sql.gz.gpg ~/restore/

# 2. Déchiffrer et décompresser
gpg --decrypt ~/restore/2026-04-29.sql.gz.gpg | gunzip > ~/restore/2026-04-29.sql

# 3. Arrêter l'API pour éviter les écritures pendant la restauration
docker compose stop api

# 4. Restaurer dans une DB temporaire (sécurité, on ne touche pas la prod directement)
docker compose exec postgres createdb -U pos pos_restore_test
docker compose exec -T postgres psql -U pos pos_restore_test < ~/restore/2026-04-29.sql

# 5. Vérifier les données dans pos_restore_test
docker compose exec postgres psql -U pos pos_restore_test -c "SELECT COUNT(*) FROM stores;"

# 6. Si tout va bien, swap les bases
docker compose exec postgres psql -U pos -c "ALTER DATABASE pos RENAME TO pos_old;"
docker compose exec postgres psql -U pos -c "ALTER DATABASE pos_restore_test RENAME TO pos;"

# 7. Redémarrer l'API
docker compose up -d api

# 8. Vérifier
curl https://<DOMAINE>/health
```

### Test de restauration mensuel

**Obligatoire** : tester la restauration une fois par mois sur un VPS de test. Un backup non testé n'est pas un backup. Documenter chaque test dans un journal.

## Monitoring et alerting

### MVP : monitoring minimal

Au MVP, pas d'outil de monitoring sophistiqué (Grafana, Prometheus). On utilise :

- **UptimeRobot** (gratuit) : ping HTTPS toutes les 5 min sur `/health`. Alerte par email si > 1 min de downtime.
- **Logs Docker** : consultables via `docker compose logs -f api` quand on investigue un problème.
- **Métriques système** : `htop`, `df -h`, `free -h` pour vérifier ponctuellement la santé du VPS.

### Vérifications hebdomadaires manuelles

Tous les lundis matins, faire :

```bash
ssh pos@<IP_VPS>
cd ~/pos-mobile

# Espace disque
df -h

# RAM et CPU
free -h
top -bn1 | head -20

# Logs des 24 dernières heures
docker compose logs --since 24h api | grep -i "error\|exception" | tail -30

# Taille de la DB
docker compose exec postgres psql -U pos pos -c "SELECT pg_size_pretty(pg_database_size('pos'));"

# Nombre de comptes actifs
docker compose exec postgres psql -U pos pos -c "SELECT COUNT(*) FROM users WHERE email_verified_at IS NOT NULL;"

# Dernier backup réussi
ls -lh ~/backups/
```

### Phase 2 : monitoring sérieux

Quand le MVP atteint 30+ commerçants, mettre en place :

- Sentry pour le tracking d'erreurs côté backend ET côté Flutter
- Une dashboard de métriques métier (DAU, ventes par jour, etc.)
- Logs centralisés (Loki ou similaire)

## Procédures d'urgence

### Le VPS ne répond plus

1. Vérifier le statut Hetzner : https://status.hetzner.com
2. Tenter un redémarrage via le panel Hetzner (web console)
3. Si le VPS répond mais HTTP non : SSH et `docker compose logs`
4. Si Docker est down : `systemctl status docker` puis `systemctl restart docker`
5. Si rien ne marche : restaurer depuis le dernier backup sur un nouveau VPS

### Les commerçants ne peuvent plus se connecter

Symptômes : login renvoie une erreur, ou les ventes ne sont plus synchronisées.

1. Vérifier le `/health` depuis l'extérieur : `curl -i https://<DOMAINE>/health`
2. Vérifier les logs de l'API : `docker compose logs --tail 100 api`
3. Vérifier la connectivité DB : `docker compose exec api python -c "from app.core.db import engine; print(engine.connect())"`
4. Si la DB est saturée en connexions : `docker compose restart api`
5. Si le problème persiste : restaurer le backup le plus récent

### Suspicion de fuite de données entre tenants

**Hautement critique.** Un commerçant signale qu'il voit des données qui ne sont pas les siennes.

1. **Couper l'accès** immédiatement : `docker compose stop api`
2. Logguer l'incident avec timestamp précis
3. Examiner les logs des dernières heures pour identifier les requêtes suspectes
4. Vérifier que les politiques RLS sont bien actives :
   ```sql
   SELECT schemaname, tablename, rowsecurity, forcerowsecurity 
   FROM pg_tables WHERE schemaname='public';
   ```
5. Si RLS désactivé sur une table tenant : c'est la cause probable, réactiver et redéployer
6. Identifier les boutiques affectées et notifier les commerçants concernés
7. Faire un post-mortem documenté dans `docs/incidents/`

### Le cron de backup a échoué pendant plusieurs jours

1. Vérifier les logs : `cat /var/log/pos-backup.log | tail -50`
2. Vérifier l'espace disque : `df -h`
3. Vérifier les credentials B2 : `rclone lsd b2:`
4. Lancer un backup manuel pour rattraper : `./scripts/backup-now.sh`
5. Comprendre pourquoi le cron a échoué et corriger

## Maintenance courante

### Renouvellement du certificat TLS

Géré automatiquement par Caddy. Aucune action requise. Le certificat se renouvelle ~30 jours avant expiration.

Pour vérifier :

```bash
echo | openssl s_client -servername <DOMAINE> -connect <DOMAINE>:443 2>/dev/null | openssl x509 -noout -dates
```

### Mise à jour des dépendances Python

Une fois par mois :

```bash
ssh pos@<IP_VPS>
cd ~/pos-mobile/backend

# Voir les dépendances obsolètes
pip list --outdated

# Mettre à jour requirements.txt manuellement après vérification
# Tester localement, puis :
git push origin main
# (déploiement standard)
```

### Mise à jour du système Ubuntu

Une fois par mois :

```bash
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y

# Si un redémarrage est requis (kernel update) :
sudo reboot

# Après le reboot, vérifier que tout est revenu :
docker compose ps
curl https://<DOMAINE>/health
```

### Création d'un compte de test pour debug

Quand un commerçant signale un bug, parfois il faut reproduire. Procédure :

```bash
docker compose exec postgres psql -U pos pos -f scripts/create-test-account.sql
```

Le script crée un compte avec email `test+<timestamp>@pos-mobile-ci.local`, mot de passe `TestPassword123`, et une boutique de test avec quelques produits seedés.

### Suppression d'un compte (RGPD-like)

Si un commerçant demande la suppression de ses données :

1. Faire un export de ses données : `./scripts/export-store.sh <store_id>`
2. Envoyer l'export au commerçant par email chiffré
3. Supprimer en cascade :
   ```sql
   DELETE FROM stores WHERE id = '<store_id>';
   -- Les FK ON DELETE CASCADE supprimeront produits, ventes, etc.
   DELETE FROM users WHERE id = '<owner_id>';
   ```
4. Documenter la demande et la suppression dans un journal

## Annexes

### Liens utiles

- Dashboard Brevo : https://app.brevo.com
- Backblaze B2 : https://secure.backblaze.com
- Statut Hetzner : https://status.hetzner.com
- Doc Caddy : https://caddyserver.com/docs
- Doc FastAPI : https://fastapi.tiangolo.com

### Contacts en cas d'incident

À compléter une fois le projet en production :

- Mainteneur principal : <nom> — <email> — <téléphone>
- Backup support : <à recruter>
- Hébergeur Hetzner support : https://www.hetzner.com/support
