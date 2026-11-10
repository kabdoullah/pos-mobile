# ADR-0015 : Sessions de caisse par appareil

## Statut

Accepté — 10 novembre 2026

## Contexte

Le commerçant doit savoir à tout moment combien d'espèces devraient se trouver dans son tiroir, compter en fin de session ce qui s'y trouve réellement, et garder une trace fiable de l'écart.

Contraintes :

- **hors ligne d'abord** : ventes, retours et mouvements de caisse sont enregistrés sans réseau puis synchronisés (UUID client, idempotence, ADR-0003) ;
- **plusieurs appareils** par boutique : chaque téléphone a son propre tiroir ;
- **un seul utilisateur par boutique** (`stores.owner_id` unique) : pas de rôles ni de comptes caissiers ;
- **ventes et retours existants** : le calcul s'appuie dessus sans les réimplémenter, et sans réécrire leurs parcours ;
- **un remboursement est confirmé au comptoir** (ADR-0010) : un retour `refund_method = cash` correspond à des espèces réellement sorties ;
- **montants exacts** (ADR-0009) : `NUMERIC(12,2)`, `Decimal`, chaîne dans le JSON.

Anti-objectifs : un paiement mobile money compté dans le tiroir ; une opération comptée deux fois après un retry ; une clôture modifiée après coup sans que le commerçant le voie ; un parcours de vente ou de retour réécrit.

## Décision

### Décisions validées par le commerçant

- **D1. Une session ouverte par téléphone.** Chaque appareil est un tiroir, identifié par un `device_id`. Un index unique partiel `(store_id, device_id) WHERE status = 'open'` garantit l'unicité, y compris face à des requêtes concurrentes.
- **D2. Pas de vente sans caisse dans l'app.** Encaisser exige une session ouverte. Le serveur accepte toujours les ventes sans session (anciennes versions de l'app).
- **D3. Sortie supérieure au solde refusée**, par l'app et par le serveur (`INSUFFICIENT_CASH`).
- **D4. Opération arrivée après la clôture : rattachée à sa session d'origine et signalée.** La clôture reste figée ; l'impact apparaît séparément.

### Choix de conception à relire

- **C1. Montant d'ouverture** stocké sur la session (`opening_amount`), pas comme mouvement, pour ne pas dupliquer l'information.
- **C2. Pas de `reference_id` sur les mouvements.** L'UUID client du mouvement est sa référence. Ventes et retours portent eux-mêmes `cash_session_id` au lieu d'être recopiés en mouvements.
- **C3. Remboursement espèces supérieur au solde : non bloqué.** Le parcours de retour reste inchangé ; le solde peut devenir négatif et l'app avertit. D3 ne s'applique qu'aux sorties manuelles.
- **C4. Retour rejeté par le serveur** : il n'existe pas côté serveur, donc il n'est pas compté dans le solde serveur. L'app affiche « Retour refusé : X FCFA rendus non comptés », ce qui explique le déficit (cohérent avec la régularisation manuelle de l'ADR-0010).
- **C5. Impact après clôture calculé à la lecture** (recalcul actuel − `expected_amount` figé), jamais écrit dans la session clôturée.
- **C6. Remboursement en espèces sans caisse ouverte** : l'app demande d'ouvrir la caisse, comme pour une vente. Un remboursement mobile money n'en a pas besoin.

### Solde théorique

```
solde = opening_amount
      + Σ part espèces des ventes de la session
      + Σ entrées − Σ sorties
      − Σ refund_amount des retours de la session en espèces
```

Part espèces d'une vente : `total_amount` si `cash`, `cash_amount` si `mixed`, 0 si mobile money. Écart : `counted_amount − expected_amount`.

### Modèle et règles

- Nouveau module `cash_register` : tables `cash_sessions` (tenant, RLS, clôture figée par trigger) et `cash_movements` (tenant, RLS, immuable). Colonnes `cash_session_id` ajoutées à `sales` et `sale_returns`, posées à l'INSERT.
- Cycle de vie `open → closed`, sans retour. Une session clôturée n'est jamais rouverte ni modifiée.
- Une vente ou un retour est rattaché à la session ouverte de l'appareil qui encaisse ou rembourse ; le serveur ne réattribue jamais une opération.
- **Le serveur fait foi** : à la clôture, `expected_amount` est recalculé en base sous verrou (`FOR UPDATE`) ; la valeur de l'app (`client_expected_amount`) n'est conservée que pour traçabilité.
- Vente ou retour tardif : toujours accepté (l'argent a bougé). Mouvement postérieur à `closed_at` : refusé (`CASH_SESSION_CLOSED`). Session inconnue lors de la synchronisation d'une vente ou d'un retour : `failed`, donc réessayable.
- Codes d'erreur : `CASH_SESSION_ALREADY_OPEN` (409), `CASH_SESSION_CLOSED` (409), `INSUFFICIENT_CASH` (422), `IDEMPOTENCY_CONFLICT` (409).
- Découplage : `cash_register.service` lit les totaux via `SaleService` et `ReturnService`, jamais leurs repositories ; la validation de session pendant la synchronisation passe par `SyncService`.

## Alternatives considérées

### Une session par boutique

Un seul tiroir partagé par tous les appareils. Rejetée : chaque téléphone a en pratique son tiroir, et le comptage de fin de session serait impossible à attribuer. Elle forcerait aussi une coordination entre appareils hors ligne.

### Ventes autorisées hors session

Laisser vendre sans caisse ouverte. Rejetée : le solde théorique serait faux sans que le commerçant le sache. L'app exige une session (D2) ; seul le serveur reste tolérant pour les anciennes versions.

### Réattribution à la session ouverte

Rattacher une opération tardive à la session actuellement ouverte. Rejetée : cela fausserait deux sessions à la fois et modifierait le sens de l'historique. L'opération reste dans sa session d'origine et son impact est signalé (D4).

### Montant d'ouverture comme mouvement

Rejetée (C1) : duplique l'information et complique le calcul de l'historique.

## Conséquences

### Positives

- Solde théorique fiable, calculé par le serveur et vérifiable.
- Écart tracé et clôture figée (trigger), visible en cas d'opération tardive.
- Aucune réécriture des parcours de vente et de retour.
- Idempotence de bout en bout (UUID client).

### Négatives

- Le calcul du solde est dupliqué (Python et Dart) : les deux implémentations doivent rester identiques, avec les mêmes cas de test.
- Un retour rejeté par le serveur après remboursement en espèces crée un déficit qu'il faut expliquer (C4).
- Un remboursement espèces peut rendre le solde négatif (C3).
- Le downgrade de la migration est refusé dès qu'une session existe.

### Neutres

- Les ventes antérieures à la fonctionnalité n'appartiennent à aucune session.

## Critères qui justifieraient de revisiter cette décision

- Apparition de rôles ou de comptes caissiers multiples.
- Besoin de clôturer à distance une session restée ouverte sur un appareil perdu ou réinstallé (hors périmètre v1).
- Besoin de contrepasser un mouvement ou d'imprimer un ticket de clôture.
- Écarts fréquents dus à des opérations tardives : revoir la règle D4.
