# ADR-0005 : Stack Flutter + FastAPI + PostgreSQL 100% open source

## Statut

Accepté — 29 avril 2026

## Contexte

Le projet démarre en mode bootstrappé par un développeur solo qui a une expérience confirmée en génie logiciel. Le choix de stack technique est structurant pour les 2-3 prochaines années.

Critères de décision :

- **100% open source** : pas de SaaS payant, pas de licences propriétaires
- **Productivité solo** : un seul développeur doit pouvoir gérer toute la stack
- **Cross-platform mobile** : Android d'abord, iOS plus tard sans réécriture
- **Maturité et écosystème** : packages stables et maintenus pour les besoins critiques (Bluetooth ESC/POS, scanner caméra, sync offline)
- **Performance acceptable** : doit tourner sur des téléphones Android de gamme moyenne (3-4 Go RAM)

## Décision

| Couche | Technologie | Justification courte |
|---|---|---|
| Backend API | FastAPI 0.111+ | Productivité Python, typage Pydantic, OpenAPI auto |
| ORM | SQLAlchemy 2.0 | Mature, async natif, intégration Pydantic |
| Migrations | Alembic | Standard avec SQLAlchemy |
| Base de données | PostgreSQL 16 | Robuste, RLS, gratuit |
| Auth | python-jose + passlib | Pas de SaaS, intégration directe |
| Email transactionnel | aiosmtplib + Brevo | Offre gratuite 300 emails/jour |
| Frontend mobile | Flutter 3.x | Cross-platform, mature |
| Storage local | drift (SQLite typé) | ORM Flutter, streams réactifs |
| State management | Riverpod | Type-safe, testable |
| HTTP client | dio + retrofit | Génération depuis OpenAPI |
| Scanner | mobile_scanner | Basé ML Kit Google |
| Bluetooth ESC/POS | flutter_blue_plus + esc_pos_bluetooth | Combo standard |

## Alternatives considérées

### Backend : Node.js avec Express ou NestJS au lieu de FastAPI

**Rejeté.** FastAPI est plus productif en solo grâce à :

- Typage statique via Pydantic + type hints Python
- Documentation OpenAPI générée automatiquement (zéro effort)
- Performance comparable à Node.js sur des charges I/O-bound (uvicorn + asyncio)
- Préférence personnelle du développeur pour Python (à confirmer mais probable vu le choix initial)

### Backend : Django au lieu de FastAPI

**Rejeté.** Django est très complet (admin auto, ORM, auth) mais :

- Plus lourd et opinioné, moins flexible pour une API JSON moderne
- L'admin Django serait du gaspillage pour ce projet (pas de back-office au MVP)
- Moins performant que FastAPI sur des workloads async
- L'ORM Django est moins puissant que SQLAlchemy 2.0

### Backend : Go avec Echo ou Gin

**Rejeté.** Go offrirait des performances supérieures et un déploiement très simple (binaire unique). Mais :

- Productivité moindre en solo dev pour une API CRUD classique
- Écosystème moins fourni que Python pour des besoins comme l'envoi d'email, la génération de PDF, etc.
- Courbe d'apprentissage si pas déjà familier

### Frontend : React Native au lieu de Flutter

**Rejeté.** React Native est un choix très défendable. Raisons du choix Flutter :

- **Performances UI plus prévisibles** : Flutter dessine ses propres widgets, pas de pont JS/natif
- **Dart est plus simple** que TypeScript + JS bridge à comprendre
- **Écosystème Bluetooth ESC/POS plus mature** côté Flutter actuellement (`esc_pos_bluetooth`)
- **drift** (SQLite typé) est un meilleur ORM mobile que ce qu'offre RN actuellement (WatermelonDB est mature mais plus complexe)

### Frontend : Kotlin natif Android puis Swift natif iOS

**Rejeté.** Le natif offre la meilleure UX et performance, mais :

- Doubler le travail (deux codebases à maintenir) en solo dev = inacceptable
- Acceptable seulement avec une grosse équipe et un budget conséquent

### Base de données : MongoDB

**Rejeté.** Le modèle relationnel correspond parfaitement aux données du POS (entités structurées, relations FK, contraintes d'intégrité fortes). MongoDB serait un mauvais choix pour des données comptables qui demandent du ACID strict.

### Storage local Flutter : isar au lieu de drift

**Considéré, rejeté pour le MVP.** Isar est plus rapide et plus simple à utiliser que drift. Mais :

- L'auteur principal d'Isar a annoncé une pause sur le maintien (incertitude)
- drift est plus mature et l'écosystème SQLite est universel (debug, outils, formation)
- Les performances sont largement suffisantes au volume MVP

À reconsidérer si Isar reprend du momentum et si drift devient un goulot d'étranglement.

### Base de données serveur : SQLite tout court

**Rejeté.** SQLite est techniquement capable de gérer des dizaines de milliers d'utilisateurs en lecture concurrente, mais :

- Pas de RLS natif → on perdrait notre filet de sécurité multi-tenant
- Pas de réplication facile pour le scaling futur
- Outils opérationnels moins fournis (pg_dump > .dump SQLite)
- PostgreSQL est gratuit aussi, donc pas d'économie

## Conséquences

### Positives

- **Productivité solo élevée** : un seul langage côté backend (Python), un seul côté mobile (Dart). Outils standards et bien documentés partout.
- **Coût zéro** sur la stack elle-même (tout open source, hébergement seulement)
- **Compétences réutilisables** : Python, PostgreSQL, Flutter sont des compétences mainstream et embauchables si le projet grossit
- **Documentation auto-générée** côté API grâce à FastAPI
- **Génération de code mobile** depuis l'API : moins de boilerplate, moins de bugs

### Négatives

- **Dépendance à plusieurs packages communautaires** : si un package critique (esc_pos_bluetooth, drift, retrofit) cesse d'être maintenu, il faudra forker ou migrer. Surveiller l'activité GitHub.
- **Python n'est pas le langage le plus performant** : si un endpoint devient critique en perf, on pourrait avoir besoin de l'optimiser ou de réécrire en Go/Rust. Très peu probable au volume MVP.
- **Flutter compile en gros APK** : taille minimum ~15-20 Mo, ce qui peut être un frein de téléchargement sur des connexions mobiles lentes en CI. Acceptable mais à surveiller (Google Play permet le téléchargement par splits).

### Neutres

- Cette stack est éprouvée pour des projets de taille similaire dans le monde startup. Pas de pari technologique risqué.

## Critères qui justifieraient de revisiter cette décision

- Performance backend insuffisante (très peu probable au MVP)
- Un package Flutter critique abandonné sans remplaçant viable
- Besoin de fonctionnalités natives mobile non couvertes par Flutter (rare)
- Augmentation drastique de l'équipe avec des spécialistes d'autres stacks (ex: si un développeur Go senior rejoint, on pourrait migrer le backend)
