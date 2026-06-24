import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';
import 'package:izee_ui/services/app_services.dart';

class FakeAppServices extends AppServices {
  double balance = 250.0;
  List<Map<String, dynamic>> paymentMethods = [];
  List<Map<String, dynamic>> transactions = [];

  @override
  Future<Map<String, dynamic>> loadWallet() async {
    return {
      'balance': balance,
      'currency': 'EGP',
      'payment_methods': paymentMethods,
      'transactions': transactions,
    };
  }

  @override
  Future<Map<String, dynamic>> topUpWallet(double amount) async {
    balance += amount;
    transactions.insert(0, {
      'title': 'Wallet Charge',
      'amount': amount,
      'timestamp': DateTime.now().toIso8601String(),
      'type': 'top_up',
    });
    return {
      'status': 'success',
      'amount': amount,
      'balance': balance,
    };
  }

  @override
  Future<Map<String, dynamic>> addPaymentMethod({
    required String cardHolder,
    required String cardNumber,
    required String cardType,
    required String expiry,
  }) async {
    // Mask in the fake service to mimic backend behavior
    final rawNum = cardNumber.replaceAll(' ', '');
    final masked = rawNum.length >= 4
        ? '**** **** **** ${rawNum.substring(rawNum.length - 4)}'
        : '**** **** **** $rawNum';
    paymentMethods.add({
      'card_holder': cardHolder,
      'card_number': masked,
      'card_type': cardType,
      'expiry': expiry,
      'is_active': true,
    });
    return {'status': 'success'};
  }
}

void main() {
  testWidgets('WalletScreen loads, displays balance, supports top up and adding card', (WidgetTester tester) async {
    final fakeServices = FakeAppServices();

    Widget buildScreen() {
      return MaterialApp(
        home: Scaffold(
          body: WalletScreen(
            services: fakeServices,
            connect: (action, request, {quiet = false}) async {
              await request();
              return true;
            },
            onGo: (screen) {},
            showTicket: false,
            onToggleTicket: () async {},
          ),
        ),
      );
    }

    // Load WalletScreen
    await tester.pumpWidget(buildScreen());
    await tester.pumpAndSettle();

    // Verify initial balance
    expect(find.text('250.0 EGP'), findsOneWidget);
    expect(find.text('No saved credit/debit cards.'), findsOneWidget);
    expect(find.text('No recent transactions found.'), findsOneWidget);

    // Click Charge button
    await tester.tap(find.text('Charge'));
    await tester.pumpAndSettle();

    // Verify Charge dialog is visible
    expect(find.text('Charge Wallet'), findsOneWidget);
    
    // Tap confirm in Charge dialog (default is 100)
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();

    // Verify balance updated to 350.0 EGP and transaction appears
    expect(find.text('350.0 EGP'), findsOneWidget);
    expect(find.text('Wallet Charge'), findsOneWidget);
    expect(find.text('+ 100.0 EGP'), findsOneWidget);

    // Scroll to Add Payment Method button
    final addPaymentMethodButton = find.text('Add Payment Method');
    await tester.ensureVisible(addPaymentMethodButton);
    await tester.pumpAndSettle();

    // Click Add Payment Method button
    await tester.tap(addPaymentMethodButton);
    await tester.pumpAndSettle();

    // Verify Add Payment Method dialog is open
    expect(find.text('Cardholder Name'), findsOneWidget);
    expect(find.text('Card Number'), findsOneWidget);

    // Enter card details
    await tester.enterText(find.widgetWithText(TextField, 'Cardholder Name'), 'Ahmed Hassan');
    await tester.enterText(find.widgetWithText(TextField, 'Card Number'), '1234567812345678');
    await tester.enterText(find.widgetWithText(TextField, 'Expiry Date'), '12/28');
    await tester.enterText(find.widgetWithText(TextField, 'CVV'), '123');
    await tester.pump();

    // Tap Save button
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    // Verify payment method added (masked card number rendered)
    expect(find.text('**** **** **** 5678'), findsOneWidget);
    expect(find.text('Expires 12/28 - Ahmed Hassan'), findsOneWidget);
  });
}
