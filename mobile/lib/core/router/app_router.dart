import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:logger/logger.dart';

import 'page_transitions.dart';
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
  final logger = Logger();
  logger.i('[Router] Creating router instance');

  late GoRouter router;
  router = GoRouter(
    initialLocation: Routes.splash,
    redirect: (BuildContext context, GoRouterState state) {
      final authValue = ref.read(authProvider);
      logger.i(
        '[Router.redirect] Current path: ${state.fullPath}, authValue: ${authValue.runtimeType}',
      );

      // Public routes (accessible while unauthenticated).
      final publicRoutes = {Routes.register, Routes.emailLogin};

      // Auth/onboarding routes (not accessible when fully authenticated).
      final authRoutes = {
        Routes.splash,
        Routes.register,
        Routes.emailLogin,
        Routes.pinSetup,
        Routes.pinLogin,
        Routes.storeSetup,
        Routes.tutorial,
      };

      // Redirect based on AsyncValue<AuthStatus> state.
      // AsyncLoading: stay on current route (init in progress).
      // AsyncError: send to login (auth failed, need to re-authenticate).
      // AsyncData: switch on the AuthStatus value.
      final targetRoute = authValue.when(
        loading: () {
          logger.i(
            '[Router.redirect] Auth loading, staying on ${state.fullPath}',
          );
          return null;
        },
        error: (_, _) {
          logger.i(
            '[Router.redirect] Auth error, redirecting to ${Routes.emailLogin}',
          );
          return Routes.emailLogin;
        },
        data: (status) {
          return switch (status) {
            // Unauthenticated: allow public routes, redirect others to email login.
            AuthUnauthenticated() =>
              publicRoutes.contains(state.fullPath) ? null : Routes.emailLogin,

            // Store setup required (first registration, store not yet configured).
            AuthStoreSetupRequired() => Routes.storeSetup,

            // PIN setup required (first login, PIN not yet created).
            AuthPinSetupRequired() => Routes.pinSetup,

            // PIN verification required (PIN exists, needs verification).
            AuthPinRequired() => Routes.pinLogin,

            // Fully authenticated: redirect from auth routes to home, allow access to main app.
            AuthAuthenticated() =>
              authRoutes.contains(state.fullPath) ? Routes.home : null,
          };
        },
      );

      // Only redirect if target differs from current path.
      final shouldRedirect =
          targetRoute != null && targetRoute != state.fullPath;
      final redirect = shouldRedirect ? targetRoute : null;

      logger.i('[Router.redirect] Target: $targetRoute, redirect: $redirect');
      return redirect;
    },
    routes: [
      GoRoute(
        path: Routes.splash,
        builder: (context, state) => const SplashPage(),
      ),
      GoRoute(
        path: Routes.register,
        pageBuilder: (context, state) =>
            PageTransitions.fade(context, state, const RegisterPage()),
      ),
      GoRoute(
        path: Routes.emailLogin,
        pageBuilder: (context, state) =>
            PageTransitions.fade(context, state, const EmailLoginPage()),
      ),
      GoRoute(
        path: Routes.pinSetup,
        pageBuilder: (context, state) =>
            PageTransitions.fade(context, state, const PinSetupPage()),
      ),
      GoRoute(
        path: Routes.pinLogin,
        pageBuilder: (context, state) =>
            PageTransitions.fade(context, state, const PinLoginPage()),
      ),
      GoRoute(
        path: Routes.storeSetup,
        pageBuilder: (context, state) =>
            PageTransitions.fade(context, state, const StoreSetupPage()),
      ),
      GoRoute(
        path: Routes.tutorial,
        pageBuilder: (context, state) =>
            PageTransitions.fade(context, state, const TutorialPage()),
      ),
      GoRoute(
        path: Routes.home,
        pageBuilder: (context, state) =>
            PageTransitions.slideRight(context, state, const HomePage()),
      ),
      GoRoute(
        path: Routes.catalog,
        pageBuilder: (context, state) =>
            PageTransitions.slideRight(context, state, const CatalogPage()),
      ),
      GoRoute(
        path: Routes.productNew,
        pageBuilder: (context, state) =>
            PageTransitions.scale(context, state, const ProductFormPage()),
      ),
      GoRoute(
        path: Routes.productEdit,
        pageBuilder: (context, state) {
          final productId = state.pathParameters['id'];
          return PageTransitions.scale(
            context,
            state,
            ProductFormPage(productId: productId),
          );
        },
      ),
      GoRoute(
        path: Routes.barcodeScanner,
        pageBuilder: (context, state) =>
            PageTransitions.scale(context, state, const BarcodeScannerPage()),
      ),
      GoRoute(
        path: Routes.newSale,
        pageBuilder: (context, state) =>
            PageTransitions.slideRight(context, state, const NewSalePage()),
      ),
      GoRoute(
        path: Routes.payment,
        pageBuilder: (context, state) =>
            PageTransitions.scale(context, state, const PaymentPage()),
      ),
      GoRoute(
        path: Routes.saleSuccess,
        pageBuilder: (context, state) {
          final extra = state.extra as ({Sale sale, List<CartItem> items})?;
          final child = extra == null
              ? const SalesHistoryPage()
              : SaleSuccessPage(sale: extra.sale, items: extra.items);
          return PageTransitions.fadeScale(context, state, child);
        },
      ),
      GoRoute(
        path: Routes.salesHistory,
        pageBuilder: (context, state) => PageTransitions.slideRight(
          context,
          state,
          const SalesHistoryPage(),
        ),
      ),
      GoRoute(
        path: Routes.saleDetail,
        pageBuilder: (context, state) {
          final sale = state.extra as Sale?;
          final child = sale == null
              ? const SalesHistoryPage()
              : SaleDetailPage(sale: sale);
          return PageTransitions.scale(context, state, child);
        },
      ),
      GoRoute(
        path: Routes.settings,
        pageBuilder: (context, state) =>
            PageTransitions.fade(context, state, const SettingsPage()),
      ),
      GoRoute(
        path: Routes.bluetoothSetup,
        pageBuilder: (context, state) =>
            PageTransitions.scale(context, state, const BluetoothSetupPage()),
      ),
    ],
  );

  // Listen to auth state changes and refresh router without recreating it.
  ref.listen(authProvider, (_, _) {
    logger.i('[Router] Auth state changed, calling router.refresh()');
    router.refresh();
  });

  return router;
}
