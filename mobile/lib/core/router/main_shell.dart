import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/navigation/nav_provider.dart';
import '../../features/home/presentation/pages/home_page.dart';
import '../../features/catalog/presentation/pages/catalog_page.dart';
import '../../features/sales/presentation/pages/sales_history_page.dart';
import '../../features/settings/presentation/pages/settings_page.dart';

/// Main shell with IndexedStack for persistent navigation and state preservation.
class MainShell extends ConsumerWidget {
  /// Creates a main shell.
  const MainShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final index = ref.watch(bottomNavIndexProvider);

    return Scaffold(
      body: IndexedStack(
        index: index,
        children: const [
          HomePage(),
          CatalogPage(),
          SalesHistoryPage(),
          SettingsPage(),
        ],
      ),
      bottomNavigationBar: _BottomNavBar(currentIndex: index, ref: ref),
    );
  }
}

/// Bottom navigation bar.
class _BottomNavBar extends StatelessWidget {
  const _BottomNavBar({required this.currentIndex, required this.ref});

  final int currentIndex;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        color: cs.surface,
        border: Border(
          top: BorderSide(
            color: cs.onSurface.withValues(alpha: 0.08),
            width: 1,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: cs.shadow.withValues(alpha: 0.04),
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            _NavBarItem(
              index: 0,
              label: 'Accueil',
              icon: Icons.home_outlined,
              activeIcon: Icons.home,
              color: cs.primary,
              isActive: currentIndex == 0,
              onTap: () =>
                  ref.read(bottomNavIndexProvider.notifier).setIndex(0),
            ),
            _NavBarItem(
              index: 1,
              label: 'Catalogue',
              icon: Icons.shopping_bag_outlined,
              activeIcon: Icons.shopping_bag,
              color: const Color(0xFF6B8E6F),
              isActive: currentIndex == 1,
              onTap: () =>
                  ref.read(bottomNavIndexProvider.notifier).setIndex(1),
            ),
            _NavBarItem(
              index: 2,
              label: 'Historique',
              icon: Icons.history_outlined,
              activeIcon: Icons.history,
              color: const Color(0xFFE8A87C),
              isActive: currentIndex == 2,
              onTap: () =>
                  ref.read(bottomNavIndexProvider.notifier).setIndex(2),
            ),
            _NavBarItem(
              index: 3,
              label: 'Paramètres',
              icon: Icons.settings_outlined,
              activeIcon: Icons.settings,
              color: const Color(0xFF8B7355),
              isActive: currentIndex == 3,
              onTap: () =>
                  ref.read(bottomNavIndexProvider.notifier).setIndex(3),
            ),
          ],
        ),
      ),
    );
  }
}

/// Individual nav bar item.
class _NavBarItem extends StatefulWidget {
  const _NavBarItem({
    required this.index,
    required this.label,
    required this.icon,
    required this.activeIcon,
    required this.color,
    required this.isActive,
    required this.onTap,
  });

  final int index;
  final String label;
  final IconData icon;
  final IconData activeIcon;
  final Color color;
  final bool isActive;
  final VoidCallback onTap;

  @override
  State<_NavBarItem> createState() => _NavBarItemState();
}

class _NavBarItemState extends State<_NavBarItem> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTapDown: (_) => setState(() => _isPressed = true),
        onTapUp: (_) {
          setState(() => _isPressed = false);
          widget.onTap();
        },
        onTapCancel: () => setState(() => _isPressed = false),
        child: MouseRegion(
          cursor: SystemMouseCursors.click,
          child: AnimatedScale(
            scale: _isPressed ? 0.9 : 1.0,
            duration: const Duration(milliseconds: 100),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: widget.isActive
                          ? widget.color.withValues(alpha: 0.12)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      widget.isActive ? widget.activeIcon : widget.icon,
                      color: widget.isActive
                          ? widget.color
                          : Theme.of(context).colorScheme.onSurfaceVariant,
                      size: 24,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    widget.label,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: widget.isActive
                          ? widget.color
                          : Theme.of(context).colorScheme.onSurfaceVariant,
                      fontWeight: widget.isActive
                          ? FontWeight.w600
                          : FontWeight.w500,
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
