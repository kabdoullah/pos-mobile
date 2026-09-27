# ADR-0008 : Catégories produit, images (produit + logo) et reçus enrichis

## Statut

Accepté — 27 septembre 2026

## Contexte

La refonte UX de l'app mobile (onglets Accueil / Vendre / Stock / Ventes / Paramètres) demande des fonctions qui n'existent ni en base, ni dans l'API, ni dans la synchro :

1. **Catégories de produits** — organiser et filtrer le stock (« Boissons : 24 produits »).
2. **Image produit** — reconnaître un produit d'un coup d'œil en caisse et dans le stock.
3. **Reçus enrichis** — logo, téléphone de la boutique et nom du vendeur sur le ticket imprimé et le reçu PDF.

Contraintes qui pèsent sur la décision :

- **Offline-first** (ADR-0003) : le catalogue se crée et se modifie hors ligne ; le téléphone est la source de vérité opérationnelle.
- **Multi-tenant RLS** (ADR-0002) : toute nouvelle table tenant porte `store_id`, un index, une politique RLS et un test d'isolation.
- **Hébergement actuel** : Render free tier. Le **disque du conteneur est éphémère** (effacé à chaque déploiement/redémarrage) : impossible d'y stocker des fichiers. Cible prod : VPS Docker + Caddy (`docker-compose.yml`).
- **100 % open source, budget minimal** (ADR-0005) : pas de service payant imposé.
- **Réseau mobile instable et données chères** en Côte d'Ivoire : les images doivent être petites et téléchargées une seule fois.
- Volumes : 50 à 300 produits par boutique (ADR-0003).

Hors périmètre de cet ADR (aucun impact backend) : **changement de PIN** (le PIN est strictement local, ADR-0006), **moyens de paiement actifs** et **notifications de stock bas** (préférences de l'appareil). Ils sont traités directement dans l'app.

## Décision

### 1. Catégories — table tenant synchronisée par état

Nouvelle table `categories` :

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | **généré côté client** (création hors ligne, comme les produits) |
| `store_id` | UUID NOT NULL | FK `stores`, index, RLS |
| `name` | VARCHAR(60) NOT NULL | unique par boutique, insensible à la casse, parmi les non supprimées (index unique partiel sur `lower(name) WHERE deleted_at IS NULL`) |
| `created_at`, `updated_at` | TIMESTAMPTZ | trigger `set_updated_at` |
| `deleted_at` | TIMESTAMPTZ NULL | soft delete, comme `products` |

`products.category_id UUID NULL` → FK `categories(id)`. Un produit a **au plus une** catégorie (pas de N-N : inutile pour ce volume).

Synchronisation : **même modèle que le catalogue** (ADR-0003, état + last-write-wins sur `updated_at`, flag `dirty` côté mobile) :

- `POST /api/v1/sync/categories` (même contrat que la sync produits : `client_updated_at`, `deleted`, statuts `created/updated/no_change/conflict/deleted`).
- `GET /api/v1/sync/changes` renvoie en plus `categories: [...]`.
- `ProductSyncRequest` / `ProductResponse` gagnent `category_id`.
- **Ordre de push côté mobile : catégories, puis produits** (la FK doit exister côté serveur). Un produit qui référence une catégorie inconnue du serveur est refusé en 422 et reste `dirty` jusqu'au cycle suivant.
- **Suppression d'une catégorie** : dans la même transaction, le serveur remet `category_id = NULL` sur ses produits et bumpe leur `updated_at` → les autres appareils reçoivent la correction au pull. Côté mobile, même règle appliquée localement.

### 2. Images — stockées en base, servies par l'API, jamais dans la sync d'état

Deux tables dédiées (FK réelles, RLS, plutôt qu'une table générique « media » sans intégrité) :

- `product_images` : `product_id` PK/FK (`ON DELETE CASCADE`), `store_id` (RLS), `content BYTEA`, `content_type`, `width`, `height`, `sha256`, `updated_at`.
- `store_logos` : `store_id` PK/FK (RLS), mêmes colonnes.

Règles :

- **Stockage en PostgreSQL (`BYTEA`)**, pas sur disque ni dans un object storage. Justification : disque Render éphémère ; aucune infra ni secret supplémentaire ; les images partent dans les **backups existants** (`scripts/backup-now.sh`) ; RLS s'applique comme au reste. Volume attendu : 300 × ~40 Ko ≈ 12 Mo par boutique.
- **Normalisation serveur** (Pillow, déjà présent en dépendance transitive de `reportlab` — à déclarer explicitement) : ré-encodage WebP, 512 px max (produit) / 384 px de large max (logo, largeur d'une imprimante 58 mm), qualité ~75. Le ré-encodage **supprime les métadonnées EXIF** (GPS du téléphone) et neutralise les fichiers piégés. Type vérifié par magic bytes (JPEG/PNG/WebP), taille brute refusée au-delà de 5 Mo (413).
- **Endpoints** (online-only) :
  - `PUT /api/v1/products/{id}/image` (multipart), `GET` (avec `ETag` = `sha256`, `Cache-Control: private, max-age=31536000, immutable` + version dans l'URL), `DELETE`.
  - `PUT|GET|DELETE /api/v1/stores/me/logo`, mêmes règles.
- **Versionnement** : `ProductResponse` et la réponse boutique exposent `image_version` / `logo_version` (le `sha256`, `null` si pas d'image). L'état synchronisé ne transporte **jamais** le binaire, seulement la version.
- **Côté mobile** : téléchargement paresseux et mise en cache disque par version (`<id>_<version>.webp`) ; un changement de version invalide le cache. Compression côté client avant envoi (≤ 1024 px) pour économiser les données.
- **Upload online-only**, comme les mouvements de stock (ADR-0007) : hors ligne, le produit s'enregistre sans image et l'app propose d'ajouter la photo plus tard. Pas de file d'attente binaire dans la `SyncQueue`.
- Le logo est **mis en cache local** pour que l'impression Bluetooth fonctionne hors ligne ; sa version est vérifiée à chaque pull de la configuration boutique.

### 3. Reçus enrichis

- `stores.phone VARCHAR(20) NULL` (E.164, validé comme `users.phone`) → imprimé sous l'adresse, et dans le PDF.
- Logo : `store_logos` ci-dessus → imprimé en tête (raster ESC/POS monochrome, tramage côté mobile) et dans le PDF (`receipt_pdf.py`).
- **Vendeur** : `users.display_name VARCHAR(80) NULL` (éditable dans « Mon profil »). Imprimé « Vendeur : … » si renseigné. C'est une donnée **utilisateur**, pas boutique : elle reste correcte le jour où plusieurs vendeurs partageront une boutique.
- `receipt_footer_text` existe déjà ; l'écran « Reçus » l'expose. (Bug mobile corrigé au passage : l'édition de la boutique l'écrasait à `null`.)

### 4. Migrations et découpage

Une migration par sujet (règle backend) :

1. `add_categories` — table + RLS + trigger + index unique partiel + `products.category_id`.
2. `add_product_images_and_store_logos` — deux tables + RLS.
3. `add_store_phone_and_user_display_name` — colonnes nullables (aucune donnée à migrer).

Toutes réversibles (`downgrade` testé), aucune n'est une migration de données. Côté mobile : drift `schemaVersion` 5 → 6 (table `Categories`, colonnes `Products.categoryId` et `Products.imageVersion`), et **`LocalDataResetService.wipeBusinessData()` doit vider `categories`** (invariant changement de compte) ainsi que le cache d'images.

Ordre de livraison : backend (1→3) déployé avant l'app ; l'app reste compatible avec un serveur qui n'envoie pas encore les nouveaux champs (tous optionnels).

## Alternatives considérées

### Images sur le disque du serveur

**Rejeté.** Le disque Render est effacé à chaque déploiement : perte garantie. Même sur VPS, il faudrait un volume dédié et l'inclure aux backups.

### Object storage S3-compatible (Cloudflare R2, MinIO)

**Rejeté pour l'instant.** Solution standard à grande échelle, mais : nouvelle infra ou compte tiers, secrets à gérer, URLs pré-signées, isolation tenant à réimplémenter hors RLS, backups séparés. Disproportionné pour ~12 Mo par boutique. Voir critères de révision.

### Images uniquement locales (jamais envoyées)

**Rejeté.** Perdues à la réinstallation ou au changement de téléphone, absentes du reçu PDF (généré par le serveur), et impossibles à partager entre appareils d'une même boutique.

### Images dans la synchro d'état (base64 dans `ProductSyncRequest`)

**Rejeté.** Chaque modification de prix renverrait l'image ; payloads de sync × 50, coûteux en données mobiles et fragiles sur réseau instable.

### Upload d'image mis en file hors ligne

**Reporté.** Il faudrait stocker des binaires dans la `SyncQueue` et gérer leur ordre avec la création du produit. Le cas « photo prise hors ligne » est rare au MVP ; l'app propose de l'ajouter une fois en ligne.

### Catégories en texte libre sur le produit (`products.category VARCHAR`)

**Rejeté.** Pas de renommage global, doublons (« Boisson », « boissons »), pas de liste gérable. Le coût d'une vraie table est faible.

### Plusieurs catégories par produit (N-N)

**Rejeté.** Complexité de sync (table de liaison) sans besoin exprimé pour ce type de commerce.

## Conséquences

### Positives

- Aucune nouvelle infrastructure ni secret : tout passe par PostgreSQL, RLS et les backups existants.
- Catégories utilisables **hors ligne**, cohérentes avec le reste du catalogue.
- Images légères (WebP ≤ 512 px), sans métadonnées personnelles, téléchargées une seule fois par version.
- Le reçu imprimé fonctionne hors ligne, logo compris.

### Négatives

- La base grossit avec les images (≈ 12 Mo par boutique) : backups plus lourds, et le PostgreSQL gratuit de Render a une taille limitée.
- Servir des binaires par l'API consomme du CPU/bande passante du conteneur (atténué par le cache `immutable` côté client).
- Ajout d'une image impossible hors ligne.
- Un produit peut rester `dirty` un cycle de plus si sa catégorie n'a pas encore été poussée (auto-résolu au cycle suivant).
- Surface de sync élargie (un endpoint, un champ de plus dans `changes`) : tests de sync à étendre.

### Neutres

- `users.display_name` introduit une notion de profil utilisateur, prête pour le multi-vendeurs sans l'implémenter.
- Pillow devient une dépendance explicite du backend.

## Critères qui justifieraient de revisiter cette décision

- Taille cumulée des images > ~1 Go ou backups nettement ralentis → migrer vers un object storage (R2/MinIO) derrière la même API (`GET /products/{id}/image` peut rediriger vers une URL signée sans changer le mobile).
- Plusieurs images par produit, ou vidéos.
- Demande forte d'ajout de photos hors ligne → file d'upload binaire dédiée.
- Passage multi-vendeurs → revoir LWW sur les catégories (même critère qu'ADR-0003).
