# ADR-0014 : Lien de réinitialisation du mot de passe généré par le support

## Statut

Proposé — 5 novembre 2026. Complète ADR-0012 (fin de « aucune action sur les comptes utilisateurs ») et ADR-0013 (récupération des comptes sans email vérifié).

## Contexte

Depuis ADR-0013, `forgot-password` n'envoie un lien qu'à une adresse **vérifiée**. Un commerçant qui a oublié son mot de passe et dont l'email est absent, mal saisi ou jamais confirmé est bloqué :

- il ne peut pas se connecter (phone + mot de passe) ;
- `resend-verification` et `PUT /users/me/email` exigent d'être connecté ;
- le backoffice (ADR-0012) est en lecture seule sur les comptes : le support ne peut rien faire.

Pas d'OTP SMS (contrainte de coût zéro, ADR-0013).

## Décision

- **Endpoint** `POST /api/v1/admin/users/{user_id}/password-reset-link`, corps `{"reason": "..."}` (3 à 500 caractères, obligatoire : comment l'identité a été vérifiée). Réponse `200 {"link", "expires_at"}` avec `Cache-Control: no-store`.
- **Même jeton que `forgot-password`** : `password_reset_tokens`, 1h, usage unique, stocké hashé SHA-256. Même lien `{APP_FRONTEND_URL}/auth/reset-password#token=…` (App Link mobile ou page de secours), consommé par `POST /auth/reset-password`. Rien à changer côté app.
- **Aucune condition sur l'email** : le lien marche que l'email soit vérifié, faux ou absent. C'est le but.
- **Le support transmet le lien lui-même** (WhatsApp ou SMS), **uniquement au numéro du compte** et après vérification d'identité (procédure humaine, hors code). Le lien n'est affiché qu'une fois et n'est jamais journalisé.
- **Compte désactivé** (`is_active = false`) : 409, le lien ne servirait à rien (le login le refuse).
- **Journal d'audit** : action `user_password_reset_link`, avec la raison, l'utilisateur ciblé (`user_id`, `user_phone` copié) et sa boutique éventuelle (`store_id`, `store_name`), pour apparaître dans la fiche boutique. Migration `c4e8a2d6f1b3` : colonnes `user_id` (sans clé étrangère, l'entrée survit à la suppression du compte, ADR-0011) et `user_phone`, contrainte `chk_admin_audit_log_action` élargie, trigger d'immuabilité mis à jour.

## Alternatives considérées

### Envoyer le lien à l'email enregistré, même non vérifié

L'admin ne voit jamais le jeton. Rejetée : inutile quand l'email est faux ou absent, c'est-à-dire la majorité des cas bloqués.

### L'admin corrige l'email et le marque vérifié

Le commerçant repasse ensuite par `forgot-password`. Rejetée : saisie manuelle sujette aux fautes, et même pouvoir de prise de compte pour un admin compromis (il suffit de mettre sa propre adresse).

### OTP SMS

Rejetée pour la même raison qu'ADR-0013 : coût récurrent.

## Conséquences

### Positives

- Plus aucun compte actif n'est irrécupérable : le support débloque en une minute.
- Aucune modification mobile, ni nouveau type de jeton.
- Chaque lien généré est tracé (qui, quand, pour quel compte, pourquoi).

### Négatives

- **Un admin compromis peut prendre la main sur n'importe quel compte commerçant.** Le risque existait en partie (lecture cross-tenant) ; il devient une écriture. Atténuations : jeton admin court (2h) sans refresh, verrouillage après 5 échecs, journal immuable. MFA admin à envisager (critère de révision d'ADR-0012).
- La sécurité dépend de la vérification d'identité faite par téléphone par le support (ingénierie sociale possible). Règle : n'envoyer le lien qu'au numéro du compte, jamais à un autre.
- Le lien transite par une messagerie tierce (WhatsApp) : il expire en 1h et ne sert qu'une fois.

### Neutres

- Générer un lien n'invalide pas les liens précédents encore valides (même comportement que `forgot-password`).

## Critères qui justifieraient de revisiter cette décision

- Plusieurs admins ou un support externalisé : rôles distincts, seul un rôle habilité génère des liens.
- Volume élevé de demandes au support : signal que la vérification d'email (ADR-0013) ne prend pas, ou qu'un OTP devient rentable.
- Un abus constaté dans le journal.
