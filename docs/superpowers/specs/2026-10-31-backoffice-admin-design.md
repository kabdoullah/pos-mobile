# Backoffice administrateur plateforme — conception

> Date : 31 octobre 2026 · Statut : validé
> Légende : **[décidé]** = choix de l'utilisateur · **[mon choix]** = proposition de Claude, modifiable

## 1. Intention

Le propriétaire de la plateforme POS (seul administrateur) n'a aujourd'hui aucune vue d'ensemble : il ne sait pas combien de commerçants sont inscrits, combien utilisent réellement l'app, ni comment agir sur un compte problématique. Le backoffice répond à deux besoins **[décidé]** :

1. **Regarder** : mesurer l'adoption (inscriptions, boutiques actives, volume de ventes) et repérer les boutiques à relancer.
2. **Agir** : suspendre / réactiver une boutique.

Succès : en ouvrant le backoffice le matin, l'admin sait en 10 secondes si l'app « marche » et peut couper une boutique en deux clics.

Note : `docs/architecture.md:376` classe « Application web compagnon (back-office) » hors MVP. Ce projet la fait entrer dans le périmètre, avec un public différent : l'administrateur de la plateforme, pas le commerçant. Mettre cette ligne à jour.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- Tableau de bord d'indicateurs plateforme (section 4.1).
- Liste des boutiques avec activité et statut (section 4.2).
- Suspension / réactivation effective au prochain contact serveur (section 4.3).
- Déploiement du front sur Netlify **[décidé]**.

**Non-objectifs (V1)** **[mon choix]**
- Modifier les données d'une boutique (produits, ventes, profil).
- Abonnements, facturation, paiements.
- Plusieurs administrateurs, rôles, écran de gestion des admins **[décidé : admin unique pour le moment]**.
- Double authentification (TOTP) **[décidé : mot de passe seul pour commencer]**.
- Consultation du détail des ventes ou du catalogue d'une boutique.

**Anti-objectifs** (échec même si « ça marche »)
- Affaiblir l'isolation RLS des routes commerçants (ADR-0002). Le chemin admin doit être un chemin à part, impossible à emprunter avec un token commerçant.
- Un token commerçant qui donne accès à une route admin, ou l'inverse.
- Une boutique suspendue qui continue à synchroniser des ventes.
- Perte de données lors d'une suspension (les données sont conservées, la réactivation rend tout).

## 3. Contraintes et état actuel (constaté dans le code)

- Backend FastAPI + PostgreSQL, RLS `FORCE` sur `stores`, `products`, `sales`, `sale_items`, `stock_movements`, `categories`, etc. La politique `rls_stores_self_access` filtre sur `app.current_store_id`.
- Aucune notion d'admin : tous les `users` sont des commerçants, une boutique par user (`stores.owner_id` unique).
- `users.is_active` existe et est vérifié **seulement** au login et au refresh (`app/modules/auth/service.py:96`, `:119`), pas à chaque requête. Un access token reste donc valide jusqu'à expiration.
- JWT : types `access` (porte `store_id`) et `refresh`. `StoreContextMiddleware` n'accepte que `type == "access"`.
- Exceptions centralisées (`app/core/exceptions.py`) avec un champ `code` : on peut renvoyer un code métier distinct.
- CORS configurable via `CORS_ORIGINS` (ajouter l'URL Netlify).
- API dev sur Render free tier (`pos-mobile-vkuh.onrender.com`, cold start ~50 s), prod prévue sur `api.pos-mobile-ci.com` (Hetzner + Caddy).
- `fastapi-limiter` est en dépendance mais non branché, et `redis_url` est vide : il n'y a pas de rate limiting effectif aujourd'hui.
- Montants : `Numeric(12,2)` en base, `String` dans les DTO, `Decimal` dans le domaine.
- App mobile dans un dépôt séparé (`pos-mobile-app`).

**Point à vérifier avant de commencer (risque hors périmètre, mais il conditionne le design) :** le login lit `stores` par `owner_id` sans `app.current_store_id` positionné. Avec `FORCE ROW LEVEL SECURITY`, cela ne fonctionne que si l'API se connecte avec un rôle superuser ou `BYPASSRLS`. Si c'est le cas en dev/prod, le RLS n'y est pas appliqué du tout (seuls les tests le vérifient, via `SET LOCAL ROLE pos_app`). Le builder doit confirmer le rôle DB réellement utilisé sur Render/prod et le signaler. Ce n'est pas à corriger dans ce projet, mais le chemin admin ne doit pas *dépendre* de ce contournement.

## 4. Comportement attendu

### 4.1 Tableau de bord **[décidé]**

| Indicateur | Définition |
|---|---|
| Boutiques inscrites | `count(stores)`, plus le nombre créé sur les 7 derniers jours |
| Boutiques actives | boutiques avec ≥ 1 vente dont `created_at` est dans les 7 derniers jours |
| Ventes du jour | nombre et somme `total_amount` (FCFA) des ventes depuis minuit, fuseau Africa/Abidjan **[mon choix]** |
| Ventes de la semaine | idem sur 7 jours glissants |
| Boutiques inactives | inscrites depuis plus de 14 jours et sans vente depuis 14 jours (ou jamais) |

Les dates de vente sont celles de `sales.created_at` (heure côté client). Une vente faite hors ligne puis synchronisée tard peut donc modifier les chiffres d'un jour passé, ce qui est accepté. Les montants sont des ventes brutes (`total_amount`), retours non déduits **[mon choix, V1]**. Les boutiques suspendues sont comptées dans « inscrites » mais pas dans « actives » ni « inactives » **[mon choix]**.

### 4.2 Liste des boutiques **[décidé]**

Colonnes : nom, téléphone du propriétaire (`users.phone_number`, pas `stores.phone`), date d'inscription, date de la dernière vente, nombre total de ventes, statut (active / suspendue), action Suspendre / Réactiver.
**[mon choix]** Recherche par nom ou téléphone, filtre par statut et par « inactives », tri par dernière vente ou date d'inscription, pagination côté serveur par offset **[mon choix]** (la pagination existante, un curseur sur `(created_at, id)`, ne permet pas de trier par dernière vente).

### 4.3 Suspension **[décidé]**

- Une boutique suspendue **conserve toutes ses données** et peut être réactivée.
- Elle est bloquée **dès le prochain contact serveur** : login, refresh et **toute requête authentifiée** (y compris `/sync/*` et `/sales`), même avec un access token encore valide.
- Réponse : HTTP 403 avec `code = "STORE_SUSPENDED"` et un message lisible.
- Côté mobile (dépôt `pos-mobile-app`, lot séparé) : sur `STORE_SUSPENDED`, afficher un écran bloquant « Votre boutique est suspendue, contactez le support » avec un numéro ou email de contact. Les ventes locales non synchronisées restent dans la file locale, elles ne sont pas supprimées **[mon choix]**.
- **[mon choix]** Modèle : colonnes `stores.suspended_at TIMESTAMPTZ NULL` et `stores.suspension_reason TEXT NULL` (raison facultative saisie par l'admin, visible seulement dans le backoffice). On suspend la boutique et non le `user` : c'est l'unité métier, et cela reste correct le jour où il y aura plusieurs vendeurs par boutique.
- La confirmation de suspension dans le backoffice passe par une boîte de dialogue intégrée (pas `window.confirm`).

## 5. Architecture

### 5.1 Backend (ce dépôt) **[mon choix]**

- Nouveau module `app/modules/admin/` (router/service/repository/schemas/models), routes sous `/api/v1/admin/*`.
- **Compte admin** : table `platform_admins` (id, email, password_hash Argon2, failed_login_count, locked_until, last_login_at, created_at, updated_at). Ce n'est pas une table tenant : pas de `store_id`, pas de RLS. Création au démarrage depuis `ADMIN_EMAIL` / `ADMIN_PASSWORD` (`seed_platform_admin`), idempotente, sans jamais écraser un admin existant. **Écart avec la version initiale** (commande CLI `make create-admin`) : Render gratuit n'offre pas de shell, donc pas de CLI possible en production.
- **Login admin** : `POST /api/v1/admin/auth/login` (email + mot de passe). Verrouillage après 5 échecs pendant 15 minutes, stocké en base (pas de dépendance à Redis). Message d'erreur vague.
- **Token admin** : JWT `type = "admin"`, `aud = "pos-admin"`, signé avec une **clé distincte** `ADMIN_JWT_SECRET` **[mon choix]** (une clé commerçant ne peut pas forger ni ouvrir une route admin, et inversement), durée 2 h, sans refresh (on se reconnecte). Le middleware commerçant l'ignore déjà (il n'accepte que `access`). Nouvelle dépendance `CurrentAdminId` qui n'accepte que `type == "admin"` et vérifie que l'admin existe toujours.
- **Lecture multi-boutiques sans affaiblir le RLS** : nouvelle session `AdminDbSession` qui fait `SET LOCAL app.is_platform_admin = 'on'`, plus des politiques RLS additionnelles :
  - `SELECT` admin sur `stores` et `sales` (et toute autre table RLS nécessaire aux indicateurs) quand `current_setting('app.is_platform_admin', true) = 'on'`. `users` n'a pas de RLS, aucune politique n'est nécessaire ;
  - `UPDATE` admin sur `stores` uniquement, limité aux colonnes de suspension (appliqué côté repository ; si possible, ajouter un trigger qui refuse toute autre modification sous le flag admin).
  - Seule `AdminDbSession` positionne ce flag, et elle n'est utilisable qu'avec `CurrentAdminId`.
  - Les requêtes d'agrégation sont faites en SQL (count/sum/group by), pas en chargeant les lignes en Python.
- **Contrôle de suspension par requête** : dans `get_tenant_db` (point de passage unique des routes authentifiées), vérifier `stores.suspended_at` pour le `store_id` du token (lookup PK) et lever `StoreSuspendedError` (nouvelle sous-classe de `ForbiddenError`, `code = "STORE_SUSPENDED"`). Même contrôle dans `login` et `refresh`.
- **Nouvel ADR-0012** « Accès administrateur plateforme » : il complète l'ADR-0002 sans le remplacer, et explique le flag de session admin, les politiques additionnelles et pourquoi on n'utilise pas un rôle `BYPASSRLS`.
- Migration dédiée : table `platform_admins`, colonnes de suspension, politiques admin. `upgrade` et `downgrade` testés.
- CORS : ajouter l'origine Netlify dans `CORS_ORIGINS` (dev et prod).

### 5.2 Front backoffice (nouveau dépôt `pos-backoffice`) **[mon choix]**

- **React + Vite + TypeScript** : SPA statique, sans Next.js, puisque toute la logique est dans FastAPI et que Netlify sert du statique sans configuration de fonctions.
- Tailwind CSS, TanStack Query (cache et états de chargement/erreur), React Router.
- Pages : `/login`, `/` (tableau de bord), `/stores` (liste et actions).
- Token admin gardé **en mémoire + `sessionStorage`** (perdu à la fermeture de l'onglet, cohérent avec la durée de 2 h). Sur un 401, retour à `/login`.
- Montants reçus en `string`, formatés `fr-FR` sans décimales (`Intl.NumberFormat`), sans arithmétique côté front.
- Gestion explicite du cold start Render : indicateur « Le serveur démarre… » si la requête dépasse quelques secondes, timeout 60 s.
- URL de l'API via `VITE_API_URL` (variable d'environnement Netlify).
- Déploiement Netlify : build `npm run build`, dossier `dist`, redirection SPA `/* /index.html 200` dans `netlify.toml`, en-têtes de sécurité (CSP limitée à l'origine de l'API, `X-Frame-Options: DENY`). Déploiement automatique à chaque push sur `main`, previews sur les PR.
- **Previews de PR : build seulement** **[mon choix]**. On ne met ni wildcard ni regex dans le CORS de l'API pour une surface admin, donc les previews ne peuvent pas appeler l'API.
- Le site Netlify n'est pas indexé (`robots.txt` Disallow et `noindex`).

## 6. Tests et preuve attendus

- Backend : tests unitaires et d'intégration du module admin (login, verrouillage, token commerçant refusé sur `/admin/*`, token admin refusé sur les routes commerçants), test que la session tenant ne voit **pas** les autres boutiques même après l'ajout des politiques admin, tests de suspension (login, refresh, access token encore valide, `/sync`), exactitude des indicateurs sur un jeu de données connu. Couverture ≥ 70 % sur le module admin.
- Front : tests de composants sur le formatage des montants, la redirection 401 et le flux suspendre/réactiver (Vitest + Testing Library).
- Vérification manuelle : déploiement Netlify fonctionnel contre l'API Render.

## 7. Ordre de réalisation suggéré

1. Backend : ADR-0012, migration, module admin (auth, indicateurs, liste, suspension), contrôle de suspension.
2. Front : scaffold, login, tableau de bord, liste, déploiement Netlify.
3. Mobile (`pos-mobile-app`) : gestion de `STORE_SUSPENDED`.

## 8. Laissé au builder

- Noms exacts des endpoints et des schémas, structure interne des composants React.
- Choix de la bibliothèque de composants UI (ou aucune) et style visuel, sobre et lisible.
- Index éventuels pour les agrégations (par exemple `sales(store_id, created_at)` s'il n'existe pas déjà).

## 9. Décisions de déploiement (V1) **[mon choix, validé par « ok vas-y »]**

- **API ciblée** : Render (`pos-mobile-vkuh.onrender.com`) uniquement. Le passage en prod (`api.pos-mobile-ci.com`) est un lot ultérieur : backup, migration, `make create-admin` et `CORS_ORIGINS` côté prod.
- **Adresse du backoffice** : URL Netlify par défaut (`<site>.netlify.app`), ajoutée telle quelle dans `CORS_ORIGINS` sur Render. Un domaine personnalisé pourra venir plus tard.
- **Contact support** : variable `SUPPORT_CONTACT` côté API, renvoyée dans le corps de l'erreur `STORE_SUSPENDED` (champ additionnel `details.support_contact`, compatible avec le format d'erreur centralisé).
- **Dépôt `pos-backoffice`** : créé via `gh` par Claude si l'utilisateur est authentifié. La liaison Netlify (OAuth GitHub) est faite par l'utilisateur, guidé pas à pas.
- **Mobile** : écran « boutique suspendue » dans `pos-mobile-app`, traité juste après, dans un lot séparé.
