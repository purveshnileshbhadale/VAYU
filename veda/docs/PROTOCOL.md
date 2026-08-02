# VEDA Wire Protocol — v1

Transport: **WSS** (TLS 1.3) from device/dashboard to relay; relay never dials devices.
Framing: one JSON object per WebSocket text message (max 512 KiB in v1).

## Envelope (every message)

```json
{
  "v": 1,
  "type": "<message-type>",
  "from": "<deviceId or dashboardId>",
  "to": "<deviceId> | \"*\" | \"dashboard\"",
  "id": "<uuid>",
  "ts": "<iso8601>",
  "auth": "<session token> | null (dashboard plain serves)",
  "body": { ... type-specific ... }
}
```

## Discovery & registry

- `hello` — on connect: `{token, device:{id,name,platform,os,version,capabilities:[...]}}`.
  Relay replies `hello.ack {device, devices:[...], peerIssues}`.
- `status` — periodic heartbeat `{cpu,ram,disk,battery,temp,fans,net,app,clipboard?}`.
- `presence` — broadcast by relay when a device joins/leaves.

## Notifications (Universal Notifications)

- `notify.send` → relay returns `notify.ack {id}` (instance id) and fans out to subscribed
  target.
- `notify.update` — attach/dismiss? Use `notify.dismiss {instanceId}` to suppress across
  ALL devices that showed it ("dismiss once, dismissed everywhere").
- `notify.broadcast` — fan-out to all paired devices.

## Control

- `control.request` → `{action, args, consent:{requested|accepted|denied}, permission}`
- `control.consent.request` → relay → target `{controlId, action, source}`. Target prompts.
- `control.consent.result` → `{controlId, ok}`.
- `control.result` → `{controlId, ok, data?, error?}`.
- `terminal.request/result` — shell toke with confirmation (voice + UI).
- `clipboard.paste` / `files.transfer` — v1 stubs; E2E layer later.

## Control action catalog (v1)

| action        | permission        | notes |
|---------------|-------------------|-------|
| open_app      | `apps.open`       | app/page path on target |
| lock          | `system.lock`     | OS lock |
| sleep         | `system.sleep`    | OS suspend |
| restart       | `system.restart`  | needs strong consent |
| shutdown      | `system.shutdown` | needs strong consent |
| set_volume    | `media.master`    | 0..100 |
| send_notify   | `notify.send`     | raise a local toast |
| run_command   | `terminal`        | confirmation-gated, `terminal.confirm` |

Every action maps to a capability, and the capability must be (a) listed by target in
`hello.device.capabilities`, (b) granted in the pairing link record, and (c) covered by an
accepted consent for this session.

## Pairing

Two-party: device generates `pairToken` (16 bytes, base64url). Owner enters it in
Dashboard → relay binds `{deviceId → owner}`. The relay never stores helper tokens plaintext
(SHA-256 at rest). Token is one-time; after binding, session tokens rotate.

## Audit (append-only)

`{"ts","act","source","target","action","consent","result","ok?}` written by relay to
`audit/<YYYYMM>-<hash>.log` rotated monthly; dashboard reads via `GET /audit` (owner-only).

## Errors
- `403 fault=device_not_paired`  `403 fault=capability_denied`  `403 fault=consent_denied`
- `401 fault=bad_token`  `429 fault=rate_limited`  `503 fault=target_offline`