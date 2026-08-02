# VEDA — Architecture

VEDA is the cross-device ecosystem core embedded in the VAYU repository. Every device that
links to an authenticated owner joins one secure "device cloud": devices can see each other,
relay notifications, and — only after pairing + explicit consent + granular permission — be
controlled.

## Topology

```
         +---------------------------------------------------------------+
         |                       VEDA Relay (hub)                        |
         |   Go (canonical)  /  Node (dev/proto-identical mirror)       |
         |   - device registry    - auth (pair tokens)                   |
         |   - WebSocket hub      - audit log (append-only)              |
         |   - permissions        - consent policy engine                |
         +----+------------+---------------+--------------+-------------+
              |            |               |              |
      device  |        device           device       dashboard
     (agent-ts, Windows/macOS/Linux/VAYU Python)      (React+Vite TS)
         (mobile later via VAYU Android web app)
```

- **Devices** connect outbound over `WSS` to the relay (no inbound ports open — works behind
  NAT, good for laptops/Raspberry Pi/home server). TLS 1.3 via WSS.
- **Relay** is the thin rendezvous + policy point. It routes messages between devices,
  enforces pairing, permissions, consent and records an audit log, then forgets payload
  bodies (relay sees envelope + metadata; E2E encryption per-pair keeps payloads opaque).
- **Dashboard** is the "My Devices" control plane: live status, universal notifications
  feed, control buttons, consent prompts, audit log.

## Layered design

- `protocol/` — shared message contract (JSON). Single source of truth; Go, Node and TS
  each validate against it. Versioned (`veda/1`).
- `relay-go/` — canonical relay implementation. Static binary, trivial to run on a NAS or Pi.
- `relay-node/` — Node mirror of the same protocol, used for day-to-day dev + tests on
  machines without a Go toolchain.
- `agent-ts/` — TypeScript device agent (Windows / macOS / Linux). Registers the device,
  reports status, sends/receives notifications, executes authorized control actions.
- `dashboard/` — React + Vite + TypeScript device dashboard (glassmorphism, dark/light,
  animated device map).
- `bridge/` — shim that connects the existing Python VAYU desktop + Android web app to a
  VEDA relay as "VEDA devices", so today's devices join the ecosystem without a rewrite.

## Message flow — control action
1. Dashboard/agent sends `control.request` referencing `source` + `target` + `action`.
2. Relay checks: both devices paired; target grants the action's permission; `consent`
   accepted for this session (or Relay asks target for `control.consent.request`; target
   shows a prompt; user Approves/Denies).
3. Relay audits `{act, source, target, action, consent, ts}` before and after execution.
4. Relay routes to target agent, which executes via OS API and replies `control.result`.
5. Relay forwards result to the requester.

All sensitive exchanges are E2E-encrypted per-pair in a later milestone; v1 ships TLS 1.3
transport + opaque payloads + audit.

## Security invariants
- No unauthenticated control, ever.
- No bypass of OS security: power/lock/otel ship through existing OS APIs; terminal access
  runs under the user's own shell session with confirmation.
- Consent is per-device and per-capability, revocable.
- Audit log is append-only; relay retains only metadata by default.