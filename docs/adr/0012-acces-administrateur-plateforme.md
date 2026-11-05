# ADR-0012 : Accès administrateur plateforme (backoffice)

## Statut

Accepté — 31 octobre 2026

## Contexte

L'éditeur doit pouvoir voir l'activité de la plateforme (indicateurs, liste des boutiques) et suspendre ou réactiver une boutique. Or le RLS (ADR-0002) cloisonne tout par `app.current_store_id` : aucune session ne voit plusieurs boutiques.

Contraintes :

- ne pas affaiblir l'isolation entre commerçants ;
- un jeton commerçant ne doit jamais ouvrir une route admin, et inversement ;
- hébergement Render gratuit : pas de shell pour lancer une commande de création de compte.

## Décision

- **Flag de session + politiques RLS additionnelles.** La session `AdminDbSession` (`get_admin_db`) exécute `SET LOCAL app.is_platform_admin = 'on'`. La migration `f3a9b1c7d2e5` ajoute des politiques permissives, en plus de l'isolation existante : `rls_stores_platform_admin_read`, `rls_stores_platform_admin_update` (sur `stores`) et `rls_sales_platform_admin_read` (lecture seule sur `sales`), toutes conditionnées par `current_setting('app.is_platform_admin', true) = 'on'`. Les routes commerçant n'activent jamais ce flag.
- **Table `platform_admins`** (email, hash Argon2, compteur d'échecs, verrouillage) : ni `store_id` ni RLS.
- **Jeton distinct.** Clé `ADMIN_JWT_SECRET` (`admin_jwt_secret_key`), `aud = "pos-admin"`, `type = "admin"`, 120 min, pas de refresh. Secret vide : le login admin répond 403 « Admin access is not configured. ». Verrouillage après 5 échecs pendant 15 min (incrément atomique en base).
- **Compte admin créé par l'environnement.** `seed_platform_admin` (`app/core/seed.py`) lit `ADMIN_EMAIL` / `ADMIN_PASSWORD` au démarrage ; idempotent, n'écrase jamais un admin existant. Choisi plutôt qu'une commande CLI car Render gratuit n'a pas de shell. `seed_superadmin` (`SUPERADMIN_*`) est sans rapport : il crée un compte **commerçant**.
- **Suspension.** `stores.suspended_at` et `stores.suspension_reason`. `assert_store_active` est appelé dans `get_tenant_db` ; le login et le refresh effectuent une vérification inline équivalente (pas `assert_store_active` lui-même) : 403 `{"detail": "Store is suspended.", "code": "STORE_SUSPENDED", "field": null, "details": {"support_contact": <SUPPORT_CONTACT>, "support_whatsapp": <SUPPORT_WHATSAPP>}}`. `SUPPORT_WHATSAPP` (optionnelle) est le numéro WhatsApp du support, indicatif pays inclus. `SUPPORT_CONTACT` doit être renseignée (chaîne vide sinon ; un avertissement `support_contact_missing` est journalisé au démarrage). Les autres erreurs n'ont pas de clé `details`.
- **Endpoints** (`/api/v1/admin`) : `POST /auth/login`, `GET /metrics`, `GET /metrics/daily`, `GET /stores`, `GET /stores/{id}`, `POST /stores/{id}/suspend`, `POST /stores/{id}/reactivate`, `GET /users`, `GET /audit-log`. Les requêtes SQL du repository sont paramétrées. Tout est en lecture seule, sauf la suspension : aucune action sur les comptes utilisateurs.
- **Lecture des produits** (migration `a7c3e9f2b4d1`) : politique `rls_products_platform_admin_read` (SELECT seul, même condition), pour compter les produits dans la fiche boutique. `users` n'a pas de RLS ; la liste des comptes joint `stores` grâce à `rls_stores_platform_admin_read`.
- **Journal `admin_audit_log`** (même migration) : une entrée par connexion réussie, suspension et réactivation, écrite dans la transaction de l'action. Table plateforme, ni `store_id` tenant ni RLS. Immuable : un trigger refuse UPDATE et DELETE, sauf le passage de `admin_id` à NULL par `ON DELETE SET NULL` (suppression de la ligne admin, voir la rotation du mot de passe). `admin_email` et `store_name` sont copiés ; `store_id` n'a pas de clé étrangère pour que l'entrée survive à la purge de la boutique (ADR-0011). Les échecs de connexion ne sont pas journalisés (déjà comptés par le verrouillage).

## Alternatives considérées

### Rôle PostgreSQL `BYPASSRLS` pour l'admin

Rejetée : contourne toutes les tables sans granularité (tout ou rien) et impose une seconde connexion/pool.

### Fonctions `SECURITY DEFINER`

Rejetée : disperse la logique d'agrégation en SQL, plus difficile à tester et à versionner que le repository Python.

### Même clé JWT que les commerçants, distinguée par un claim

Rejetée : une fuite ou une erreur de validation d'un côté ouvrirait l'autre. Une clé et une audience distinctes l'empêchent.

### Création de l'admin par commande CLI

Rejetée : pas de shell sur Render gratuit.

## Conséquences

### Positives

- L'isolation commerçant est inchangée ; l'élévation est explicite, locale à la transaction et limitée à des tables et opérations précises (lecture `sales`, lecture/écriture `stores`).
- Ajouter un accès admin à une autre table = une politique dans une migration, visible en revue.
- Admin désactivé par défaut tant que `ADMIN_JWT_SECRET` est vide.

### Négatives

- Le mot de passe admin initial transite par une variable d'environnement.
- Pas de refresh : reconnexion toutes les 2 h.
- Un access token déjà émis reste valide jusqu'à sa prochaine requête passant par `get_tenant_db`.
- Le verrouillage (5 échecs / 15 min, sans limite par IP) peut être abusé pour bloquer l'unique admin hors de son compte : compromis accepté.
- Rotation du mot de passe : le seed ne réécrit jamais un admin existant, donc changer `ADMIN_PASSWORD` n'a aucun effet. Pour le changer, mettre à jour `password_hash` en base (haché via `app.core.security.hash_password`) ou supprimer la ligne `platform_admins` avant le redémarrage.

### Neutres

- Un seul niveau d'administrateur, aucun rôle fin.

## Point ouvert : rôle DB réellement utilisé en dev/prod

Le login lit `stores` par `owner_id` sans contexte boutique, sous `FORCE ROW LEVEL SECURITY`. Cela ne fonctionne que si l'API se connecte avec un superutilisateur ou un rôle `BYPASSRLS`. Les tests utilisent le rôle non-superutilisateur `pos_app` ; si dev/prod utilisent un superutilisateur, **le RLS n'y est peut-être pas appliqué**. À vérifier (hors périmètre de cette tâche), puis à corriger si besoin (rôle applicatif sans `BYPASSRLS`, et lecture par une politique ou fonction dédiée au login).

## Critères qui justifieraient de revisiter cette décision

- Plusieurs administrateurs avec des droits différents.
- Besoin de MFA ou d'un audit log des actions admin.
- Backoffice destiné aux commerçants (autre périmètre, autre ADR).
- Accès shell disponible en production (reviendrait à une commande CLI).
