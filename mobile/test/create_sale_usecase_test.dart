import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/sales/domain/entities/cart_item.dart';
import 'package:mobile/features/sales/domain/entities/sale.dart';
import 'package:mobile/features/sales/domain/repositories/sales_repository.dart';
import 'package:mobile/features/sales/domain/usecases/create_sale_usecase.dart';
import 'package:mocktail/mocktail.dart';

// Mock repository
class MockSalesRepository extends Mock implements SalesRepository {}

// Helpers
CartItem makeCartItem({
  String productId = 'prod-1',
  String productName = 'Produit test',
  Decimal? unitPrice,
  int quantity = 1,
}) {
  return CartItem(
    productId: productId,
    productName: productName,
    unitPrice: unitPrice ?? Decimal.parse('100'),
    quantity: quantity,
  );
}

Sale makeSale({
  String id = 'sale-123',
  int receiptNumber = 1,
  Decimal? totalAmount,
  Decimal? vatAmount,
  PaymentMethod paymentMethod = PaymentMethod.cash,
}) {
  return Sale(
    id: id,
    receiptNumber: receiptNumber,
    totalAmount: totalAmount ?? Decimal.parse('100'),
    vatAmount: vatAmount ?? Decimal.parse('0'),
    paymentMethod: paymentMethod,
    createdAt: DateTime.now(),
  );
}

void main() {
  setUpAll(() {
    registerFallbackValue(PaymentMethod.cash);
    registerFallbackValue(Decimal.zero);
    registerFallbackValue(<CartItem>[]);
  });

  group('CreateSaleUseCase', () {
    late MockSalesRepository mockRepository;
    late CreateSaleUseCase useCase;

    setUp(() {
      mockRepository = MockSalesRepository();
      useCase = CreateSaleUseCase(repository: mockRepository);
    });

    group('Validation: cart not empty', () {
      test('throws CreateSaleException when cart is empty', () async {
        const expectedMessage = 'Le panier est vide';

        expect(
          () => useCase(
            items: [],
            totalAmount: Decimal.parse('100'),
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.cash,
          ),
          throwsA(
            isA<CreateSaleException>().having(
              (e) => e.message,
              'message',
              expectedMessage,
            ),
          ),
        );

        // Repository should never be called
        verifyZeroInteractions(mockRepository);
      });
    });

    group('Validation: amount constraints', () {
      test('throws CreateSaleException when totalAmount is negative', () async {
        final items = [makeCartItem()];

        expect(
          () => useCase(
            items: items,
            totalAmount: Decimal.parse('-100'),
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.cash,
          ),
          throwsA(
            isA<CreateSaleException>().having(
              (e) => e.message,
              'message',
              'Montant total invalide',
            ),
          ),
        );

        verifyZeroInteractions(mockRepository);
      });

      test('throws CreateSaleException when vatAmount is negative', () async {
        final items = [makeCartItem()];

        expect(
          () => useCase(
            items: items,
            totalAmount: Decimal.parse('100'),
            vatAmount: Decimal.parse('-10'),
            paymentMethod: PaymentMethod.cash,
          ),
          throwsA(
            isA<CreateSaleException>().having(
              (e) => e.message,
              'message',
              'Montant TVA invalide',
            ),
          ),
        );

        verifyZeroInteractions(mockRepository);
      });
    });

    group('Validation: cart total coherence', () {
      test('throws when calculated total does not match provided total', () {
        // Create items that sum to 150
        final items = [
          makeCartItem(unitPrice: Decimal.parse('100'), quantity: 1),
          makeCartItem(
            productId: 'prod-2',
            unitPrice: Decimal.parse('50'),
            quantity: 1,
          ),
        ];

        expect(
          () => useCase(
            items: items,
            totalAmount: Decimal.parse('200'), // Mismatch: actual is 150
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.cash,
          ),
          throwsA(
            isA<CreateSaleException>().having(
              (e) => e.message,
              'message',
              contains('Total panier'),
            ),
          ),
        );

        verifyZeroInteractions(mockRepository);
      });

      test('double-check detects money precision mismatch', () {
        // Items sum to 1234.56 exactly
        final items = [
          makeCartItem(unitPrice: Decimal.parse('1234.56'), quantity: 1),
        ];

        // Provide a different total that would pass with double arithmetic
        // but fails with Decimal (more precise)
        expect(
          () => useCase(
            items: items,
            totalAmount: Decimal.parse('1234.57'),
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.cash,
          ),
          throwsA(isA<CreateSaleException>()),
        );
      });
    });

    group('Validation: mixed payment coherence', () {
      test(
        'accepts mixed payment when cash + mobileMoney equals total',
        () async {
          final items = [makeCartItem(unitPrice: Decimal.parse('100'))];
          final mockSale = makeSale(
            totalAmount: Decimal.parse('100'),
            paymentMethod: PaymentMethod.mixed,
          );

          when(
            () => mockRepository.createSale(
              items: any(named: 'items'),
              totalAmount: any(named: 'totalAmount'),
              vatAmount: any(named: 'vatAmount'),
              paymentMethod: any(named: 'paymentMethod'),
              cashAmount: any(named: 'cashAmount'),
              mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
            ),
          ).thenAnswer((_) async => mockSale);

          final result = await useCase(
            items: items,
            totalAmount: Decimal.parse('100'),
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.mixed,
            cashAmount: Decimal.parse('60'),
            mobileMoneyAmount: Decimal.parse('40'),
          );

          expect(result.id, 'sale-123');
          verify(
            () => mockRepository.createSale(
              items: any(named: 'items'),
              totalAmount: Decimal.parse('100'),
              vatAmount: Decimal.parse('0'),
              paymentMethod: PaymentMethod.mixed,
              cashAmount: Decimal.parse('60'),
              mobileMoneyAmount: Decimal.parse('40'),
            ),
          ).called(1);
        },
      );

      test(
        'throws when mixed payment totals do not match sale total',
        () async {
          final items = [makeCartItem(unitPrice: Decimal.parse('100'))];

          expect(
            () => useCase(
              items: items,
              totalAmount: Decimal.parse('100'),
              vatAmount: Decimal.parse('0'),
              paymentMethod: PaymentMethod.mixed,
              cashAmount: Decimal.parse('60'),
              mobileMoneyAmount: Decimal.parse('30'), // Total: 90, not 100
            ),
            throwsA(
              isA<CreateSaleException>().having(
                (e) => e.message,
                'message',
                contains('Total paiement'),
              ),
            ),
          );

          verifyNever(
            () => mockRepository.createSale(
              items: any(named: 'items'),
              totalAmount: any(named: 'totalAmount'),
              vatAmount: any(named: 'vatAmount'),
              paymentMethod: any(named: 'paymentMethod'),
            ),
          );
        },
      );

      test('treats null cashAmount as Decimal.zero in mixed payment', () async {
        final items = [makeCartItem(unitPrice: Decimal.parse('100'))];
        final mockSale = makeSale(totalAmount: Decimal.parse('100'));

        when(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: any(named: 'totalAmount'),
            vatAmount: any(named: 'vatAmount'),
            paymentMethod: any(named: 'paymentMethod'),
            cashAmount: any(named: 'cashAmount'),
            mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
          ),
        ).thenAnswer((_) async => mockSale);

        final result = await useCase(
          items: items,
          totalAmount: Decimal.parse('100'),
          vatAmount: Decimal.parse('0'),
          paymentMethod: PaymentMethod.mixed,
          cashAmount: null,
          mobileMoneyAmount: Decimal.parse('100'),
        );

        expect(result.id, 'sale-123');
        verify(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: Decimal.parse('100'),
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.mixed,
            cashAmount: null,
            mobileMoneyAmount: Decimal.parse('100'),
          ),
        ).called(1);
      });

      test(
        'throws when both cashAmount and mobileMoneyAmount are null with positive total',
        () async {
          final items = [makeCartItem(unitPrice: Decimal.parse('100'))];

          expect(
            () => useCase(
              items: items,
              totalAmount: Decimal.parse('100'),
              vatAmount: Decimal.parse('0'),
              paymentMethod: PaymentMethod.mixed,
              cashAmount: null,
              mobileMoneyAmount: null,
            ),
            throwsA(
              isA<CreateSaleException>().having(
                (e) => e.message,
                'message',
                contains('Total paiement'),
              ),
            ),
          );

          verifyNever(
            () => mockRepository.createSale(
              items: any(named: 'items'),
              totalAmount: any(named: 'totalAmount'),
              vatAmount: any(named: 'vatAmount'),
              paymentMethod: any(named: 'paymentMethod'),
            ),
          );
        },
      );
    });

    group('Nominal cases', () {
      test('creates sale with cash payment successfully', () async {
        final items = [
          makeCartItem(unitPrice: Decimal.parse('2500'), quantity: 1),
          makeCartItem(
            productId: 'prod-2',
            productName: 'Autre produit',
            unitPrice: Decimal.parse('500'),
            quantity: 2,
          ),
        ];
        final expectedTotal = Decimal.parse('3500');
        final mockSale = makeSale(
          totalAmount: expectedTotal,
          paymentMethod: PaymentMethod.cash,
        );

        when(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: any(named: 'totalAmount'),
            vatAmount: any(named: 'vatAmount'),
            paymentMethod: any(named: 'paymentMethod'),
            cashAmount: any(named: 'cashAmount'),
            mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
          ),
        ).thenAnswer((_) async => mockSale);

        final result = await useCase(
          items: items,
          totalAmount: expectedTotal,
          vatAmount: Decimal.parse('0'),
          paymentMethod: PaymentMethod.cash,
        );

        expect(result.id, 'sale-123');
        expect(result.totalAmount, expectedTotal);
        verify(
          () => mockRepository.createSale(
            items: items,
            totalAmount: expectedTotal,
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.cash,
            cashAmount: null,
            mobileMoneyAmount: null,
          ),
        ).called(1);
      });

      test('creates sale with mobile money payment successfully', () async {
        final items = [makeCartItem(unitPrice: Decimal.parse('1000'))];
        final mockSale = makeSale(
          totalAmount: Decimal.parse('1000'),
          paymentMethod: PaymentMethod.orangeMoney,
        );

        when(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: any(named: 'totalAmount'),
            vatAmount: any(named: 'vatAmount'),
            paymentMethod: any(named: 'paymentMethod'),
            cashAmount: any(named: 'cashAmount'),
            mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
          ),
        ).thenAnswer((_) async => mockSale);

        final result = await useCase(
          items: items,
          totalAmount: Decimal.parse('1000'),
          vatAmount: Decimal.parse('0'),
          paymentMethod: PaymentMethod.orangeMoney,
        );

        expect(result.paymentMethod, PaymentMethod.orangeMoney);
        verify(
          () => mockRepository.createSale(
            items: items,
            totalAmount: Decimal.parse('1000'),
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.orangeMoney,
            cashAmount: null,
            mobileMoneyAmount: null,
          ),
        ).called(1);
      });
    });

    group('Decimal precision', () {
      test('handles decimal amounts with sub-unit precision', () async {
        final items = [
          makeCartItem(unitPrice: Decimal.parse('1234.56'), quantity: 1),
          makeCartItem(
            productId: 'prod-2',
            unitPrice: Decimal.parse('0.99'),
            quantity: 1,
          ),
        ];
        final expectedTotal = Decimal.parse('1235.55');
        final mockSale = makeSale(totalAmount: expectedTotal);

        when(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: any(named: 'totalAmount'),
            vatAmount: any(named: 'vatAmount'),
            paymentMethod: any(named: 'paymentMethod'),
            cashAmount: any(named: 'cashAmount'),
            mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
          ),
        ).thenAnswer((_) async => mockSale);

        final result = await useCase(
          items: items,
          totalAmount: expectedTotal,
          vatAmount: Decimal.parse('0'),
          paymentMethod: PaymentMethod.cash,
        );

        expect(result.totalAmount, expectedTotal);
        verify(
          () => mockRepository.createSale(
            items: items,
            totalAmount: expectedTotal,
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.cash,
            cashAmount: null,
            mobileMoneyAmount: null,
          ),
        ).called(1);
      });

      test('accurately sums cart with multiple decimal items', () async {
        final items = [
          makeCartItem(unitPrice: Decimal.parse('100.50'), quantity: 2),
          makeCartItem(
            productId: 'prod-2',
            unitPrice: Decimal.parse('50.25'),
            quantity: 4,
          ),
        ];
        // 100.50 * 2 + 50.25 * 4 = 201 + 201 = 402
        final expectedTotal = Decimal.parse('402');
        final mockSale = makeSale(totalAmount: expectedTotal);

        when(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: any(named: 'totalAmount'),
            vatAmount: any(named: 'vatAmount'),
            paymentMethod: any(named: 'paymentMethod'),
            cashAmount: any(named: 'cashAmount'),
            mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
          ),
        ).thenAnswer((_) async => mockSale);

        final result = await useCase(
          items: items,
          totalAmount: expectedTotal,
          vatAmount: Decimal.parse('0'),
          paymentMethod: PaymentMethod.cash,
        );

        expect(result.totalAmount, expectedTotal);
      });
    });

    group('Repository error propagation', () {
      test('propagates repository exception without masking', () async {
        final items = [makeCartItem()];
        final repositoryError = Exception('Database connection failed');

        when(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: any(named: 'totalAmount'),
            vatAmount: any(named: 'vatAmount'),
            paymentMethod: any(named: 'paymentMethod'),
            cashAmount: any(named: 'cashAmount'),
            mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
          ),
        ).thenThrow(repositoryError);

        expect(
          () => useCase(
            items: items,
            totalAmount: Decimal.parse('100'),
            vatAmount: Decimal.parse('0'),
            paymentMethod: PaymentMethod.cash,
          ),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('Integration: full workflow', () {
      test('complex multi-item sale with VAT and mixed payment', () async {
        final items = [
          makeCartItem(
            productName: 'Riz 25kg',
            unitPrice: Decimal.parse('15000'),
            quantity: 2,
          ),
          makeCartItem(
            productId: 'prod-2',
            productName: 'Huile 5L',
            unitPrice: Decimal.parse('8500'),
            quantity: 1,
          ),
          makeCartItem(
            productId: 'prod-3',
            productName: 'Sucre 1kg',
            unitPrice: Decimal.parse('2500'),
            quantity: 3,
          ),
        ];
        // Total: 15000*2 + 8500*1 + 2500*3 = 30000 + 8500 + 7500 = 46000
        final expectedTotal = Decimal.parse('46000');
        final expectedVat = Decimal.parse('4600');

        final mockSale = makeSale(
          totalAmount: expectedTotal,
          vatAmount: expectedVat,
          paymentMethod: PaymentMethod.mixed,
        );

        when(
          () => mockRepository.createSale(
            items: any(named: 'items'),
            totalAmount: any(named: 'totalAmount'),
            vatAmount: any(named: 'vatAmount'),
            paymentMethod: any(named: 'paymentMethod'),
            cashAmount: any(named: 'cashAmount'),
            mobileMoneyAmount: any(named: 'mobileMoneyAmount'),
          ),
        ).thenAnswer((_) async => mockSale);

        final result = await useCase(
          items: items,
          totalAmount: expectedTotal,
          vatAmount: expectedVat,
          paymentMethod: PaymentMethod.mixed,
          cashAmount: Decimal.parse('20000'),
          mobileMoneyAmount: Decimal.parse('26000'),
        );

        expect(result.totalAmount, expectedTotal);
        expect(result.vatAmount, expectedVat);
        expect(result.paymentMethod, PaymentMethod.mixed);
        verify(
          () => mockRepository.createSale(
            items: items,
            totalAmount: expectedTotal,
            vatAmount: expectedVat,
            paymentMethod: PaymentMethod.mixed,
            cashAmount: Decimal.parse('20000'),
            mobileMoneyAmount: Decimal.parse('26000'),
          ),
        ).called(1);
      });
    });
  });
}
