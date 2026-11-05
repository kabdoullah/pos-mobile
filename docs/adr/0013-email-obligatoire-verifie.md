# ADR-0013 : Email obligatoire et vérifié pour la récupération du compte

## Statut

Proposé — 5 novembre 2026. Supersedes ADR-0006 (partie « email optionnel » et « Récupération de compte » ; le login phone + password et le PIN local restent inchangés).

## Contexte

ADR-0006 a rendu l'email optionnel pour réduire la friction à l'inscription. La réinitialisation du mot de passe passe pourtant uniquement par un lien envoyé par email (Brevo). Il n'y a pas d'OTP SMS, à cause de la contrainte de coût zéro.

Conséquences observées :

- **Pas de self-service** : un compte sans email ne peut pas récupérer son accès. Chaque oubli de mot de passe passe par le support, et le support ne peut pas vérifier l'identité de façon fiable.
- **Email jamais vérifié** : le mail de vérification était envoyé, mais aucun endpoint ne consommait son token, donc `email_verified_at` n'était jamais renseigné.
- **Squat d'adresse** : n'importe qui pouvait s'inscrire avec l'email d'autrui. Il recevait alors les liens de réinitialisation de cette adresse et empêchait son propriétaire de l'utiliser pour s'inscrire.

## Décision

### Inscription : email obligatoire

- Dans `POST /api/v1/auth/register`, `email` devient requis, en plus de `phone_number` et `password`. Sans email, la réponse est une 422 avec `field=email`.
- `users.email` reste nullable en base : les comptes créés sous ADR-0006 sans email restent valides. Il n'y a pas de migration.
- Le login reste phone + password, et le PIN local reste inchangé (ADR-0006).

### Vérification de l'adresse

- Un token de 24h, à usage unique et stocké hashé en SHA-256, est envoyé par email à l'inscription.
- Le lien du mail est `{APP_FRONTEND_URL}/auth/verify-email#token=…`. Le token est dans le fragment, donc absent des logs d'accès.
- `GET /auth/verify-email` sert une page de confirmation. Le token est envoyé à `POST /api/v1/auth/verify-email` seulement au clic, pour que les scanners de liens des messageries ne valident pas l'adresse à la place de son propriétaire.
- `POST /api/v1/auth/resend-verification` (connecté, 3 par heure) invalide les anciens liens et en renvoie un nouveau. L'app le propose dans Paramètres → Compte, d'après `email_verified_at` exposé par `GET /api/v1/users/me`.

### Réinitialisation du mot de passe : seulement vers une adresse vérifiée

- `forgot-password` n'envoie le lien que si `email_verified_at` est renseigné. Sinon, la réponse reste un 204 silencieux, pour ne révéler ni l'existence du compte ni son état de vérification.

## Alternatives considérées

### OTP SMS pour la récupération (ou la vérification du numéro)

C'est le canal naturel pour des commerçants « phone-first » (ADR-0006). Rejeté : le coût est récurrent à chaque envoi, ce qui est incompatible avec la contrainte de coût zéro. Il faudrait aussi un fournisseur SMS, plus une protection anti-fraude contre le pompage de SMS.

### Garder l'email optionnel et ne vérifier que ceux fournis

Ça préserve l'inscription sans friction d'ADR-0006. Rejeté : les comptes sans email restent sans aucune récupération en self-service, et c'est précisément le problème à résoudre.

### Unicité seulement sur les emails vérifiés, ou reprise d'un email non vérifié après 24h

Ça empêcherait complètement le blocage d'une adresse par un squatteur. Reporté : il faut remplacer l'index unique `users.email` par un index partiel, avec une migration, et gérer deux comptes portant la même adresse non vérifiée. Le risque principal, recevoir les liens de reset d'autrui, est déjà neutralisé par le reset réservé aux adresses vérifiées.

### Valider l'email directement à l'ouverture du lien (GET)

C'est plus simple : pas de page ni de bouton. Rejeté : les scanners de liens des messageries (antivirus, aperçus) ouvrent les URL. Ils confirmeraient l'adresse sans action humaine, ce qui annule l'intérêt de la vérification.

### Vérification dans l'app via App Link (comme le reset)

Rejeté pour l'instant : le lien doit aussi fonctionner depuis un PC ou un autre téléphone que celui de la caisse. Une page web suffit, puisqu'il n'y a rien à saisir.

## Conséquences

### Positives

- Chaque nouveau compte peut réinitialiser son mot de passe seul, sans passer par le support.
- Un tiers qui s'inscrit avec l'email d'autrui ne reçoit jamais de lien de réinitialisation pour cette adresse.
- La vérification d'email, envoyée depuis le début mais inutilisable, fonctionne enfin.
- Les tokens ne passent ni dans les logs d'accès (fragment `#`) ni dans l'en-tête Referer (`no-referrer`).

### Négatives

- **Comptes existants** : aucun n'est vérifié au déploiement. Ils ne peuvent plus réinitialiser leur mot de passe avant d'avoir confirmé leur email depuis Paramètres → Compte. Le backend et la version mobile doivent être publiés ensemble.
- **Friction à l'inscription** : les commerçants sans email actif, cas identifié par ADR-0006, doivent en créer un ou se faire accompagner, avec un risque d'abandon.
- **Anciens comptes sans email** : ils n'ont toujours aucune récupération en self-service, et aucun endpoint ne permet d'ajouter un email.
- **Squat d'adresse** : il reste possible de bloquer l'inscription d'une adresse sans la posséder. Résolution manuelle par le support.
- **Ancienne app** : elle envoie une inscription sans email et reçoit une 422 tant qu'elle n'est pas mise à jour.

### Neutres

- `users.email` reste nullable en base : la contrainte « obligatoire » ne vit que dans le schéma d'inscription.
- Le seed superadmin est ignoré, avec un warning, si `SUPERADMIN_EMAIL` est vide.
- Le message de conflit « Cet email est déjà enregistré » révèle l'existence d'un compte, comme le message équivalent pour le téléphone.

## Critères qui justifieraient de revisiter cette décision

- **Abandon à l'inscription** : l'étape email fait chuter les inscriptions de façon mesurable, ou le support reçoit souvent des commerçants sans email. Il faudrait alors rouvrir l'option OTP SMS ou un email facultatif avec récupération alternative.
- **Squat signalé** : des cas réels arrivent au support. Il faudrait alors passer à l'unicité limitée aux emails vérifiés (index partiel et migration).
- **Budget SMS disponible** : un fournisseur à coût acceptable (ou gratuit, type WhatsApp OTP) rendrait l'OTP téléphone préférable pour une base phone-first.
- **Peu de comptes vérifiés** : beaucoup de comptes existants n'ont toujours pas vérifié leur email plusieurs semaines après le déploiement. Il faudrait alors une relance in-app plus visible (bannière à l'accueil) ou un renvoi en masse.
- **Changement d'email** : si l'ajout ou la modification de l'email depuis l'app est développé, le changement doit repasser par la vérification, et cet ADR sera à compléter.
