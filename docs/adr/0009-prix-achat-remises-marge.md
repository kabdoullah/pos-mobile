# ADR-0009 : Prix d'achat, réductions et marge, instantané dans les ventes

## Statut

Accepté — 27 septembre 2026

## Contexte

Un produit n'avait qu'un prix (`unit_price`, en pratique le prix de vente). Les commerçants veulent :

- saisir un prix d'achat pour connaître leur marge ;
- accorder des réductions en caisse, sur une ligne ou sur toute la vente ;
- consulter plus tard le chiffre d'affaires, le coût d'achat et la marge.

Deux contraintes structurent la décision :

- **les ventes sont immuables** (ADR-0003, trigger PostgreSQL) et synchronisées hors ligne. Une vente doit porter tout ce qu'il faut pour se reconstruire sans jamais relire le produit actuel ;
- **montants exacts** : `Decimal` dans le domaine, `String` dans l'API, `TEXT` dans drift, `NUMERIC(12,2)` en base.

## Décision

### Produit

- `unit_price` est **renommé `selling_price`** partout : Dart, drift, API, base et modèle d'import CSV.
- `purchase_price` est ajouté, **nullable** : `NULL` signifie « non renseigné ». Les produits existants passent à `NULL`. Un 0 ferait croire à une marge de 100 %, et le prix de vente à une marge nulle.
- Aucune contrainte `selling_price > purchase_price` : vendre à perte est permis. L'UI affiche alors une marge négative.
- **Compatibilité transitoire** : le serveur accepte encore `unit_price` en entrée (alias Pydantic, colonne CSV). Ses réponses exposent `unit_price` (déprécié) en plus de `selling_price`, pour les versions de l'app déjà installées. Si une ancienne app n'envoie pas `purchase_price`, le prix d'achat serveur reste inchangé.

### Réductions

- `DiscountType { amount, percentage }` et un value object `Discount { type, value }` dans le domaine `sales`.
- Une réduction porte sur un **total brut** :
  - ligne : `unit_price × quantity` ;
  - vente : le sous-total, c'est-à-dire la somme des totaux nets des lignes.
- Elle ne modifie jamais le prix catalogue.
- Montant d'une réduction en pourcentage : **arrondi au franc entier, demi vers le haut**, plafonné au brut. La règle est identique côté Dart (`Discount.amountOn`) et Python (`discount_amount_for`).
- Validation :
  - valeur strictement positive ;
  - pourcentage ≤ 100 ;
  - montant ≤ brut.
- Garanties :
  - `line_total = brut − discount_amount ≥ 0` ;
  - `total_amount = Σ line_total − remise globale`.
- Si la quantité ou le panier change, une réduction en montant supérieure au nouveau brut est ramenée à ce brut (`Discount.fitTo`).
- **Réduction de ligne et remise globale sont deux concepts distincts**, stockés séparément.

### Instantané historique

Chaque ligne de vente fige, au moment de l'ajout au panier :

| Champ (API / base) | drift | Sens |
|---|---|---|
| `unit_price_at_sale` | `unit_price` | prix de vente appliqué |
| `purchase_price_at_sale` | `purchase_unit_price` | prix d'achat (NULL = inconnu) |
| `discount_type`, `discount_value` | idem | réduction saisie |
| `discount_amount` | idem | montant retiré |
| `line_total` | idem | total net payé |

La vente porte `discount_type`, `discount_value` et `discount_amount` (remise globale).

L'historique, le reçu et les marges se calculent **uniquement** depuis ces valeurs, jamais depuis le produit actuel.

### Marge

- Marge d'une ligne : `line_total − purchase_price_at_sale × quantity`, avec le prix réellement payé.
- `MarginSummary` donne le chiffre d'affaires, le coût, la marge brute et le taux de marge d'un ensemble de ventes :
  - la remise globale est répartie au prorata des lignes ;
  - les lignes au coût inconnu sont exclues du coût et de la marge, et signalées par `hasUnknownCost`.
- Le provider `todayMarginSummaryProvider` est prêt ; aucun écran de tableau de bord n'est ajouté.

### Confidentialité

Le prix d'achat et la marge ne s'affichent que :

- dans le formulaire produit ;
- dans la fiche produit ;
- dans un bloc « Infos internes » replié du détail de vente.

Ils n'apparaissent jamais en caisse, sur le reçu ESC/POS ou sur le reçu PDF.

## Migrations

- **drift v6 → v7** :
  - `RENAME COLUMN unit_price TO selling_price` ;
  - ajout de colonnes nullables ou avec `DEFAULT '0'`.
  - Aucune donnée supprimée.
- **Alembic `6935928f6907`** :
  - renommage de colonne et de contrainte ;
  - ajout des colonnes ;
  - `chk_sale_items_line_total` devient `line_total = unit_price_at_sale * quantity - discount_amount`, ce que les lignes existantes (réduction 0) satisfont.
  - `ADD COLUMN` est du DDL et ne déclenche donc pas les triggers d'immuabilité.
  - Le downgrade est **refusé** si une vente porte une réduction.

## Ordre de déploiement

**Le backend d'abord**, puis l'app :

- l'ancien backend rejetterait une vente remisée (contrainte `line_total`) ;
- le nouveau mobile lit `selling_price`, absent des anciennes réponses.

Une vente refusée reste dans la file de synchro et repart après le déploiement : aucune perte.

## Alternatives considérées

### Garder `unit_price` comme nom du prix de vente

Aucune rupture d'API, mais le nom reste ambigu à côté de `purchase_price`. Écarté par décision produit, avec une compatibilité transitoire pour limiter le risque.

### Prix d'achat obligatoire, défaut 0

Cela fausse toutes les marges des produits existants tant qu'ils ne sont pas corrigés.

### Réduction appliquée au prix unitaire

Cela produit des prix unitaires non entiers (500 FCFA sur 3 articles) et ne correspond pas à l'usage en caisse (« 500 de remise sur la ligne »).

### Ne stocker que le montant de la réduction

Cette option ne dit pas au commerçant qu'il a accordé « 10 % ». Le type et la valeur sont conservés en plus du montant.

### Ventiler la remise globale sur chaque ligne en base

Plus de colonnes et des arrondis à répartir. La ventilation est faite au calcul de la marge seulement.

## Conséquences

### Positives

- L'historique reste exact quelles que soient les modifications futures du catalogue.
- La marge est calculée sur le prix réellement payé.
- Aucune dépendance au produit côté serveur pour reconstruire une vente.

### Négatives

- La règle d'arrondi est dupliquée (Dart et Python) et doit rester alignée ; des tests la couvrent de chaque côté.
- `unit_price` reste exposé temporairement dans les réponses produit ; il faudra le retirer quand les anciennes versions ne circuleront plus.
- La marge par ligne affichée dans le détail d'une vente ignore la remise globale. Seul le total de marge la prend en compte.
