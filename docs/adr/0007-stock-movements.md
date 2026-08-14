# ADR-0007 : Traçabilité du stock via un ledger append-only (stock_movements)

## Statut

Accepté — 2 août 2026

## Contexte

`products.current_stock` existait déjà (INTEGER NULL, `NULL` = stock non géré) mais n'était qu'un champ déclaratif : le client (mobile ou Swagger) l'écrivait directement via `POST/PATCH /products` et la sync catalogue, et rien ne le décrémentait à la vente. Aucune trace de qui avait changé quoi ni pourquoi.

Un commerçant test a explicitement demandé de savoir, pour toute variation de stock, le **qui/quand/pourquoi** — pas seulement le solde courant. Deux décisions produit ont été actées avec le fondateur avant la conception technique :

1. **Traçabilité totale** : vente, ajustement manuel dédié, `PATCH /products/{id}`, sync catalogue et création de produit avec stock initial doivent tous produire une ligne immuable dans un historique.
2. **Le stock ne bloque jamais une vente** : si une vente fait passer `current_stock` sous zéro, elle passe quand même. Pas de 409, jamais.

Cette décision déroge à la règle MVP "pas d'audit log natif" évoquée dans l'ADR-0003 (Négatives) — c'est un arbitrage produit explicite du fondateur, pas un oubli.

## Décision

Ajout d'une table `stock_movements` : ledger **append-only et immuable** (même mécanisme que `sales` — trigger `BEFORE UPDATE`/`BEFORE DELETE` qui lève une exception). `products.current_stock` reste la colonne cache pour la lecture rapide, mais devient une valeur **dérivée** : toute variation transite par l'insertion d'un `StockMovement`.

### Nouveau module `inventory`, dépendance à sens unique vers `catalog`

`app/modules/inventory/` est un module autonome (router/service/repository/schemas/models), pas une extension de `catalog`. La dépendance ne va que dans un sens : **`inventory` importe `catalog.service`, jamais l'inverse**. `InventoryService` a besoin d'appeler `catalog` pour muter `current_stock` ; si `catalog` importait `inventory` en retour, ce serait un cycle d'import bloquant au chargement du module.

Conséquence directe : `catalog/service.py` ne connaît jamais `inventory`. L'orchestration "cette écriture doit produire un mouvement" se fait un niveau au-dessus de `ProductService` :

- `catalog/router.py` orchestre pour `POST/PATCH /products` (import de `InventoryService` autorisé — un router n'est importé par aucun service)
- `sales/service.py` orchestre pour la vente (`SaleService` appelle `InventoryService.record_sale_movements` après un insert de vente réussi)
- `sync/service.py` orchestre pour la sync catalogue

### Calcul en code applicatif, pas en trigger PL/pgSQL

Contrairement à `generate_receipt_number` (trigger nécessaire car couplé à l'upsert idempotent de `sales`), le calcul `current_stock = current_stock + delta` n'a aucune contrainte d'atomicité inter-requêtes qui justifierait un trigger : c'est un simple `UPDATE` protégé par le verrou de ligne MVCC standard. Le code vit dans `ProductRepository.adjust_stock` (pattern `setattr` + `flush` + `refresh`, identique à `ProductRepository.update`), pas en SQL. Plus simple à lire, à tester en pytest, et cohérent avec le reste du module `catalog`.

Le trigger sur `stock_movements` sert **uniquement à l'immuabilité** du ledger, pas à l'arithmétique.

### `NULL` reste un état de tracking distinct de `0`

`current_stock IS NULL` signifie "ce produit n'est pas suivi" (choix délibéré du commerçant), différent de `0` ("suivi, stock épuisé"). Une vente sur un produit non suivi **n'active jamais** le tracking automatiquement (elle génère quand même une ligne `stock_movements` pour la traçabilité de la vente, mais `resulting_stock` reste `NULL`). Un ajustement manuel ou une écriture catalogue/sync, en revanche, active le tracking explicitement — c'est un signal d'intention du commerçant.

`stock_movements.quantity_delta` est donc **nullable** : `NULL` représente la transition "désactivation du tracking" (`current_stock: X → NULL`), qui n'est pas un delta numérique. Contrainte DB : `quantity_delta IS NOT NULL OR resulting_stock IS NULL`.

### Le stock ne bloque jamais une vente — conséquence sur les contraintes

`products.current_stock` perd sa contrainte `>= 0` (`chk_products_current_stock_non_negative`), et `stock_movements.resulting_stock` n'en a volontairement aucune. `ProductRepository.adjust_stock` n'a pas de verrou `FOR UPDATE` : sous écriture concurrente sur le même produit, un lost update est possible et accepté (léger désynchronisme, pas une violation d'invariant métier).

### Un échec de traçabilité ne doit jamais faire échouer une vente

`InventoryService.record_sale_movements` catch et log toute exception par item, sans jamais la relancer. Un bug dans l'enregistrement d'un mouvement dégrade la traçabilité, jamais la capacité à encaisser.

### `POST /products` (création avec stock initial) est dans le scope

Un produit créé avec `current_stock: 50` produit une ligne `stock_movements` (`reason=catalog_update`, delta=50), au même titre qu'un PATCH — cohérent avec l'exigence de traçabilité totale du fondateur, sans quoi le ledger ne pourrait jamais expliquer la présence de ce stock initial.

## Alternatives considérées

### Trigger PL/pgSQL pour l'arithmétique (comme `generate_receipt_number`)

Rejeté : aucune contrainte d'atomicité multi-statement ne le justifie ici, contrairement au compteur `receipt_number` couplé à l'upsert idempotent de `sales`. Un trigger aurait été plus dur à lire, tester et faire évoluer (ex: activer/désactiver le tracking) qu'une méthode Python simple.

### `current_stock` entièrement piloté par trigger, tables `catalog`/`sync` inchangées

Rejeté : aurait laissé un trou de traçabilité béant sur `PATCH /products` et la sync — exactement le problème que le fondateur a demandé de résoudre.

### Verrouillage `SELECT ... FOR UPDATE` sur `products` lors de tout ajustement

Rejeté pour le MVP : la décision produit #2 accepte explicitement un léger désynchronisme sous concurrence plutôt que de complexifier avec du locking. Aucun `FOR UPDATE` n'existe ailleurs dans la base de code aujourd'hui — première introduction reportée jusqu'à preuve d'un besoin réel.

### Ajustement manuel intégré à la queue de sync offline mobile dès le MVP

Rejeté pour le MVP : l'endpoint `POST /inventory/movements` est online-only. Le catalogue et les ventes ont déjà leurs propres mécanismes de sync (ADR-0003) ; y greffer un troisième type de payload dès maintenant aurait été un chantier disproportionné pour un besoin non encore confirmé côté mobile hors-ligne.

## Conséquences

### Positives

- Ledger append-only auditable : qui/quand/pourquoi pour toute variation de stock, y compris les écritures indirectes (PATCH, sync).
- Aucune vente n'est jamais bloquée par un problème de stock, conforme à l'hypothèse d'adoption quotidienne sans friction.
- `inventory → catalog` à sens unique : pas de couplage circulaire, `catalog` reste ignorant de l'existence du module inventory.

### Négatives

- L'ajustement manuel (`POST /inventory/movements`) est online-only : un commerçant hors-ligne ne peut pas corriger son stock avant retour de connectivité. Gap documenté, à revisiter si confirmé comme un blocage réel en beta.
- `current_stock` peut devenir négatif : nécessite un traitement UI/UX côté mobile (affichage, alerte) qui n'est pas dans le scope de cet ADR (backend uniquement).
- Pas de `FOR UPDATE` : sous forte concurrence sur un même produit (peu probable en usage mono-boutique/mono-caissier au MVP), un lost update reste possible.

### Neutres

- `POST /products` avec stock initial est désormais tracé (contrairement à la portée initialement évoquée dans les échanges de conception) — comportement volontairement étendu pour rester cohérent avec l'exigence "tout est tracé".

## Critères qui justifieraient de revisiter cette décision

- Un commerçant confirme avoir besoin d'ajuster son stock hors-ligne (intégrer `stock_movements` à la `sync_queue`, cf. ADR-0003).
- Apparition de plusieurs caissiers/employés opérant simultanément sur le même produit (hors-scope MVP acté) : le lost update deviendrait plus probable, réévaluer `FOR UPDATE`.
- Besoin d'un job de réconciliation périodique si un désynchronisme entre `current_stock` et la somme des mouvements est un jour suspecté.
