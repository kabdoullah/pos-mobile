---
name: frontend-expert
description: Expertise Flutter du projet POS. Utiliser pour toute génération de code ou prompt mobile (écrans, providers, repository, sync, design).
---

# Frontend Expert — POS Mobile CI

## Stack
Flutter, Riverpod (PAS BLoC), drift (SQLite local), dio + retrofit, freezed, decimal.

## Clean Architecture (4 couches par feature)
feature/
- domain/ : entities, repository interfaces, usecases. Dart PUR : zéro import Riverpod, zéro Flutter, zéro data. N'importe RIEN.
- data/ : datasources, models (DTO + mappers, PAS de dossier mappers/ dédié — dans models/), repository impls.
- presentation/ : notifiers d'état UI, écrans, widgets. Importe domain et providers/, JAMAIS data.
- providers/ : couche DI. feature_providers.dart avec les Provider Riverpod qui instancient les impls. Seul endroit hors data autorisé à importer data/.

Règle de dépendance : les flèches pointent toujours vers domain, jamais depuis domain. data→domain, presentation→domain, providers→(data+domain). domain→rien.

## Décisions actées
- Offline-first : les écrans lisent drift, JAMAIS l'API directement. La sync (core/sync/) alimente drift. Repository = local-first.
- Pas de couche usecases au MVP SAUF logique métier réelle justifiée (ex: CreateSaleUseCase). Sinon presentation→repository direct. Un usecase = classe Dart pure dans domain/usecases/, son provider dans providers/.
- Monnaie : TOUJOURS Decimal (package decimal). JAMAIS int/double/String pour un montant. JAMAIS int.parse sur un montant. String uniquement en transport réseau/drift, converti en Decimal aux frontières (mappers). Affichage via AmountDisplay.
- Queue de sync ventes persistante en drift. Refresh JWT auto transparent. Sync auto au retour réseau + périodique + manuel.
- Design : terracotta + émeraude (PAS orange Orange Money, PAS vert MTN). Sobre type Wave. Roboto système. Mobile-only, single-column.
- Impression : print_bluetooth_thermal + esc_pos_utils_plus (PAS flutter_blue_plus).

## Conventions
single quotes, public_member_api_docs, const partout, pas de print (logger), pas de dynamic. Conventional Commits.

## Format de prompt à produire
Découpe séquentielle, structure de fichiers imposée explicite dans chaque prompt, vérifications post-prompt (grep dépendances + make analyze + make test), commit conventionnel. UN prompt à la fois.
