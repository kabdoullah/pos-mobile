# ADR-0011 : Suppression de compte depuis l'app et purge de la boutique

## Statut

Accepté — 17 octobre 2026

## Contexte

L'App Store (règle 5.1.1(v)) exige qu'un compte créé dans l'app puisse être supprimé **depuis l'app**. Jusqu'ici, seule une page web demandait d'écrire un e-mail (suffisant pour le Play Store, refusé par Apple).

La politique de confidentialité et la page de suppression promettent déjà l'effacement définitif du compte, de la boutique, du catalogue et de l'historique des ventes.

Contraintes :

- `sales`, `sale_returns`, `sale_return_items` et `stock_movements` sont **immuables** par trigger (ADR-0003, ADR-0007, ADR-0010) ;
- les tables tenant référencent `stores` en `RESTRICT`, et `stores.owner_id` référence `users` en `RESTRICT` ;
- RLS (ADR-0002) : une session ne voit que la boutique de `app.current_store_id`.

## Décision

- Endpoint `DELETE /api/v1/users/me`, corps `{ "password": "…" }`. Le mot de passe est revérifié ; s'il est faux : **403** (pas 401, qui déclencherait le rafraîchissement du token côté app). Réponse 204.
- Suppression **définitive** et immédiate : boutique et toutes ses données (images et logo compris), puis l'utilisateur. Aucune anonymisation, aucune période de grâce.
- Fonction SQL `purge_store(p_store_id)` (SECURITY INVOKER, donc soumise à RLS) : pose `app.purging_store_id` pour la transaction puis supprime les tables dans l'ordre des clés étrangères.
- Les fonctions d'immuabilité laissent passer **uniquement** un `DELETE` dont la ligne appartient à la boutique en cours de purge (`OLD.store_id = app.purging_store_id`). `UPDATE` reste toujours interdit, et un `DELETE` hors purge lève toujours l'exception.
- Côté app : entrée « Supprimer mon compte » dans les Réglages, confirmation puis mot de passe, en ligne uniquement. Après succès, l'app efface toutes les données locales (base, file de sync, jetons, PIN, cache d'images) et revient à la connexion.

## Alternatives considérées

### Anonymiser et conserver les ventes

Garder les ventes sans donnée identifiante. Rejetée : contredit la page publiée et la politique de confidentialité, et la conservation comptable incombe au commerçant, pas à l'éditeur.

### `session_replication_role = replica` ou `ALTER TABLE … DISABLE TRIGGER`

Désactive tous les triggers. Rejetée : exige un superutilisateur ou le propriétaire des tables, pose un verrou exclusif sur toute la table (toutes les boutiques), et ne limite pas la portée à une boutique.

### Désactivation (soft delete) du compte

Rejetée : ne satisfait ni Apple ni la promesse d'effacement.

## Conséquences

### Positives

- Conforme App Store et Play Store avec un seul parcours.
- L'immuabilité reste garantie en fonctionnement normal ; l'exception est limitée à une boutique et à une transaction.

### Négatives

- Irréversible : une erreur de manipulation efface tout (atténué par la confirmation et le mot de passe).
- Les ventes non synchronisées de l'appareil sont perdues.

### Neutres

- Un access token encore valide après la suppression ne voit plus aucune donnée ; le rafraîchissement échoue (utilisateur introuvable).

## Critères qui justifieraient de revisiter cette décision

- Plusieurs utilisateurs par boutique (supprimer un employé ne doit pas purger la boutique).
- Obligation légale de conservation à la charge de l'éditeur.
