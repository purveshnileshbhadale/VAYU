# VEDA — VAYU Ecosystem

VEDA is the **cross-device ecosystem core** living inside the VAYU repository. Any device you
log into becomes part of one secure "device cloud": they discover each other, relay
universal notifications, and — only after pairing, consent and granular permissions — can be
controlled.

This first milestone covers **Universal Notifications + Control**, built on the stack you
chose:

- **Go relay** (canonical, static binary — runs on a Pi/NAS/home server)
- **TypeScript everywhere** (node dev-relay mirror, device agents, dashboard)

```
veda/
├── docs/
│   ├── ARCHITECTURE.md     # topology, security invariants
│   └── PROTOCOL.md         # wire contract v1 (single source of truth)
├── protocol/               # shared TS types (mirrors Go structs)
├── relay-go/               # canonical relay (Go 1.26)
│   ├── cmd/veda-relay/     # the binary
│   └── internal/{auth,hub,policy,audit,server,message}
├── relay-node/             # dev mirror of the same protocol (no Go needed)
├── agent/                  # TS device agent (Windows/macOS/Linux)
├── dashboard/              # React+Vite TS "My Devices" control plane
└── scripts/                # helpers
```

## Run it (dev, today, no Go required)

```powershell
# 1. relay (node mirror)
cd veda\relay-node; npm install; npm run dev -- --port=8080 --token=vayu-dev
# 2. an agent on this machine
cd veda\agent; npm install
$env:VEDA_RELAY='ws://127.0.0.1'; $env:VEDA_TOKEN='vayu-dev'; npm run dev
# 3. dashboard
cd veda\dashboard; npm install; npm run dev   # http://localhost:5173
```

## Run the canonical Go relay

```
go build -o dist/veda-relay ./...   # or use a prebuilt release
veda-relay --listen :8080 --token <claim> [--tls-cert cert.pem --tls-key key.pem] [--ui dist]
```

TLS 1.3 on by default when you pass a cert; otherwise plain WS for LAN dev. Wire a reverse
proxy (Caddy/traefik) in front for public relays.

## Security model (v1)

- Every connection authenticates a `hello` token; unauthenticated peers get `401`.
- Remote **control** requires the target to list the capability **and** the relay to audit it.
- **Destructive/system actions** (`restart`, `shutdown`, `run_command`) go through a
  **consent gate**: the agent shows an OS-native prompt and the user explicitly approves.
- All actions are written to an **append-only audit log** (`audit/<YYYYMM>.log`).
- The relay is a thin rendezvous; end-to-end payload encryption is the next milestone
  (transport encryption via TLS today).

## Spaces to build next

Universal clipboard · drag-and-drop files · AI command center · shared memory ·
remote terminal · unified search · media control · presence. The `protocol/types.ts`
`envelope` and `control` flows are the seam where those plug in.

## Tests

```
# Go relay: build, vet, unit tests
go build ./... && go vet ./... && go test ./...
# cross-implementation e2e (Go relay must be running on :8080)
cd veda\relay-node && npx tsx src/smoke.ts   # expects ALL PASS
```

`go.mod` — the repo has no `go.sum` committed yet; run `go mod tidy` before first CI.