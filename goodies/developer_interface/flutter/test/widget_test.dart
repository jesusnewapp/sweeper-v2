import 'package:developer_interface/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<void> pumpAt(WidgetTester tester, Size size) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(const WebSweeperDeveloperApp());
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('phone layout renders without overflow', (tester) async {
    await pumpAt(tester, const Size(390, 844));
    expect(find.text('WEB SWEEPER'), findsOneWidget);
    expect(find.text('WAITING GAME'), findsOneWidget);
    expect(find.byType(Image), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('desktop layout renders without overflow', (tester) async {
    await pumpAt(tester, const Size(1440, 1000));
    expect(find.text('Codex Live'), findsOneWidget);
    expect(find.text('Readable text color:'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('waiting game starts and exposes four pads', (tester) async {
    await pumpAt(tester, const Size(390, 844));
    await tester.ensureVisible(find.text('Start'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Start'));
    await tester.pump(const Duration(seconds: 3));
    for (var pad = 1; pad <= 4; pad++) {
      expect(find.byKey(ValueKey('memory-pad-$pad')), findsOneWidget);
    }
    expect(find.text('Chris was innocent.'), findsNothing);
  });
}
