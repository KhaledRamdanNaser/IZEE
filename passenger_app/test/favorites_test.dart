import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';
import 'package:izee_ui/services/app_services.dart';

void main() {
  testWidgets('Favorite Searches logic and toggling works', (WidgetTester tester) async {
    final session = PlanTripSession();
    final services = AppServices();
    
    Widget buildScreen() {
      return MaterialApp(
        home: Scaffold(
          body: PlanTripScreen(
            services: services,
            connect: (action, request, {quiet = false}) async => true,
            onGo: (screen) {},
            session: session,
            onRouteSelected: (route) {},
          ),
        ),
      );
    }

    await tester.pumpWidget(buildScreen());

    // Initial state: star icon should NOT be visible since origin/destination are not selected
    expect(find.byIcon(Icons.star_border), findsNothing);
    expect(find.byIcon(Icons.star), findsNothing);

    // Populate origin & destination in session
    session.selectedOrigin = {'lat': 30.0444, 'lon': 31.2357};
    session.selectedDestination = {'lat': 30.0131, 'lon': 31.2089};
    session.originText = 'Maadi';
    session.destinationText = 'Zamalek';

    // Re-pump widget to reflect changes
    await tester.pumpWidget(buildScreen());

    // Now star icon should be visible since origin/destination are selected
    final headerStarBorder = find.descendant(of: find.byType(HeaderRow), matching: find.byIcon(Icons.star_border));
    final headerStar = find.descendant(of: find.byType(HeaderRow), matching: find.byIcon(Icons.star));

    expect(headerStarBorder, findsOneWidget);

    // Toggle favorite
    await tester.tap(headerStarBorder);
    await tester.pump();

    // Verify it is added to favorites and the icon turns into a filled star
    expect(session.favoriteSearches.length, 1);
    expect(session.favoriteSearches.first.originText, 'Maadi');
    expect(session.favoriteSearches.first.destinationText, 'Zamalek');

    // Re-pump to verify filled star icon rendering
    await tester.pumpWidget(buildScreen());
    expect(headerStar, findsOneWidget);

    // Untoggle favorite
    await tester.tap(headerStar);
    await tester.pump();

    // Verify it is removed
    expect(session.favoriteSearches.isEmpty, true);

    // Re-pump to verify outline star icon rendering
    await tester.pumpWidget(buildScreen());
    expect(headerStarBorder, findsOneWidget);
  });

  testWidgets('FavoritesScreen displays favorites, clicking select works, and deleting works', (WidgetTester tester) async {
    final session = PlanTripSession();
    session.favoriteSearches.add(const FavoriteTrip(
      routeId: 'trip_plan_test_001',
      originText: 'Maadi',
      destinationText: 'Zamalek',
      origin: {'lat': 30.0444, 'lon': 31.2357},
      destination: {'lat': 30.0131, 'lon': 31.2089},
    ));

    FavoriteTrip? selectedFav;
    var backPressed = false;

    Widget buildScreen() {
      return MaterialApp(
        home: Scaffold(
          body: FavoritesScreen(
            session: session,
            onBack: () => backPressed = true,
            onSelectFavorite: (fav) => selectedFav = fav,
            onDeleteFavorite: (fav) {},
          ),
        ),
      );
    }

    await tester.pumpWidget(buildScreen());

    // Verify it renders the favorite trip label
    expect(find.text('Maadi -> Zamalek'), findsOneWidget);

    // Click the favorite search tile to trigger onSelectFavorite
    await tester.tap(find.text('Maadi -> Zamalek'));
    await tester.pump();

    expect(selectedFav, isNotNull);
    expect(selectedFav!.originText, 'Maadi');
    expect(selectedFav!.destinationText, 'Zamalek');

    // Tap delete button to remove it
    await tester.tap(find.byIcon(Icons.delete_outline));
    await tester.pump();

    // Verify it is deleted from the session and screen is updated
    expect(session.favoriteSearches.isEmpty, true);
    expect(find.text('Maadi -> Zamalek'), findsNothing);
    expect(find.text('No favorite places yet'), findsOneWidget);
  });
}
