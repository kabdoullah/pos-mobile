import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/auth/presentation/pages/splash_page.dart';
import '../../features/auth/presentation/pages/register_page.dart';
import '../../features/auth/presentation/pages/pin_setup_page.dart';
import '../../features/auth/presentation/pages/pin_login_page.dart';
import '../../features/auth/presentation/pages/email_login_page.dart';
import '../../features/auth/presentation/pages/store_setup_page.dart';
import '../../features/onboarding/presentation/pages/tutorial_page.dart';
import '../../features/auth/presentation/providers/auth_providers.dart';
import '../../features/catalog/presentation/pages/catalog_page.dart';
import '../../features/catalog/presentation/pages/product_form_page.dart';
import '../../features/catalog/presentation/pages/barcode_scanner_page.dart';
import '../../features/sales/presentation/pages/new_sale_page.dart';
import '../../features/sales/presentation/pages/payment_page.dart';
import '../../features/sales/presentation/pages/sale_success_page.dart';
import '../../features/sales/presentation/pages/sales_history_page.dart';
import '../../features/sales/presentation/pages/sale_detail_page.dart';
import '../../features/sales/domain/entities/sale.dart';
import '../../features/sales/domain/entities/cart_item.dart';
import '../../features/home/presentation/pages/home_page.dart';
import '../../features/settings/presentation/pages/settings_page.dart';
import '../../features/printing/presentation/pages/bluetooth_setup_page.dart';

part 'app_router.g.dart';

/// Navigation routes for the app.
abstract class Routes {
  /// Splash/loading screen.
  static const String splash = '/splash';

  /// Onboarding flow (email + password registration).
  static const String register = '/register';

  /// PIN setup after first login.
  static const String pinSetup = '/pin-setup';

  /// Daily PIN login.
  static const String pinLogin = '/pin-login';

  /// Email login for account recovery / new device.
  static const String emailLogin = '/email-login';

  /// Store configuration screen.
  static const String storeSetup = '/store-setup';

  /// Onboarding tutorial.
  static const String tutorial = '/tutorial';

  /// Home/dashboard screen.
  static const String home = '/home';

  /// Catalog (product list).
  static const String catalog = '/catalog';

  /// Create new product.
  static const String productNew = '/catalog/new';

  /// Edit product (path parameter :id).
  static const String productEdit = '/catalog/:id/edit';

  /// Barcode scanner modal.
  static const String barcodeScanner = '/scan';

  /// New sale (create sale from cart).
  static const String newSale = '/sales/new';

  /// Payment method selection.
  static const String payment = '/sales/payment';

  /// Sale success confirmation.
  static const String saleSuccess = '/sales/success';

  /// Sales history (past sales with date filtering).
  static const String salesHistory = '/sales/history';

  /// Sale detail view (path parameter :id, or receives Sale via extra).
  static const String saleDetail = '/sales/detail';

  /// Settings page.
  static const String settings = '/settings';

  /// Bluetooth printer setup.
  static const String bluetoothSetup = '/settings/printer';
}

/// Root router configuration.
@Riverpod(keepAlive: true)
GoRouter appRouter(Ref ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: Routes.splash,
    redirect: (BuildContext context, GoRouterState state) {
      // Routes that don't require redirect logic.
      final publicRoutes = {Routes.splash, Routes.register, Routes.emailLogin};

      if (publicRoutes.contains(state.fullPath)) {
        return null;
      }

      // Redirect based on auth state.
      return switch (authState) {
        // Unauthenticated: redirect to email login.
        AuthStateUnauthenticated() => Routes.emailLogin,

        // PIN setup required (first login, PIN not yet created).
        AuthStatePinSetupRequired() => Routes.pinSetup,

        // PIN verification required (PIN exists, needs verification).
        AuthStatePinRequired() => Routes.pinLogin,

        // Fully authenticated: allow access to main app.
        AuthStateAuthenticated() => null,

        // Loading or error: stay on current route.
        _ => null,
      };
    },
    routes: [
      GoRoute(
        path: Routes.splash,
        builder: (context, state) => const SplashPage(),
      ),
      GoRoute(
        path: Routes.register,
        builder: (context, state) => const RegisterPage(),
      ),
      GoRoute(
        path: Routes.emailLogin,
        builder: (context, state) => const EmailLoginPage(),
      ),
      GoRoute(
        path: Routes.pinSetup,
        builder: (context, state) => const PinSetupPage(),
      ),
      GoRoute(
        path: Routes.pinLogin,
        builder: (context, state) => const PinLoginPage(),
      ),
      GoRoute(
        path: Routes.storeSetup,
        builder: (context, state) => const StoreSetupPage(),
      ),
      GoRoute(
        path: Routes.tutorial,
        builder: (context, state) => const TutorialPage(),
      ),
      GoRoute(path: Routes.home, builder: (context, state) => const HomePage()),
      GoRoute(
        path: Routes.catalog,
        builder: (context, state) => const CatalogPage(),
      ),
      GoRoute(
        path: Routes.productNew,
        builder: (context, state) => const ProductFormPage(),
      ),
      GoRoute(
        path: Routes.productEdit,
        builder: (context, state) {
          final productId = state.pathParameters['id'];
          return ProductFormPage(productId: productId);
        },
      ),
      GoRoute(
        path: Routes.barcodeScanner,
        builder: (context, state) => const BarcodeScannerPage(),
      ),
      GoRoute(
        path: Routes.newSale,
        builder: (context, state) => const NewSalePage(),
      ),
      GoRoute(
        path: Routes.payment,
        builder: (context, state) => const PaymentPage(),
      ),
      GoRoute(
        path: Routes.saleSuccess,
        builder: (context, state) {
          final extra = state.extra as ({Sale sale, List<CartItem> items})?;
          if (extra == null) return const SalesHistoryPage();
          return SaleSuccessPage(sale: extra.sale, items: extra.items);
        },
      ),
      GoRoute(
        path: Routes.salesHistory,
        builder: (context, state) => const SalesHistoryPage(),
      ),
      GoRoute(
        path: Routes.saleDetail,
        builder: (context, state) {
          final sale = state.extra as Sale?;
          if (sale == null) return const SalesHistoryPage();
          return SaleDetailPage(sale: sale);
        },
      ),
      GoRoute(
        path: Routes.settings,
        builder: (context, state) => const SettingsPage(),
      ),
      GoRoute(
        path: Routes.bluetoothSetup,
        builder: (context, state) => const BluetoothSetupPage(),
      ),
    ],
  );
}
