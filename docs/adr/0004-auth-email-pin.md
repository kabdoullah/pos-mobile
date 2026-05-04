# ADR-0004 : Authentification email + mot de passe + PIN local

## Statut

Accepté — 29 avril 2026

## Contexte

L'authentification est un point d'entrée critique du produit. Elle doit :

- Être **simple et rapide** au quotidien (le commerçant ouvre son app plusieurs fois par jour)
- Permettre la **récupération de compte** en cas d'oubli ou de perte de téléphone
- Être **gratuite** ou très peu coûteuse à opérer (MVP bootstrappé)
- Être **adaptée au contexte ivoirien** : tous les commerçants n'ont pas un email actif, mais beaucoup ont WhatsApp et un numéro de téléphone

L'option initiale (V1.0 du document de specs) était une authentification par OTP SMS sur le numéro de téléphone, calquée sur les apps Mobile Money que les commerçants connaissent. Cette option a été abandonnée pour des raisons de coût et de complexité d'intégration.

## Décision

Authentification en **deux couches complémentaires** :

### Couche 1 — Inscription et récupération : email + mot de passe

- Inscription via `POST /api/v1/auth/register` avec email + mot de passe (≥ 8 caractères) + numéro de téléphone (info, pas de vérif)
- Email de confirmation envoyé via Brevo (offre gratuite, 300 emails/jour)
- Connexion classique via `POST /api/v1/auth/login` qui renvoie un JWT
- Récupération de mot de passe via lien magique envoyé par email

### Couche 2 — Usage quotidien : PIN à 4 chiffres

- Après la première connexion, le commerçant définit un PIN à 4 chiffres
- Le PIN est hashé localement via bcrypt et stocké en `flutter_secure_storage` (Keystore Android)
- Pour rouvrir l'app au quotidien : juste le PIN, pas d'appel réseau, ouverture instantanée
- Après 5 échecs : blocage 5 min puis obligation de reconnexion via email + mot de passe

## Alternatives considérées

### OTP SMS sur numéro de téléphone (option V1.0)

Inscription et reconnexion via code SMS reçu sur le numéro.

**Rejeté.** Avantages : adapté au contexte CI (tout le monde a un numéro, pas tout le monde a un email). Inconvénients :

- **Coût récurrent** : 25-50 FCFA par SMS via les agrégateurs locaux. À 50 commerçants × 10 SMS/mois = 12 500-25 000 FCFA/mois récurrent. Pas tenable au MVP bootstrappé.
- **Intégration complexe** : APIs Orange/MTN nécessitent souvent des contrats commerciaux. Les agrégateurs internationaux comme Twilio facturent en USD avec carte bancaire.
- **Délai d'envoi non garanti** : SMS qui mettent 5+ minutes à arriver = abandon utilisateur.

### WhatsApp OTP via API Meta

Envoyer le code via WhatsApp Business API ou via lien `wa.me`.

**Rejeté.** Risques :

- **Dépendance Meta** : le compte WhatsApp Business peut être suspendu sans préavis (cela arrive régulièrement)
- **WhatsApp Business API** est payante et complexe à intégrer
- **Approche `wa.me`** (lien de message pré-rempli) fonctionne mais demande une opération manuelle au commerçant qui est moins UX qu'un OTP SMS
- Risque de violation des CGU Meta si utilisé pour de l'envoi automatisé

### Magic link uniquement (pas de mot de passe)

Connexion sans mot de passe, juste un lien envoyé par email à chaque session.

**Rejeté.** Avantages : sécurité supérieure à un mot de passe, pas de mot de passe à retenir. Inconvénients :

- **Ne marche pas en hors-ligne** : le commerçant ne peut pas se reconnecter sans réseau
- **Latence** : attendre un email à chaque session est insupportable au quotidien
- **Email pas toujours consulté** : nombreux commerçants n'ouvrent leur email que rarement

### Biométrie (empreinte digitale, Face Unlock)

Connexion par capteur biométrique du téléphone.

**Reporté en Phase 2.** Avantages : très bonne UX. Inconvénients pour le MVP :

- Hétérogénéité du parc Android : tous les téléphones bas de gamme n'ont pas de capteur fiable
- Complexité d'intégration Flutter (`local_auth` package)
- Toujours besoin d'un fallback PIN/password donc on doit l'implémenter de toute façon

À ajouter en Phase 2 comme option par-dessus la couche PIN existante.

### Pas de couche PIN (juste email + password)

Reconnexion à chaque session via email + password.

**Rejeté.** Inconvénients :

- UX médiocre au quotidien : taper un mot de passe long sur smartphone à chaque ouverture est fastidieux
- Pousse les commerçants vers des mots de passe faibles ou auto-complétés (donc moins sécurisés en pratique)
- Les apps Mobile Money locales utilisent toutes un PIN, c'est l'attente UX standard

## Conséquences

### Positives

- **Coût zéro** : Brevo gratuit jusqu'à 300 emails/jour, largement suffisant pour le MVP
- **UX quotidienne excellente** : ouverture en < 2 secondes via PIN
- **Familier** pour les commerçants ivoiriens (calque l'UX des apps Mobile Money)
- **Récupération possible** sans dépendre du téléphone physique : un commerçant qui perd son téléphone se reconnecte sur un nouveau appareil avec son email + mot de passe
- **Pas de dépendance** à un service tiers payant ou risquant la suspension de compte
- **Sécurité raisonnable** : mot de passe bcrypt côté serveur + PIN bcrypt côté client + JWT à courte durée + rate limiting

### Négatives

- **Tous les commerçants n'ont pas d'email actif** : nécessite un onboarding manuel pour les premiers utilisateurs (création d'un Gmail si besoin). Acceptable et même bénéfique en bêta privée car oblige à passer du temps avec eux.
- **PIN à 4 chiffres seulement** : 10 000 combinaisons possibles, donc bruteforçable en théorie. Mitigé par : blocage après 5 essais, hash bcrypt, accès physique au téléphone requis. Suffisant pour des données de POS.
- **Email de récupération peut être perdu** : si le commerçant oublie aussi son mot de passe ET n'a plus accès à son email, il faut un process de récupération manuel par le support. Documenter dans le runbook.

### Neutres

- 300 emails/jour suffisent pour le MVP mais à surveiller. Si on dépasse régulièrement, basculer sur Brevo payant (~5 €/mois pour 5000 emails/jour).

## Critères qui justifieraient de revisiter cette décision

- Volume d'emails > 300/jour récurrent (passer en payant ou changer de provider)
- Nombre de réclamations support sur l'oubli de mot de passe > 5% des utilisateurs (envisager d'ajouter une option SMS payante en Phase 2)
- Régulation locale qui impose une 2FA stricte (peu probable pour un POS)
- Ajout du multi-vendeurs : il faudra repenser l'authentification pour permettre des sous-comptes employés
