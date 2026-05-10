# ADR-0003 : Synchronisation hybride événementiel + état

## Statut

Accepté — 29 avril 2026

## Contexte

L'application POS Mobile doit fonctionner intégralement en mode hors-ligne (le réseau mobile en Côte d'Ivoire est instable). Le téléphone est la source de vérité opérationnelle. Quand la connexion revient, les données locales doivent être synchronisées avec le backend.

Deux types de données très différents transitent dans la sync :

- **Ventes** : créées en continu, jamais modifiées, jamais supprimées (immuables comptables). Doivent être garanties d'être enregistrées exactement une fois côté serveur.
- **Catalogue produit** : créé, modifié, parfois soft-supprimé. Volumes faibles (50-300 produits par boutique).

La question : quel modèle de synchronisation choisir, sachant que les contraintes diffèrent radicalement entre ces deux types de données ?

## Décision

Adopter un modèle **hybride** :

- **Ventes** → synchronisation **événementielle append-only** avec idempotence par UUID client
- **Catalogue** → synchronisation **par état** avec last-write-wins basé sur `updated_at`

### Modèle événementiel pour les ventes

Chaque vente est un événement immuable. Le client génère un UUID v4 au moment de la création. Cet UUID est envoyé au serveur via `POST /api/v1/sync/sales`. Le serveur fait :

```sql
INSERT INTO sales (id, ...) VALUES ($uuid, ...) ON CONFLICT (id) DO NOTHING;
```

Si le client renvoie la même vente plusieurs fois (timeout réseau, crash, etc.), le serveur ne crée pas de doublon. Le client peut donc retry sans risque.

Une `sync_queue` côté SQLite local trace les ventes en attente. Une fois confirmée par le serveur, l'entrée est marquée `synced` puis purgée.

### Modèle par état pour le catalogue

Le client envoie l'état complet du produit avec son `updated_at` local. Le serveur compare :

- Si `client.updated_at > serveur.updated_at` → UPDATE (le client gagne)
- Si `serveur.updated_at >= client.updated_at` → 409 Conflict, le serveur renvoie son état au client qui doit s'aligner

Le client a un flag `dirty=true` sur les produits modifiés localement non encore synchronisés.

## Alternatives considérées

### Tout en événementiel (CQRS / event sourcing complet)

Tous les changements (produit créé, prix modifié, produit supprimé...) sont des événements stockés dans un journal append-only. L'état actuel est dérivé en rejouant les événements.

**Rejeté.** Avantages réels : audit complet, possibilité de "voyager dans le temps", découplage fort. Inconvénients pour ce projet :

- Complexité conceptuelle élevée (event store, projections, idempotence des handlers, versioning des événements)
- Tooling et débugging plus compliqués
- Solo dev MVP : trop de surface d'apprentissage pour un bénéfice limité au volume actuel
- Le catalogue produit est typiquement CRUD basique, l'event sourcing serait du luxe

À reconsidérer si le projet nécessite un audit log complet ou si on doit ajouter beaucoup de logique métier basée sur l'historique.

### Tout en état (last-write-wins partout)

Tout, y compris les ventes, est synchronisé via state-based avec `updated_at`.

**Rejeté.** L'événementiel pour les ventes apporte deux choses critiques :

1. **Idempotence native** via UUID : un retry après timeout ne crée pas de vente fantôme. En state-based, on aurait besoin d'un mécanisme externe (ex: token de requête).
2. **Sémantique correcte** : une vente n'est pas un "état", c'est un événement. Modéliser une vente avec `updated_at` est conceptuellement faux puisqu'elle ne se met jamais à jour.

### CRDT (Conflict-free Replicated Data Types)

Utiliser des structures de données qui convergent automatiquement (Yjs, Automerge).

**Rejeté.** CRDTs sont brillants pour les outils collaboratifs temps-réel (édition de doc à plusieurs). Pour un POS où un seul commerçant utilise sa boutique, c'est de l'over-engineering. La complexité d'intégration et l'overhead de stockage ne sont pas justifiés.

### Three-way merge avec common ancestor

Approche Git-like où on stocke à la fois l'état au moment du dernier sync et les modifications locales et serveur, puis on fait un merge à 3 voies.

**Rejeté.** Très puissant pour la résolution fine de conflits, mais nécessite de stocker un état "ancestor" en plus de l'état actuel, et les conflits sur des champs simples (prix d'un produit) ne justifient pas cette complexité.

## Conséquences

### Positives

- **Idempotence garantie pour les ventes** : aucun risque de doublon comptable, même en cas de mauvais réseau
- **Modèle simple à comprendre et déboguer** : les ventes vont dans une queue et sont envoyées en batch ; les produits ont un flag `dirty` et sont synchronisés un par un
- **Pas de framework CQRS lourd** : juste des appels HTTP idempotents et un peu de logique applicative
- **Évolution future possible** : si on veut ajouter de l'audit log sur les produits plus tard, on pourra introduire de l'événementiel sur ces tables sans tout réécrire

### Négatives

- **Asymétrie conceptuelle** : un développeur qui découvre le code doit comprendre que les deux flux fonctionnent différemment. Mitigé par la documentation (cet ADR + architecture.md).
- **Conflits last-write-wins peuvent perdre des données** : si un commerçant modifie un produit hors-ligne pendant que quelqu'un d'autre le modifie ailleurs, la dernière modification écrase la première sans avertissement. Acceptable au MVP (un seul user par boutique), à reconsidérer pour le multi-vendeurs en Phase 2.
- **Pas d'audit log natif sur le catalogue** : on ne peut pas reconstituer "qui a changé le prix du produit X et quand". Si besoin, ajouter une table `product_price_history` plus tard.

### Neutres

- La queue de sync côté SQLite peut grossir si la connexion est coupée longtemps (plusieurs jours). Prévoir une limite + alerte si > 1000 entrées en attente.

## Critères qui justifieraient de revisiter cette décision

- Passage en multi-vendeurs où plusieurs personnes peuvent modifier le catalogue simultanément (vraisemblablement mauvais à gérer en LWW)
- Besoin d'un audit log complet pour des raisons réglementaires ou juridiques
- Apparition de cas d'usage où "voyager dans le temps" sur les données serait utile (ex: voir l'état du catalogue à une date donnée)
