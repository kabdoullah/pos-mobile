---
description: Implémente un service backend complet avec tests, suivant les conventions du projet
---

# /implement-service

Implémente un service backend complet avec tests, en suivant la structure modulaire du projet.

## Étapes

1. Demander à l'utilisateur :
   - Le nom du service (ex: EmailService, NotificationService)
   - L'emplacement : core/ (transverse) ou modules/<feature>/ (métier)
   - Les opérations principales (3-5 méthodes max au MVP)
   - Les dépendances externes (SMTP, API, etc.)

2. Lire le contexte :
   - app/core/config.py pour les settings disponibles
   - app/core/exceptions.py pour les types d'exceptions
   - .claude/rules/backend-conventions.md pour les conventions

3. Présenter un plan détaillé avec :
   - Les fichiers à créer
   - Les fichiers à modifier
   - Les dépendances Python supplémentaires (si besoin)
   - Les tests à écrire

4. Après validation :
   - Implémenter le service avec async/await
   - Créer les tests unitaires (mocker les dépendances externes)
   - Mettre à jour les TODOs dans les services consommateurs
   - Lancer make format && make lint && make test

5. Rapporter à l'utilisateur :
   - Les fichiers créés/modifiés
   - Le résultat des tests
   - Les TODOs restants éventuels