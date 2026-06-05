# Anti-patterns UI — POS Mobile

## Couleurs

### ❌ Couleur hardcodée → ✅ ColorScheme

```dart
// ❌ AVANT
color: const Color(0xFFC0714A)
color: Colors.green

// ✅ APRÈS
color: Theme.of(context).colorScheme.primary
color: Theme.of(context).colorScheme.secondary
```

### ❌ Palette non-conforme → ✅ Palette POS

```dart
// ❌ AVANT — orange Money / vert MTN
color: const Color(0xFFFF6600)  // interdit
color: const Color(0xFF00A650)  // interdit

// ✅ APRÈS — terracotta + émeraude POS
color: Theme.of(context).colorScheme.primary    // #C0714A
color: Theme.of(context).colorScheme.secondary  // #2D7A5B
```

---

## Typographie

### ❌ TextStyle inline → ✅ TextTheme

```dart
// ❌ AVANT
style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)
style: TextStyle(color: Colors.grey, fontSize: 12)

// ✅ APRÈS
style: Theme.of(context).textTheme.titleLarge
style: Theme.of(context).textTheme.bodySmall?.copyWith(
  color: Theme.of(context).colorScheme.onSurfaceVariant,
)
```

**Correspondances M3 → usage POS :**

| Style M3 | Usage |
|----------|-------|
| `titleLarge` | Titre écran, total vente |
| `titleMedium` | En-tête section, nom produit |
| `bodyMedium` | Texte courant, description |
| `bodySmall` | Métadonnées, dates |
| `labelLarge` | Texte de bouton |
| `labelSmall` | Badges, chips |

---

## Composants M2 → M3

### ❌ RaisedButton → ✅ FilledButton

```dart
// ❌ AVANT
RaisedButton(
  color: Colors.blue,
  onPressed: _encaisser,
  child: Text('Encaisser'),
)

// ✅ APRÈS
FilledButton(
  onPressed: _encaisser,
  child: const Text('Encaisser'),  // ✨ style via theme
)
```

### ❌ FlatButton → ✅ TextButton

```dart
// ❌ AVANT
FlatButton(onPressed: _annuler, child: Text('Annuler'))

// ✅ APRÈS
TextButton(onPressed: _annuler, child: const Text('Annuler'))
```

### ❌ BottomNavigationBar → ✅ NavigationBar

```dart
// ❌ AVANT
BottomNavigationBar(items: [...])

// ✅ APRÈS
NavigationBar(
  destinations: const [
    NavigationDestination(icon: Icon(Icons.point_of_sale), label: 'Caisse'),
    NavigationDestination(icon: Icon(Icons.receipt_long), label: 'Ventes'),
    NavigationDestination(icon: Icon(Icons.inventory_2), label: 'Stock'),
  ],
  selectedIndex: _index,
  onDestinationSelected: (i) => setState(() => _index = i),
)
```

### ❌ Container décoré → ✅ Card M3

```dart
// ❌ AVANT
Container(
  padding: const EdgeInsets.all(16),
  decoration: BoxDecoration(
    color: Colors.white,
    borderRadius: BorderRadius.circular(8),
    boxShadow: [BoxShadow(blurRadius: 4, color: Colors.black12)],
  ),
  child: ...,
)

// ✅ APRÈS
Card(
  elevation: 1,  // ✨ tonal elevation M3
  child: Padding(
    padding: const EdgeInsets.all(16),
    child: ...,
  ),
)
```

---

## Accessibilité

### ❌ IconButton sans tooltip → ✅ Avec tooltip

```dart
// ❌ AVANT
IconButton(icon: const Icon(Icons.delete), onPressed: _delete)

// ✅ APRÈS
IconButton(
  tooltip: 'Supprimer la ligne',  // ✨ Semantics auto + hint utilisateur
  icon: const Icon(Icons.delete),
  onPressed: _delete,
)
```

### ❌ Zone tactile trop petite → ✅ 48×48px minimum

```dart
// ❌ AVANT
GestureDetector(
  onTap: _toggle,
  child: const Icon(Icons.add, size: 20),
)

// ✅ APRÈS
IconButton(
  constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
  icon: const Icon(Icons.add, size: 20),
  onPressed: _toggle,
)
```

### ❌ Image sans sémantique → ✅ Exclu du tree ou labellisé

```dart
// ❌ AVANT
Image.asset('assets/logo.png')

// ✅ APRÈS — si décoratif
Image.asset('assets/logo.png', excludeFromSemantics: true)

// ✅ APRÈS — si porteur de sens
Semantics(
  label: 'Logo POS',
  child: Image.asset('assets/logo.png'),
)
```

---

## Responsive

### ❌ Largeur fixe → ✅ Adaptive

```dart
// ❌ AVANT
SizedBox(width: 320, child: _form)

// ✅ APRÈS
LayoutBuilder(
  builder: (context, constraints) => SizedBox(
    width: constraints.maxWidth.clamp(0, 480),  // ✨ max raisonnable sur grands écrans
    child: _form,
  ),
)
```

### ❌ Column overflow → ✅ Scrollable

```dart
// ❌ AVANT — risque RenderFlex overflow
Column(children: [...longList])

// ✅ APRÈS
SingleChildScrollView(
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [...longList],
  ),
)
```

---

## États manquants

### ❌ Pas de gestion d'états → ✅ 4 états requis

```dart
// ❌ AVANT
return ListView.builder(
  itemCount: items.length,
  itemBuilder: (_, i) => _ItemTile(items[i]),
);

// ✅ APRÈS
return salesAsync.when(
  loading: () => const Center(child: CircularProgressIndicator()),
  error: (e, _) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('Erreur : $e'),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: () => ref.invalidate(saleNotifierProvider),
          child: const Text('Réessayer'),
        ),
      ],
    ),
  ),
  data: (items) => items.isEmpty
      ? const EmptyState(
          icon: Icons.receipt_long_outlined,
          title: 'Aucune vente',
          subtitle: 'Les ventes apparaîtront ici.',
        )
      : ListView.builder(
          itemCount: items.length,
          itemBuilder: (_, i) => _ItemTile(items[i]),
        ),
);
```

---

## Performance Flutter

### ❌ `const` manquant → ✅ Partout où possible

```dart
// ❌ AVANT
SizedBox(height: 16)
Text('Total')
Icon(Icons.receipt)
EdgeInsets.all(16)

// ✅ APRÈS
const SizedBox(height: 16)
const Text('Total')
const Icon(Icons.receipt)
const EdgeInsets.all(16)
```

### ❌ Widget monolithique → ✅ Découpé

```dart
// ❌ AVANT — écran de 300 lignes avec tout inline

// ✅ APRÈS — extraction en widgets privés
class SaleScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: const _SaleAppBar(),       // widget extrait
      body: const _SaleBody(),           // widget extrait
      bottomNavigationBar: const _SaleBottomBar(),  // widget extrait
    );
  }
}

class _SaleAppBar extends StatelessWidget implements PreferredSizeWidget { ... }
class _SaleBody extends ConsumerWidget { ... }
class _SaleBottomBar extends ConsumerWidget { ... }
```