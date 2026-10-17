# ADR-0010 : Retours clients, remboursement manuel et validation serveur

## Statut

Accepté — 17 octobre 2026

## Contexte

Un client rapporte tout ou partie des articles d'une vente. Le commerçant doit enregistrer le retour, rendre l'argent et, si l'article est revendable, le remettre en stock.

Plusieurs contraintes structurent la décision :

- **les ventes sont immuables** (ADR-0003, trigger PostgreSQL) : un retour ne modifie jamais la vente d'origine ;
- **hors ligne d'abord** : les ventes sont enregistrées sans réseau et synchronisées plus tard (UUID client, idempotence) ;
- **plusieurs appareils** par boutique : deux téléphones hors ligne peuvent retourner les mêmes articles ;
- **aucune intégration de paiement** : un remboursement est fait à la main (espèces sorties de la caisse, transfert mobile money). Le système ne peut pas le déclencher ni constater son échec ;
- **paiement mixte** : seule la répartition espèces / mobile money est connue, pas l'opérateur ;
- **montants exacts** (ADR-0009) : `Decimal`, `NUMERIC(12,2)`, jamais de `double`.

## Décision

### Modèle

- Deux tables tenant **immuables** (trigger) avec RLS : `sale_returns` et `sale_return_items`.
- L'id du retour et de chaque ligne est un UUID généré par l'app : un nouvel envoi du même retour répond `already_exists`.
- **Chaque ligne de retour référence la ligne de vente** (`sale_item_id`), pas seulement le produit. Prérequis : une ligne de vente a le même id sur l'appareil et le serveur (l'app envoie l'id de ligne avec la vente).
- `return_number` séquentiel par boutique, posé par trigger depuis `stores.next_return_number`, comme `receipt_number`.
- Motif : `defective`, `damaged`, `wrong_product`, `sale_error`, `changed_mind`, `other` (commentaire obligatoire).
- État par ligne : `resellable`, `damaged`, `defective`, `unsellable`.
- Moyen de remboursement : `cash`, `mobile_money_orange`, `mobile_money_mtn`, `mobile_money_wave`. Par défaut dans l'app : le moyen d'origine si la vente a été payée d'un seul moyen, sinon espèces. Jamais « remboursé automatiquement sur le moyen d'origine ».

### Remboursement

**Le remboursement est confirmé au comptoir** : le commerçant atteste avoir rendu le montant au moment du retour. `refund_amount` est ce qui a été rendu. Il n'y a pas de statut « à rembourser » ni « échoué » : ils supposeraient un retour modifiable ou une intégration de paiement. Le statut de synchronisation est distinct et vit dans l'app.

### Calcul du montant (identique app et serveur)

Uniquement à partir des valeurs figées dans la vente, jamais du prix catalogue actuel. En entiers (francs) :

1. **Montant payé d'une ligne** : la remise globale est répartie au prorata des `line_total` (déjà nets de la réduction de ligne), au franc entier, par la méthode du plus fort reste. Égalités départagées par l'id de ligne croissant. La somme des montants payés vaut le total encaissé.
2. **Rembourser q unités sur Q dont r déjà retournées** : `floor(payé × (r+q) / Q) − floor(payé × r / Q)`. Formule cumulative : la somme des retours successifs d'une ligne vaut exactement son montant payé une fois entièrement retournée, jamais davantage.

L'app calcule et affiche le montant, le serveur le recalcule et refuse tout écart (`amount_mismatch`). Implémentation serveur : `app/modules/returns/refund.py`.

### Stock

Seul un article `resellable` dont le produit existe encore réintègre le stock : mouvement `customer_return` (lié par `sale_return_id`) dans la même transaction que le retour. Un produit au stock non suivi le reste. Les autres états sont tracés dans la ligne de retour (`restocked = false`) sans toucher au stock disponible.

### Synchronisation et concurrence

- `POST /api/v1/sync/returns`, par lots de 50, envoyé **après les ventes**. Chaque retour a son SAVEPOINT.
- Le serveur verrouille la vente (`SELECT … FOR UPDATE`), additionne les quantités déjà retournées, vérifie et recalcule, puis insère le retour et les mouvements. Deux retours concurrents d'une même vente sont donc sérialisés : le second voit les quantités du premier.
- Résultats : `created`, `already_exists`, `rejected` avec un `error_code` (`sale_not_found`, `item_not_in_sale`, `quantity_exceeded`, `amount_mismatch`) — définitif, ne pas renvoyer —, ou `failed` (erreur inattendue, à renvoyer).
- `GET /sync/changes` ajoute une phase `returns` (tri `synced_at`), après les ventes.

### Côté app

- Un retour n'est possible que sur une **vente synchronisée** (numéro de reçu attribué) : le serveur connaît la vente et ses lignes, le reçu de retour cite un vrai numéro.
- Enregistrement hors ligne permis : transaction locale (retour, lignes, stock, file de synchro), puis envoi.

## Alternatives considérées

### Retours en ligne uniquement

Comme les ajustements de stock (ADR-0007) : aucun conflit possible. Rejetée : le commerçant doit pouvoir rembourser sans réseau, comme il vend sans réseau.

### Modifier la vente (quantités, statut « retournée »)

Rejetée : la vente est immuable et sert de référence comptable. Un retour est un événement distinct.

### Rembourser au prorata du prix catalogue actuel

Rejetée : rembourserait un montant différent de celui payé (prix modifié, réductions).

### Arrondi indépendant de chaque retour

`round(payé × q / Q)` à chaque retour : la somme de retours successifs peut dépasser le montant payé. Rejetée au profit de la formule cumulative.

### Statuts de remboursement « en attente » / « échoué »

Rejetés pour la v1 : sans intégration de paiement, le système ne constate ni l'exécution ni l'échec d'un remboursement. Un statut « en attente » exigerait un second événement « remboursement effectué ».

## Conséquences

### Positives

- Aucune modification de la vente, historique complet et immuable.
- Pas de remboursement supérieur au payé, même avec des retours successifs ou une remise globale.
- Pas de dépassement de quantité côté serveur, même entre appareils.
- Idempotence de bout en bout (UUID client).

### Négatives

- **Conflit hors ligne entre deux appareils** : le second retour est refusé par le serveur alors que l'argent a peut-être déjà été rendu. L'app l'affiche ; le commerçant régularise à la main. Seul un mode en ligne obligatoire l'éviterait.
- Le calcul est dupliqué (Python et Dart) : les deux implémentations doivent rester identiques (tests de part et d'autre sur les mêmes cas).
- Le downgrade de la migration est refusé dès qu'un retour existe.

### Neutres

- Pas de contrepassation d'un retour en v1 : une erreur se corrige hors de l'app.

## Critères qui justifieraient de revisiter cette décision

- Intégration d'une API de paiement (remboursement mobile money automatique) : statuts de remboursement réels.
- Conflits hors ligne fréquents : envisager le mode en ligne obligatoire pour les retours.
- Besoin d'annuler un retour : contrepassation traçable.
