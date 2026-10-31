# Backoffice admin — Front (pos-backoffice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une SPA React déployée sur Netlify qui permet à l'administrateur de se connecter, voir les indicateurs plateforme, lister les boutiques et les suspendre / réactiver.

**Architecture:** SPA statique Vite + React + TypeScript dans un nouveau dépôt `pos-backoffice` (dossier frère : `/Users/kemogoha/Documents/Developpement/Projet Perso/pos-backoffice`). Un client `apiFetch` unique gère base URL, token, timeout et erreurs ; TanStack Query gère cache et états ; React Router protège les pages derrière le login.

**Tech Stack:** Vite (template `react-ts`), React 19, React Router 7, @tanstack/react-query 5, Tailwind CSS 4 (`@tailwindcss/vite`), Vitest + @testing-library/react + @testing-library/user-event + jsdom. Node 26 / npm 11 (présents).

**Spec:** `docs/superpowers/specs/2026-10-31-backoffice-admin-design.md` (dans le dépôt `pos-mobile`). **Prérequis :** plan backend `2026-10-31-backoffice-admin-backend.md` terminé (contrat d'API ci-dessous).

## Global Constraints

- Interface en français. Pas de `window.confirm` / `alert` : confirmation via `<dialog>` natif.
- Montants reçus en `string`, jamais d'arithmétique côté front ; affichage `Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })` + ` FCFA`.
- Dates : `Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeZone: 'Africa/Abidjan' })`.
- Token admin : mémoire + `sessionStorage` (clé `pos_admin_token`, avec `expires_at`), jamais `localStorage`.
- Timeout requêtes : 60 s ; message « Le serveur démarre… » après 5 s d'attente.
- API via `import.meta.env.VITE_API_URL` ; le build échoue si la variable est absente.
- Site non indexé : `<meta name="robots" content="noindex">` + `robots.txt` `Disallow: /`.
- TypeScript `strict`, pas de `any`.

## Contrat d'API (produit par le plan backend)

| Méthode | Chemin | Corps / Query | Réponse |
|---|---|---|---|
| POST | `/api/v1/admin/auth/login` | `{email, password}` | `{access_token, token_type: "bearer", expires_in}` |
| GET | `/api/v1/admin/metrics` | — | `{stores_total, stores_new_7d, stores_active_7d, stores_inactive_14d, stores_suspended, sales_today_count, sales_today_amount, sales_7d_count, sales_7d_amount}` (montants en string) |
| GET | `/api/v1/admin/stores` | `search, status=all\|active\|suspended, inactive=bool, sort=last_sale\|created, limit, offset` | `{items: AdminStoreItem[], total}` |
| POST | `/api/v1/admin/stores/{id}/suspend` | `{reason?: string ≤ 500}` | `AdminStoreItem` |
| POST | `/api/v1/admin/stores/{id}/reactivate` | — | `AdminStoreItem` |

`AdminStoreItem = {id, name, owner_phone, created_at, last_sale_at: string|null, sales_count, suspended_at: string|null, suspension_reason: string|null}`. Erreurs : `{detail, code, field, details?}`. 401 = token absent ou expiré.

## Review Focus

1. Token expiré pendant la session (2 h) → la requête suivante renvoie 401 → retour à `/login`, pas d'écran blanc (test Task 2).
2. API injoignable / cold start Render → indicateur après 5 s, puis message d'erreur + bouton « Réessayer » (tests Tasks 1 et 3).
3. Boutique sans vente → « Jamais » dans la colonne dernière vente (test Task 4).
4. Double clic sur « Confirmer la suspension » → une seule requête (bouton désactivé pendant la mutation) (test Task 4).
5. Rechargement direct de `/stores` → la page s'affiche (redirection SPA Netlify) et la session est conservée (test Task 2 + vérification Task 5).

---

### Task 1: Scaffold, client API et formatage

**Files:**
- Create: projet via `npm create vite@latest pos-backoffice -- --template react-ts`, `vite.config.ts` (plugins react + tailwind ; `test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' }`), `src/test/setup.ts`, `src/index.css` (`@import "tailwindcss";`), `src/vite-env.d.ts` (`VITE_API_URL: string`)
- Create: `src/lib/api.ts`, `src/lib/format.ts`, `src/lib/types.ts`
- Test: `src/lib/api.test.ts`, `src/lib/format.test.ts`

**Interfaces:**
- Produces : `class ApiError extends Error { status: number; code: string; kind: 'http' | 'timeout' | 'network' }` ; `apiFetch<T>(path: string, init?: { method?: string; body?: unknown; token?: string | null }): Promise<T>` (préfixe `VITE_API_URL`, JSON, `Authorization: Bearer`, timeout via `AbortSignal.timeout(60_000)` ; sur 401 appelle le handler enregistré par `setUnauthorizedHandler(fn: () => void): void`) ; `formatFcfa(amount: string): string` ; `formatDate(iso: string | null): string` (`null` → `"Jamais"`) ; types `PlatformMetrics`, `AdminStoreItem`, `AdminStorePage`, `StoreQuery` conformes au contrat.

- [ ] **Step 1:** Scaffold, `git init`, installer les dépendances de Tech Stack, scripts `"test": "vitest run"` et `"typecheck": "tsc -b"`. `npm run build` → OK.
- [ ] **Step 2: Write the failing tests** :
  - `formatFcfa("1234567.00")` → après `.replace(/\s/g, ' ')` : `"1 234 567 FCFA"` ; `formatFcfa("0")` → `"0 FCFA"`.
  - `formatDate(null)` → `"Jamais"`.
  - `apiFetch` avec `fetch` mocké : 200 → corps JSON ; 403 `{detail: "x", code: "FORBIDDEN"}` → `ApiError` `status 403`, `code "FORBIDDEN"`, `message "x"` ; 401 → handler appelé une fois ; rejet `TypeError` → `kind 'network'` ; rejet `DOMException` nommée `TimeoutError` → `kind 'timeout'`.
- [ ] **Step 3:** `npm test` → FAIL. Implémenter. `npm test && npm run typecheck` → PASS.
- [ ] **Step 4:** `git commit -m "chore: scaffold Vite React TS, client API et formatage"`

### Task 2: Authentification et routes protégées

**Files:**
- Create: `src/auth/session.ts`, `src/auth/AuthProvider.tsx`, `src/auth/RequireAuth.tsx`, `src/pages/LoginPage.tsx`, `src/App.tsx` (routes `/login`, `/`, `/stores` ; layout avec navigation et « Se déconnecter »), `src/main.tsx` (QueryClient, `retry: 1`)
- Test: `src/auth/auth.test.tsx`

**Interfaces:**
- Consumes : `apiFetch`, `setUnauthorizedHandler`, `ApiError`.
- Produces : `loadSession(): { token: string; expiresAt: number } | null` (null si absente ou expirée) ; `saveSession(token: string, expiresInSeconds: number): void` ; `clearSession(): void` ; hook `useAuth(): { token: string | null; login(email: string, password: string): Promise<void>; logout(): void }`.

- [ ] **Step 1: Write the failing tests** :
  - login réussi (fetch mocké) → navigation vers `/`, `sessionStorage.pos_admin_token` présent.
  - 401 au login → texte `"Email ou mot de passe incorrect."`, reste sur `/login`.
  - accès direct à `/stores` sans session → redirigé vers `/login`.
  - session valide dans `sessionStorage` au montage → `/stores` accessible sans reconnexion.
  - session expirée (`expiresAt` passé) → `/login`.
  - 401 sur une requête protégée → session effacée, `/login`, cache TanStack vidé.
- [ ] **Step 2:** `npm test` → FAIL. Implémenter. `npm test && npm run typecheck` → PASS.
- [ ] **Step 3:** `git commit -m "feat: connexion admin et routes protégées"`

### Task 3: Tableau de bord

**Files:**
- Create: `src/pages/DashboardPage.tsx`, `src/components/StatCard.tsx`, `src/components/QueryState.tsx`, `src/hooks/useSlowFlag.ts`
- Test: `src/pages/DashboardPage.test.tsx`

**Interfaces:**
- Produces : `useSlowFlag(isPending: boolean, delayMs?: number /* 5000 */): boolean` ; `<QueryState isPending isError error onRetry>` (chargement ; « Le serveur démarre, cela peut prendre jusqu'à une minute… » quand lent ; erreur + bouton « Réessayer »), réutilisé en Task 4.
- Cartes (spec 4.1) : « Boutiques inscrites » (`stores_total`, sous-titre `+{stores_new_7d} cette semaine`), « Boutiques actives (7 j) », « Ventes aujourd'hui » (`sales_today_count` + `formatFcfa(sales_today_amount)`), « Ventes 7 jours », « Inactives (14 j) » (lien `/stores?inactive=true`), « Suspendues » (lien `/stores?status=suspended`).

- [ ] **Step 1: Write the failing tests** : données mockées → les 6 libellés et `"5 000 FCFA"` affichés ; requête en attente > 5 s (fake timers) → texte « Le serveur démarre » ; erreur réseau → bouton « Réessayer » qui relance la requête.
- [ ] **Step 2:** `npm test` → FAIL. Implémenter. `npm test && npm run typecheck` → PASS.
- [ ] **Step 3:** `git commit -m "feat: tableau de bord des indicateurs plateforme"`

### Task 4: Liste des boutiques et suspension

**Files:**
- Create: `src/pages/StoresPage.tsx`, `src/components/SuspendDialog.tsx`, `src/hooks/useStores.ts`
- Test: `src/pages/StoresPage.test.tsx`

**Interfaces:**
- Consumes : `QueryState`, `formatDate`, `apiFetch`, types.
- Produces : `useStores(query: StoreQuery)` (clé `['stores', query]`), `useSuspendStore()`, `useReactivateStore()` (invalident `['stores']` et `['metrics']` au succès).
- Comportement : filtres dans l'URL (`useSearchParams` : `search`, `status`, `inactive`, `sort`, `page`) ; recherche avec debounce 300 ms ; 20 par page ; colonnes Nom, Téléphone, Inscrite le, Dernière vente, Ventes, Statut (badge « Active » / « Suspendue », raison en `title`), Action. « Suspendre » ouvre `SuspendDialog` (raison facultative, `maxLength={500}`, boutons « Annuler » / « Confirmer la suspension », désactivés pendant la mutation). « Réactiver » agit directement. Erreur de mutation → message affiché dans le dialogue ou la ligne.

- [ ] **Step 1: Write the failing tests** :
  - liste mockée → ligne sans vente affiche « Jamais » ; badge « Suspendue » pour l'item suspendu.
  - saisie « kiosk » → une seule requête avec `search=kiosk` après 300 ms (fake timers).
  - `?status=suspended` dans l'URL → requête avec `status=suspended`.
  - suspendre : ouvrir le dialogue, saisir « Impayé », double-cliquer sur Confirmer → **une** requête POST avec `{reason: "Impayé"}`, dialogue fermé, liste re-fetchée.
  - réactiver → POST `/reactivate` puis re-fetch.
  - pagination : `total = 45` → « Page 1 / 3 » ; Suivant → `offset=20`.
- [ ] **Step 2:** `npm test` → FAIL. Implémenter. `npm test && npm run typecheck && npm run build` → PASS.
- [ ] **Step 3:** `git commit -m "feat: liste des boutiques, suspension et réactivation"`

### Task 5: Dépôt GitHub et déploiement Netlify

**Files:**
- Create: `netlify.toml`, `public/robots.txt`, `README.md` (dev local, variables, déploiement) ; modifier `index.html` (`lang="fr"`, `<title>POS Backoffice</title>`, meta robots)

- [ ] **Step 1:** `netlify.toml` :
  ```toml
  [build]
    command = "npm run build"
    publish = "dist"
  [[redirects]]
    from = "/*"
    to = "/index.html"
    status = 200
  [[headers]]
    for = "/*"
    [headers.values]
      X-Frame-Options = "DENY"
      X-Content-Type-Options = "nosniff"
      Referrer-Policy = "strict-origin-when-cross-origin"
      X-Robots-Tag = "noindex"
      Content-Security-Policy = "default-src 'self'; connect-src 'self' https://pos-mobile-vkuh.onrender.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
  ```
- [ ] **Step 2:** `npm test && npm run build` → PASS ; `git commit -m "chore: configuration Netlify"`.
- [ ] **Step 3:** Créer le dépôt **privé** et pousser, après accord explicite de l'utilisateur : `gh repo create kabdoullah/pos-backoffice --private --source . --push`.
- [ ] **Step 4 (utilisateur, guidé) :** Netlify → « Add new site » → « Import an existing project » → GitHub → `pos-backoffice` ; variable `VITE_API_URL = https://pos-mobile-vkuh.onrender.com` ; Deploy. Noter l'URL `https://<site>.netlify.app`.
- [ ] **Step 5:** Ajouter cette URL à `CORS_ORIGINS` sur Render (plan backend, Task 7) et redéployer l'API.
- [ ] **Step 6: Vérification bout-en-bout** sur l'URL Netlify : login admin → tableau de bord chargé ; rechargement direct de `/stores` → page affichée ; suspendre une boutique de test → `curl` avec le token de cette boutique sur `/api/v1/stores/me` → 403 `STORE_SUSPENDED` ; réactiver → 200.
