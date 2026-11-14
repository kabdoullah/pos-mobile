# ADR-0016 : Billetterie de caisse (comptage par coupure)

## Statut

Accepté — 14 novembre 2026. Complète l'ADR-0015 (sessions de caisse), sans le remplacer.

## Contexte

À l'ouverture et à la clôture, le commerçant compte son tiroir. Saisir seulement un total ne laisse aucune trace de ce qui a été compté et favorise les erreurs de calcul mental. On veut compter billet par billet, pièce par pièce, et garder ce détail pour l'audit.

Contraintes : hors ligne d'abord (ADR-0003), le serveur fait foi (ADR-0015), montants exacts (ADR-0009), compatibilité avec les versions de l'app déjà installées.

## Décision

- **Coupures** : gamme BCEAO, définie une fois côté serveur (`DENOMINATIONS`, `cash_register/schemas.py`) et une fois côté app (`fcfaDenominations`). Billets 10 000, 5 000, 2 000, 1 000, 500 ; pièces 500, 250, 200, 100, 50, 25, 10, 5. 500 existe en billet et en pièce : la coupure est identifiée par (type, valeur). Ajouter une coupure : serveur d'abord, app ensuite.
- **Deux modes, choisis sur l'appareil et mémorisés** : « Billets et pièces » (le montant est la somme du comptage) ou « Total seulement » (parcours de l'ADR-0015, sans détail). Le comptage est donc **facultatif** dans l'API : `opening_count` / `closing_count` absents = mode total, ou ancienne version de l'app.
- **Stockage** : table tenant immuable `cash_count_lines` (une ligne par coupure et par opération `opening` / `closing`, quantités nulles comprises : elles prouvent que la coupure a été comptée). `subtotal = denomination × quantity` imposé par CHECK. Le total du comptage reste le montant de la session (`opening_amount`, `counted_amount`) : pas de colonne en double.
- **Le serveur recalcule** : il ne reçoit que (type, coupure, quantité), calcule les sous-totaux et refuse (`VALIDATION_ERROR`, champ `opening_count` / `closing_count`) un comptage dont la somme diffère du montant envoyé, une coupure inconnue ou en double, une quantité négative, décimale ou supérieure à 100 000.
- **Atomicité** : les lignes d'ouverture sont insérées dans le même savepoint que la session ; les lignes de clôture juste avant l'UPDATE de clôture, dans la même transaction. Une clôture refusée n'écrit rien. Un trigger refuse toute ligne ajoutée à une session déjà clôturée.
- **Idempotence** : le comptage fait partie du contenu comparé lors d'un retry. Même montant mais répartition différente : `IDEMPOTENCY_CONFLICT` (ouverture) ou `CASH_SESSION_CLOSED` (clôture).
- **Clôture « à l'aveugle »** dans l'app : le solde théorique n'est montré qu'après le comptage, au récapitulatif. Le solde théorique n'est jamais ajusté au comptage.
- **Lecture** : `CashSessionDetailResponse` expose `opening_count` et `closing_count` (lignes, total billets, total pièces, total), null sans billetterie.

## Alternatives considérées

### Détail en JSON sur la session

Une colonne `opening_count JSONB`. Rejetée : pas de contrainte par ligne (sous-total, quantité ≥ 0, unicité), et une session ouverte reste modifiable alors qu'un comptage validé doit être figé.

### Le serveur dérive le montant du comptage

Supprimer `opening_amount` / `counted_amount` des requêtes quand un comptage est envoyé. Rejetée : casse l'idempotence existante et les anciennes versions ; garder le montant et le vérifier coûte une comparaison.

### Coupures configurables par boutique

Rejetée pour l'instant : toutes les boutiques utilisent le franc CFA BCEAO. Une liste unique suffit et reste modifiable en un endroit par côté.

## Conséquences

### Positives

- Détail de comptage auditable, immuable, isolé par boutique (RLS) et purgé avec le compte (ADR-0011).
- Aucune rupture : anciennes versions et mode « Total seulement » inchangés.

### Négatives

- Deux listes de coupures à garder identiques (un test backend fige la liste).
- Les sessions en mode « Total seulement » n'ont pas de détail.
