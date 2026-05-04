---
description: Crée un nouvel Architecture Decision Record numéroté
---

# /new-adr

Crée un nouvel ADR dans `docs/adr/` en suivant le template existant.

## Étapes

1. Lister les ADRs existants : `ls docs/adr/0*.md`
2. Identifier le prochain numéro disponible (incrémental, padding sur 4 chiffres)
3. Demander à l'utilisateur :
   - Le titre court de la décision (en kebab-case pour le nom de fichier)
   - Le contexte (problème à résoudre)
   - La décision prise
4. Copier le template `docs/adr/_template.md` vers `docs/adr/<numéro>-<titre>.md`
5. Pré-remplir avec les infos données par l'utilisateur, en gardant les sections "Alternatives considérées", "Conséquences" et "Critères qui justifieraient de revisiter" vides pour que l'utilisateur les complète
6. Mettre à jour la table dans `docs/adr/README.md` avec la nouvelle entrée
7. Indiquer le chemin du fichier créé pour que l'utilisateur puisse le compléter

Le statut initial est "Proposé" — l'utilisateur le passera à "Accepté" quand la décision sera finalisée.
