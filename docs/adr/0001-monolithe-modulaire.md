# ADR-0001 : Monolithe modulaire FastAPI

## Statut

Accepté — 29 avril 2026

## Contexte

Le projet POS Mobile CI démarre comme un MVP développé en mode solo par un seul développeur. Le système comporte plusieurs domaines fonctionnels distincts : authentification, catalogue produit, ventes, synchronisation, gestion de boutique.

La question : faut-il dès le départ découper le backend en plusieurs services indépendants (microservices), ou tout regrouper dans une seule application (monolithe) ?

Contraintes spécifiques :

- Un seul développeur au MVP, peu de bande passante pour gérer de la complexité opérationnelle
- Volume cible MVP : ~50 commerçants en bêta, ~100 commerçants en GA initiale
- Budget infrastructure ultra-contraint (< 10 €/mois)
- Pas de devops dédié

## Décision

Le backend est une **application FastAPI unique** (un seul process, un seul `Dockerfile`, un seul déploiement) organisée en **modules métier** internes faiblement couplés.

Structure :

```
backend/app/
├── core/              Code transverse (config, DB, auth, helpers)
└── modules/
    ├── auth/
    ├── stores/
    ├── catalog/
    ├── sales/
    └── sync/
```

Chaque module suit la même structure interne (`router`, `service`, `repository`, `schemas`, `models`). Les modules communiquent via leurs services exposés, jamais directement via leurs repositories ou modèles.

## Alternatives considérées

### Microservices

Découper dès le départ en services distincts (auth-service, catalog-service, sales-service...) déployés indépendamment.

**Rejeté.** Pour un solo dev avec ce volume, ce serait du sur-engineering grave. Gérer N services distincts implique :

- N pipelines CI/CD
- Une couche de communication inter-services (REST ou messaging)
- Des outils de tracing distribué (Jaeger, OpenTelemetry)
- Une orchestration (Kubernetes ou Nomad)
- Une gestion plus fine des transactions distribuées

Tout ça pour résoudre des problèmes qu'on n'a pas (équipes multiples, scale extrême, déploiements indépendants).

### Monolithe sans modules ("big ball of mud")

Tout le code dans un seul namespace plat sans organisation.

**Rejeté.** Le code devient illisible et impossible à faire évoluer dès qu'il dépasse quelques milliers de lignes. La modularité est gratuite à mettre en place dès le départ.

### Architecture hexagonale stricte

Découpage fort par couches (domain / application / infrastructure) avec inversion de dépendances rigoureuse, ports et adapters partout.

**Rejeté pour le MVP.** Apporte une complexité conceptuelle et de boilerplate qui n'est pas justifiée à ce stade. À reconsidérer si le projet grossit beaucoup et qu'on a besoin de tester unitairement la logique métier sans aucune dépendance à FastAPI ou SQLAlchemy.

## Conséquences

### Positives

- Une seule application à déployer, à monitorer, à débugger
- Transactions DB simples (toutes les opérations dans une seule connexion)
- Facile à exécuter en local (`docker compose up`)
- Tests d'intégration simples (un seul process à lancer)
- Performances optimales (pas de latence réseau inter-services)
- Empreinte mémoire et CPU minimale (un seul process Python)
- Si un mentor ou co-fondateur rejoint, le code est lisible

### Négatives

- Le scale horizontal est plus grossier (on scale toute l'application, pas un service spécifique). Acceptable jusqu'à ~500-1000 commerçants.
- Une faute dans un module peut potentiellement crasher tout le process. Mitigé par des tests sérieux et la gestion d'erreurs FastAPI.
- Migrer vers des microservices plus tard nécessitera du travail. Acceptable : la modularité interne facilitera le découpage si on en a vraiment besoin.

### Neutres

- Le déploiement est moins fréquent que dans une approche microservices, mais c'est OK en solo (on déploie quand on a quelque chose à déployer).

## Critères qui justifieraient de revisiter cette décision

- Volume > 5000 commerçants actifs avec contention sur la DB
- Multiples équipes avec des cycles de release différents (jamais avant le MVP)
- Besoin réel de scaler indépendamment certains modules (ex: le module sync devient le goulot)
- Refonte majeure du produit avec de nouveaux domaines
