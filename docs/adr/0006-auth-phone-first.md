# ADR-0006 : Authentification phone-first + email optionnel pour récupération

## Statut

Accepté — 7 juin 2026. Supersedes ADR-0004.

## Contexte

ADR-0004 imposait l'email comme identifiant principal. Trois mois de terrain ont révélé un problème d'onboarding : une part significative des commerçants cibles (30-50 ans, Côte d'Ivoire) n'ont pas d'email actif ou ne le consultent pas régulièrement. En revanche, tous ont un numéro de téléphone — c'est l'identifiant naturel de Mobile Money (Wave, Orange Money, MTN), le point de référence quotidien.

L'email comme champ requis crée une friction à l'inscription qui peut causer de l'abandon ou forcer un accompagnement manuel systématique en bêta.

Contraintes maintenues :
- **Coût zéro** : MVP bootstrappé, pas de budget pour OTP SMS récurrent
- **Récupération de compte** : un commerçant qui perd son téléphone doit pouvoir récupérer son accès
- **Sécurité raisonnable** : le POS contient des données de vente sensibles

## Décision

### Couche 1 — Inscription et connexion quotidienne : phone + password

- Inscription via `POST /api/v1/auth/register` avec :
  - `phone_number` (requis, unique, format E.164 validé)
  - `password` (requis, ≥ 8 caractères)
  - `email` (optionnel, pour récupération de compte uniquement)
- Connexion via `POST /api/v1/auth/login` avec `phone_number` + `password`
- Pas de vérification de numéro par SMS en V1 (voir section "Alternatives")
- Unicité du numéro : first-come-first-served. Conflit → résolution manuelle support.

### Couche 2 — Usage quotidien : PIN à 4 chiffres (inchangé)

Identique à ADR-0004 : PIN hashé localement, stocké en `flutter_secure_storage`, 5 tentatives max.

### Récupération de compte

- Si `email` fourni à l'inscription : réinitialisation via lien envoyé par Brevo (inchangé).
- Si pas d'email : réinitialisation impossible en self-service → contact support documenté dans le runbook.
- L'email peut être ajouté après coup via `PUT /api/v1/auth/me` (hors scope V1, à prévoir en V1.5).

## Alternatives considérées

### Email requis comme identifiant (ADR-0004)

**Rejeté.** Friction onboarding pour les commerçants sans email actif. Coût d'accompagnement manuel en bêta trop élevé. La valeur de l'email comme identifiant primaire ne justifie pas la friction.

### OTP SMS sur numéro de téléphone (déjà dans ADR-0004)

**Rejeté.** Coût récurrent (25-50 FCFA/SMS), intégration complexe avec agrégateurs CI, délais non garantis. Voir ADR-0004 pour détail complet.

### WhatsApp OTP via API Meta

**Rejeté.** Meta approval process (2-4 semaines), pricing conversation-based, risque de suspension de compte. Discuté et acté le 7 juin 2026.

### Phone obligatoire + SMS verification dès V1

**Reporté en V2** (condition sine qua non avant lancement public). En bêta privée (<50 commerçants), le risque d'usurpation de numéro est théorique : pas d'incitation financière à voler un compte POS vide, surface d'attaque fermée.

## Conséquences

### Positives

- Onboarding aligné avec les habitudes de la cible (numéro = identifiant naturel)
- Moins d'abandon à l'inscription
- Coût zéro maintenu (email Brevo gratuit pour la récupération)
- Compatible avec l'ajout de SMS verification en V2 sans casser le schéma

### Négatives

- Commerçant sans email = pas de self-service recovery → process support manuel documenté
- Sans SMS verify : usurpation théoriquement possible (faible risque en bêta privée)
- `phone_number` devient une donnée critique d'identité — rotation du numéro = blocage temporaire compte

### Neutres

- SMS verification = dette technique assumée. À implémenter avant tout lancement public ou passage à 50+ merchants.
- `email` reste en DB comme colonne nullable — aucune migration destructive lors de l'ajout de SMS verify plus tard.

## Critères qui justifieraient de revisiter cette décision

- Lancement public (>50 merchants) : SMS verification devient obligatoire, traiter comme bloquant
- Première plainte d'usurpation de numéro en bêta → accélérer SMS verify
- Si Wave ou Orange CI expose une API d'authentification phone (moins probable) : envisager OAuth social
- Ajout multi-vendeurs/employés : revoir l'ensemble du modèle d'authentification
