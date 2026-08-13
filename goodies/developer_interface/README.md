# Web Sweeper Developer Interface

The Developer Interface is a simple cross-platform control surface for Web Sweeper. It shows lane health, current stages, accepted and uploaded counts, Codex Live totals supplied by the controller, source and batch settings, and explicitly configured recovery actions.

It includes:

- one Flutter codebase with Android, iOS, macOS, Windows, Linux, and web targets;
- a dependency-free Python/Tk desktop companion;
- an authenticated Python controller bridge for desktop and mobile clients;
- configurable readable-text colors;
- green, yellow, orange, and red lane states;
- a color-coded `Gate X/Y · Ns` sweep signal on every lane (six acquisition gates and seven publisher gates);
- exact counters that refresh independently from the gate timer;
- an elapsed timer after the complete durable progress vector remains unchanged for 10 seconds;
- a per-lane Push control that remains disabled until five minutes without any progress evidence, then invokes only the host-configured trusted `push` action;
- a four-pad waiting game with a persistent high score and one-time round-20 message;
- one serialized production-writer invariant.

## Flutter

```bash
cd flutter
flutter pub get
flutter run
```

Choose the target with `flutter devices` and `flutter run -d <device>`. The shared UI is responsive; platform folders are provided for Android, iOS, macOS, Windows, Linux, and web.

## Python desktop app

```bash
python3 python/developer_interface.py
```

## Controller bridge

Copy `python/controller.example.json`, set its `projectRoot` and lane state paths, and add only the trusted action commands the operator intends to expose. Arbitrary commands from clients are never accepted.

Local desktop use:

```bash
export WEB_SWEEPER_TOKEN='replace-with-a-long-random-token'
python3 python/server.py --config /path/to/controller.json
```

For the simplest same-Mac connection, `--local-no-auth` accepts only loopback
clients and cannot be combined with a network-facing host. Remote and mobile
connections still require HTTPS and a token.

For a local service, the token may instead be kept in a mode-`0600` file and
passed with `--token-file`. A configured `metricsPath` supplies live global
counts such as `codexLive` and `confirmedStaged` without embedding project
specific storage credentials in the UI.

Mobile access must use HTTPS:

```bash
export WEB_SWEEPER_TOKEN='replace-with-a-long-random-token'
python3 python/server.py \
  --config /path/to/controller.json \
  --host 0.0.0.0 \
  --cert /path/to/fullchain.pem \
  --key /path/to/private-key.pem
```

Enter that HTTPS URL and token in the Android or iOS app. Tokens are stored only in the device's application preferences and are not part of public source. For an internet-facing deployment, use a maintained TLS reverse proxy, firewall rules, token rotation, and a private network or VPN.

## Safety contract

- Status is read from configured state/checkpoint/receipt files; a PID alone is not treated as progress.
- Inactivity is multi-signal: accepted, discovery-page/cursor, candidate-inventory,
  stage, upload, publication, verification, checkpoint timestamp, and receipt
  movement all count. A quiet accepted counter cannot terminate active discovery.
- Source adapters whose page journal is separate from their lane state can list
  trusted `progressPaths`; file-size or modification movement then resets the
  progress clock without parsing or exposing the journal contents.
- A recent discovery journal presents the lane explicitly as `discovery` with
  “moving smoothly” status. Its controller heartbeat is grouped as a 30-second
  checkpoint signal while exact accepted counts remain unchanged.
- Acquisition cards expose a pressable **Discovery Mode** or **Uploading Mode**
  pill with exact page, candidate, checkpoint, and upload details. Large
  discovery journals are sampled no more than once every 30 seconds.
- The publisher exposes **Verification Mode** or **Uploading Mode**. Its
  dismissible details show the exact gate, receipts, counts, queue state, and
  timestamps while upload counts remain visible on the card.
- Raw adapter stage names such as `prepare` are kept inside the detail view.
  The card instead shows a glowing **Active** status and a pressable Discovery,
  Verification, or Uploading control. Discovery and verification controls show
  the exact unchanged-evidence age and scale yellow to orange to red at five
  minutes; any durable counter, journal, receipt, or timestamp movement resets
  that clock.
- Production publishing remains limited to one serialized writer.
- UI actions invoke only host-configured commands and cannot accept shell text from the client.
- Actions are disabled by default in the public example.
- Push is a continuation request, not a permission bypass: no eligible staged unit means nothing is published.
- The interface does not bypass duplicate screening, publication receipts, or live verification.
- Staged, uploaded, published, and live-verified counts remain distinct.
