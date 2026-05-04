# ADR-0006 : Hébergement VPS Hetzner avec Docker Compose

## Statut

Accepté — 29 avril 2026

## Contexte

Le backend doit être hébergé quelque part de manière fiable et économique. Les contraintes :

- **Budget infrastructure < 10 €/mois** au MVP
- **Disponibilité raisonnable** : ~99% uptime acceptable au MVP, l'app fonctionne offline donc une heure de downtime serveur n'est pas catastrophique
- **Latence acceptable** depuis la Côte d'Ivoire (la majorité des utilisateurs)
- **Backups robustes** et procédure de restauration testée
- **Pas de devops dédié** : un développeur solo doit pouvoir tout opérer

## Décision

Hébergement sur un **VPS Hetzner Cloud CPX11** (Allemagne ou Finlande) à 4,15 €/mois (2 vCPU, 2 Go RAM, 40 Go SSD), avec :

- **Ubuntu 24.04 LTS** comme système
- **Docker Compose** pour orchestrer les 3 services (Caddy, FastAPI, PostgreSQL)
- **Caddy** comme reverse proxy avec TLS automatique via Let's Encrypt
- **Backups quotidiens** chiffrés vers Backblaze B2 (~5 USD/mois)
- **UptimeRobot** gratuit pour le monitoring de disponibilité

Coût total : **~10 €/mois** pour l'infrastructure complète.

## Alternatives considérées

### Cloud providers majeurs (AWS, GCP, Azure)

**Rejeté pour le MVP.** Avantages : services managés, scaling auto, écosystème énorme. Inconvénients :

- **Coût** : un setup équivalent (EC2 + RDS + ALB + S3) coûterait 50-100 USD/mois minimum
- **Complexité opérationnelle** : nombreux services, IAM, VPC, etc. Trop pour un solo dev
- **Lock-in** : difficile de migrer plus tard
- À reconsidérer en Phase 2 ou 3 si le projet grossit suffisamment pour justifier les services managés

### Cloud providers africains (Cloud Africa, Vodacom Cloud, Orange Business)

**Rejeté pour le MVP.** Avantages potentiels : latence proche, présence locale. Inconvénients :

- Tarifs souvent supérieurs à Hetzner
- Maturité opérationnelle inégale (uptime, support technique)
- Documentation et tooling moins fournis que les géants
- Pas de procédure standard pour Docker Compose ou serveurs Linux génériques

À reconsidérer quand le projet aura suffisamment d'utilisateurs locaux pour que la latence devienne un vrai sujet (~500+ commerçants).

### OVHcloud (France)

**Considéré, raisonnablement comparable.** OVH offre des VPS à ~5 €/mois avec des caractéristiques similaires. Pourquoi Hetzner :

- Réputation Hetzner légèrement meilleure sur la fiabilité (moins de pannes documentées)
- Meilleure UX du panel Hetzner Cloud
- Tarification plus prévisible (pas de coûts cachés)

OVH reste un choix défendable. Si Hetzner pose problème, OVH est l'alternative directe.

### Scaleway (France)

**Considéré, raisonnable.** Tarifs comparables, présence française. Limitations historiques de fiabilité (pannes plus fréquentes que les concurrents) qui ont fait pencher pour Hetzner.

### PaaS managé (Render, Fly.io, Railway)

**Rejeté.** Avantages : zéro setup, déploiement par git push, certificats automatiques. Inconvénients :

- **Coût** plus élevé pour la même configuration (~20-30 USD/mois minimum)
- **Limitations** sur la configuration du système (pas de PostgreSQL avec extensions custom comme `pg_trgm`, pas de cron jobs natifs)
- **Lock-in** : on dépend de l'API du provider
- À reconsidérer si on veut éliminer complètement la charge ops

### Kubernetes (sur n'importe quel provider)

**Rejeté.** Pour un projet à ce stade, Kubernetes est de la sur-ingénierie majeure :

- Courbe d'apprentissage de plusieurs mois
- Overhead mémoire et CPU important (cluster de 3 nœuds minimum recommandé = 30+ €/mois rien que pour le control plane)
- Tooling complexe à maîtriser (helm, kubectl, ingress controllers, etc.)
- Aucun avantage tangible avant ~1000 utilisateurs

Docker Compose suffit largement et tient parfaitement pour des années à ce volume.

### Self-hosting sur un Raspberry Pi ou serveur maison

**Rejeté.** Avantages : coût zéro après achat. Inconvénients :

- Disponibilité dépendante de la fiabilité du réseau internet domestique (peu fiable en CI)
- Pas d'IP statique facile, pas de protection DDoS, pas de redondance d'alimentation
- Inacceptable pour un service business utilisé par des commerçants

## Conséquences

### Positives

- **Coût total < 10 €/mois** pour une stack complète, robuste, et professionnelle
- **Contrôle total** : on peut tout configurer comme on veut, pas de limitations de PaaS
- **Backups testés** automatiquement chez Backblaze B2 avec restauration documentée
- **Caddy** simplifie énormément la gestion TLS (zero config)
- **Setup reproductible** : `docker compose up -d` et tout démarre, peu importe le serveur
- **Migration possible** : si on veut changer de provider, le `docker-compose.yml` est portable

### Négatives

- **Latence vers la CI** : ~150-200 ms depuis Abidjan vers les datacenters Hetzner (Allemagne/Finlande). Acceptable pour des appels API ponctuels, plus lourd pour des syncs volumineuses (rapatriement de 90 jours de ventes).
- **Dépendance à un single point of failure** : un seul serveur, pas de redondance. Si le VPS tombe, le service est down. Mitigé par : l'app fonctionne offline donc l'impact direct sur les commerçants est limité, et les backups permettent une reconstruction sur un autre serveur en quelques heures.
- **Gestion ops manuelle** : updates système, monitoring, débogage en SSH. Charge mentale supplémentaire pour un solo dev mais procédures documentées dans le runbook.
- **Pas de scaling automatique** : si soudainement 1000 commerçants se connectent en même temps, on est contraint par les ressources du VPS. Acceptable au MVP, à reconsidérer si le produit décolle.

### Neutres

- Hetzner facture en EUR. Pas de problème pour un dev qui paie en CFA via Visa/Mastercard, mais à anticiper si jamais on veut changer de mode de paiement.

## Plan de migration éventuel

Au cas où on doive un jour migrer ailleurs, le coût de migration est limité grâce à Docker Compose :

1. Provisionner un nouveau VPS chez un autre provider
2. Setup initial (voir runbook)
3. Restaurer le dernier backup PostgreSQL
4. Mettre à jour le DNS
5. Vérifier que tout fonctionne

Temps estimé : 2-4 heures de downtime maîtrisé.

## Critères qui justifieraient de revisiter cette décision

- Volume > 500 commerçants actifs (envisager un VPS plus puissant ou une séparation DB / API)
- Latence vers la CI devient un problème mesurable (envisager un cloud africain ou AWS Cape Town)
- Charge ops devient ingérable en solo (envisager un PaaS managé)
- Disponibilité requise plus stricte (envisager une architecture redondante avec failover)
