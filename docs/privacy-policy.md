# Politique de confidentialité — Ma Caisse

**Dernière mise à jour : 8 juin 2025**

Ma Caisse est une application de point de vente (POS) destinée aux commerçants et petites entreprises. Cette politique de confidentialité explique quelles données sont collectées, comment elles sont utilisées et quels sont vos droits.

---

## 1. Qui est responsable du traitement des données ?

**Abdoulaye Kemogoha Coulibaly**
Contact : abdoullahcoulibaly2@gmail.com

---

## 2. Données collectées

### 2.1 Données de compte

Lors de l'inscription et de l'utilisation de l'application, nous collectons :

- **Numéro de téléphone** (format E.164) — identifiant principal du compte
- **Adresse e-mail** (optionnelle) — uniquement pour la récupération de compte
- **Nom de la boutique** et informations commerciales saisies lors de la configuration

### 2.2 Données d'activité commerciale

- Catalogue produits (nom, prix, code-barres) créé par le commerçant
- Historique des ventes enregistrées via l'application

### 2.3 Données stockées localement sur l'appareil

- **Code PIN** — haché localement (PBKDF2-HMAC-SHA256 avec sel aléatoire) et stocké dans le trousseau sécurisé de l'appareil (`flutter_secure_storage`). Le PIN n'est **jamais** transmis à nos serveurs.
- **Jetons d'authentification JWT** — stockés dans le trousseau sécurisé, utilisés pour maintenir la session.
- **Cache des données de vente** — stocké localement pour permettre l'utilisation hors connexion.

### 2.4 Permissions matérielles utilisées

| Permission | Usage |
|---|---|
| Internet | Synchronisation des données avec le serveur |
| Caméra | Scan de codes-barres produits |
| Bluetooth | Connexion à l'imprimante thermique pour les reçus |

---

## 3. Utilisation des données

Les données collectées sont utilisées exclusivement pour :

- Fournir et faire fonctionner le service de caisse
- Synchroniser le catalogue et l'historique des ventes entre l'appareil et le serveur
- Permettre l'accès sécurisé au compte (authentification par téléphone + PIN)
- Générer et imprimer des reçus clients

Nous n'utilisons pas vos données à des fins publicitaires ou de profilage.

---

## 4. Partage des données

Vos données ne sont **pas vendues** ni partagées avec des tiers à des fins commerciales.

Les données sont hébergées sur notre serveur backend. Aucune donnée n'est transmise à des services d'analyse tiers ou de publicité.

---

## 5. Conservation des données

- Les données de compte et d'activité sont conservées tant que le compte est actif.
- En cas de demande de suppression de compte, les données sont supprimées dans un délai de 30 jours.

---

## 6. Sécurité

- Les communications entre l'application et le serveur sont chiffrées via HTTPS (TLS).
- Le PIN est haché localement et n'est jamais transmis en clair.
- Les jetons d'authentification sont stockés dans le trousseau sécurisé du système d'exploitation.
- L'accès aux données est isolé par boutique (chaque commerçant ne peut accéder qu'à ses propres données).

---

## 7. Vos droits

Vous disposez des droits suivants concernant vos données personnelles :

- **Accès** : demander une copie des données associées à votre compte
- **Rectification** : corriger des données inexactes
- **Suppression** : demander la suppression de votre compte et de vos données

Pour exercer ces droits, contactez-nous à : **abdoullahcoulibaly2@gmail.com**

---

## 8. Modifications de cette politique

Toute modification substantielle de cette politique sera notifiée via l'application. La date de dernière mise à jour figurant en haut de ce document sera également actualisée.

---

## 9. Contact

Pour toute question relative à cette politique de confidentialité :

**Email :** abdoullahcoulibaly2@gmail.com
