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

  testWidgets('unchanged percentages show their age after ten seconds', (
    tester,
  ) async {
    final since = DateTime.utc(2026, 1, 1);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ModelCard(
            model: const ModelView(
              id: 'publisher',
              name: 'Publisher',
              stage: 'Live verification',
              accepted: 100,
              target: 100,
              uploaded: 100,
              health: Health.healthy,
              detail: 'Single writer',
            ),
            observation: ProgressObservation(
              progressTenthsPercent: 1000,
              since: since,
            ),
            stageObservation: StageObservation(
              stage: 'Live verification',
              since: since,
            ),
            now: since.add(const Duration(seconds: 11)),
            onPush: () {},
          ),
        ),
      ),
    );
    expect(find.textContaining('At 100.0% for'), findsOneWidget);
    expect(find.text('Gate 6/7 · 11s'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('acquisition search gate has a timed health signal', (
    tester,
  ) async {
    final since = DateTime.utc(2026, 1, 1);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ModelCard(
            model: const ModelView(
              id: 'library-of-congress',
              name: 'Library of Congress',
              stage: 'prepare',
              accepted: 0,
              target: 2000,
              uploaded: 0,
              health: Health.watch,
              detail: 'Searching and qualifying candidates',
            ),
            observation: ProgressObservation(
              progressTenthsPercent: 0,
              since: since,
            ),
            stageObservation: StageObservation(stage: 'prepare', since: since),
            now: since.add(const Duration(seconds: 37)),
            onPush: () {},
          ),
        ),
      ),
    );
    expect(find.text('Gate 2/6 · 37s'), findsOneWidget);
    expect(find.byIcon(Icons.radar_rounded), findsOneWidget);
    expect(
      find.byKey(const ValueKey('active-pill-library-of-congress')),
      findsOneWidget,
    );
    expect(find.text('Active'), findsOneWidget);
    expect(find.text('prepare'), findsNothing);
    expect(find.text('Discovery · 37s'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('discovery mode opens exact live journal details', (
    tester,
  ) async {
    final since = DateTime.utc(2026, 1, 1);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ModelCard(
            model: const ModelView(
              id: 'library-of-congress',
              name: 'Library of Congress',
              stage: 'discovery',
              mode: 'discovery',
              modeDetail: {
                'stage': 'discovery',
                'pagesCompleted': 152,
                'candidateRecords': 450,
                'sampleCadenceSeconds': 30,
              },
              accepted: 6,
              target: 2000,
              uploaded: 0,
              health: Health.healthy,
              detail: 'Discovery mode · moving smoothly',
            ),
            observation: ProgressObservation(
              progressTenthsPercent: 3,
              since: since,
            ),
            stageObservation: StageObservation(
              stage: 'discovery',
              since: since,
            ),
            now: since.add(const Duration(seconds: 30)),
            onPush: () {},
          ),
        ),
      ),
    );
    await tester.tap(
      find.byKey(const ValueKey('mode-pill-library-of-congress')),
    );
    await tester.pumpAndSettle();
    expect(find.text('Discovery details'), findsOneWidget);
    expect(find.text('Pages completed'), findsOneWidget);
    expect(find.text('152'), findsOneWidget);
    expect(find.text('Candidate records'), findsOneWidget);
    expect(find.text('450'), findsOneWidget);
    await tester.tap(
      find.byKey(const ValueKey('close-mode-library-of-congress')),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('mode-dialog-library-of-congress')),
      findsNothing,
    );
  });

  testWidgets('publisher verification mode exposes receipt details', (
    tester,
  ) async {
    final since = DateTime.utc(2026, 1, 1);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ModelCard(
            model: const ModelView(
              id: 'publisher',
              name: 'Stage-to-live publisher',
              stage: 'live-verification',
              mode: 'verification',
              modeDetail: {
                'stage': 'live-verification',
                'published': 853,
                'liveVerified': 812,
                'publicationReceipt': true,
                'promotionReceipt': false,
              },
              accepted: 812,
              target: 853,
              uploaded: 853,
              health: Health.healthy,
              detail: 'Verification in progress',
            ),
            observation: ProgressObservation(
              progressTenthsPercent: 952,
              since: since,
            ),
            stageObservation: StageObservation(
              stage: 'live-verification',
              since: since,
            ),
            now: since.add(const Duration(seconds: 20)),
            onPush: () {},
          ),
        ),
      ),
    );
    await tester.tap(find.byKey(const ValueKey('mode-pill-publisher')));
    await tester.pumpAndSettle();
    expect(find.text('Verification details'), findsOneWidget);
    expect(find.text('Live verified'), findsOneWidget);
    expect(find.text('812'), findsAtLeastNWidgets(1));
    expect(find.text('Promotion receipt'), findsOneWidget);
  });

  testWidgets('push remains disabled until five minutes without movement', (
    tester,
  ) async {
    final since = DateTime.utc(2026, 1, 1);
    var pushes = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ModelCard(
            model: const ModelView(
              id: 'publisher',
              name: 'Publisher',
              stage: 'Listening for next exact staged unit',
              accepted: 853,
              target: 853,
              uploaded: 853,
              health: Health.watch,
              detail: '0 ready',
            ),
            observation: ProgressObservation(
              progressTenthsPercent: 1000,
              since: since,
            ),
            stageObservation: StageObservation(
              stage: 'Listening for next exact staged unit',
              since: since,
            ),
            now: since.add(const Duration(minutes: 5)),
            onPush: () => pushes++,
          ),
        ),
      ),
    );
    await tester.tap(find.byKey(const ValueKey('push-publisher')));
    expect(pushes, 1);
    expect(find.text('Push'), findsOneWidget);
    expect(find.text('Gate 7/7 · 300s'), findsOneWidget);
    expect(find.text('Verification · stuck 5m 00s'), findsOneWidget);
  });

  testWidgets('four model slots expose name and connector fields', (
    tester,
  ) async {
    await pumpAt(tester, const Size(1440, 1200));
    for (var slot = 0; slot < 4; slot++) {
      expect(find.byKey(ValueKey('model-slot-$slot')), findsOneWidget);
      expect(find.byKey(ValueKey('model-name-$slot')), findsOneWidget);
      expect(find.byKey(ValueKey('model-connector-$slot')), findsOneWidget);
    }
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
