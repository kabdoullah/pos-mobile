# Idées de skills à créer plus tard

> Fichier de capture libre. Note ici toute idée de skill qui te traverse l'esprit pendant le développement, sans te poser de questions. Tu trieras plus tard.

## Comment utiliser ce fichier

À chaque fois que tu te dis pendant le développement :

- "J'aimerais bien avoir un référentiel propre sur X..."
- "Je galère à chaque fois que je touche à Y..."
- "Je viens de découvrir un piège que je n'aurais pas dû reproduire..."
- "Cette procédure, je la refais pour la 3e fois..."

→ Ajoute une ligne ici. Pas besoin que ce soit bien rédigé. Juste un titre et 2-3 lignes de contexte.

Quand tu en as 5-6 et que certaines reviennent souvent dans ton travail, créées les skills correspondantes.

## Format suggéré

```
### Titre court
- Pourquoi : (le problème rencontré)
- Quand : (dans quel contexte ça se manifeste)
- Statut : idée | brouillon | à créer | créée
```

---

## Idées en attente

### receipt-template (ESC/POS + conformité DGI)
- Pourquoi : la première fois qu'on touche aux commandes ESC/POS et au format DGI, on perd 1-2 jours
- Quand : pendant l'implémentation de l'epic E4 (impression du reçu)
- Statut : idée — à créer si problèmes rencontrés
- Notes : voir aussi US-25 (conformité DGI), valider format avec un expert-comptable ivoirien avant production

### rls-testing (patterns de test multi-tenant)
- Pourquoi : les politiques RLS sont critiques mais leur test est subtil (oubli du SET LOCAL, leak de transaction, etc.)
- Quand : pendant la première implémentation d'une table tenant + ses tests
- Statut : idée — à créer après le 2e ou 3e test RLS écrit, pour capturer les patterns réellement utilisés

### mobile-money-receipt
- Pourquoi : format des références Wave/Orange/MTN, validation numéros +225, format FCFA standard
- Quand : pendant l'epic E3 (encaissement)
- Statut : idée

### bluetooth-printer-debug
- Pourquoi : les imprimantes BT sont une source de bugs en production qui se découvrent sur le terrain
- Quand : APRÈS avoir eu les premiers bugs réels en bêta
- Statut : idée — ne pas créer avant d'avoir des cas concrets

---

## Idées rejetées (avec raison)

> Garde ici les idées que tu as eu mais que tu as décidé de ne pas créer, avec la raison. Évite de revenir 3 mois plus tard avec la même idée.

(vide pour l'instant)
