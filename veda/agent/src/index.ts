// VEDA agent core: WebSocket relay client with reconnect, status reporting,
// notification handling, consent-gated control execution, local audit log.
import WebSocket from 'ws';
import { randomUUID } from 'node:crypto';
import { appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { homedir, hostname } from 'node:os';
import type { Envelope, Device, ControlRequest, ConsentRequest, ConsentResult, Notify } from '../../protocol/index.js';
import { Msg, env } from '../../protocol/index.js';
import * as pl from './platform.js';

const STATE_DIR = process.env.VEDA_STATE || join(homedir(), '.veda');
const AUDIT_FILE = join(STATE_DIR, 'audit.log');
mkdirSync(STATE_DIR, { recursive: true });

function audit(action: string, meta: Record<string, unknown>) {
  appendFileSync(AUDIT_FILE, JSON.stringify({ ts: new Date().toISOString(), action, ...meta }) + '\n');
}

interface Opts {
  relay: string;          // ws://host:port or wss://...
  token: string;          // claim/pair token issued by relay owner
  port?: number;
  device: Device;
}

const CRITICAL_ACTIONS = new Set(['restart', 'shutdown', 'run_command', 'lock', 'sleep']);

/** How long a consent this device granted stays usable. */
const GRANT_TTL_MS = 60_000;

export class Agent {
  private ws?: WebSocket;
  private closed = false;

  /**
   * Control IDs this device approved through its own consent dialog, with
   * expiry. This is the only thing that counts as consent — the `consent`
   * field on an inbound request is written by whoever sent the request, so it
   * is never evidence that the user agreed to anything.
   */
  private readonly granted = new Map<string, number>();

  constructor(private readonly opts: Opts) {}

  private rememberGrant(controlId: string) {
    const now = Date.now();
    for (const [id, expiry] of this.granted) if (expiry <= now) this.granted.delete(id);
    this.granted.set(controlId, now + GRANT_TTL_MS);
  }

  /** Consume a grant for controlId; false if absent or expired. Single-use. */
  private consumeGrant(controlId: string): boolean {
    const expiry = this.granted.get(controlId);
    if (expiry === undefined) return false;
    this.granted.delete(controlId);
    return expiry > Date.now();
  }

  connect(): Promise<void> {
    const url = `${this.opts.relay}${this.opts.port ? `:${this.opts.port}` : ''}/`;
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      this.ws = ws;
      ws.on('open', () => {
        this.send(env(Msg.Hello, '', { token: this.opts.token, device: this.opts.device }));
        resolve();
      });
      ws.on('message', (raw) => this.onMessage(String(raw)));
      ws.on('close', () => this.scheduleReconnect());
      ws.on('error', (err) => reject(err));
    });
  }

  private scheduleReconnect() {
    if (this.closed) return;
    setTimeout(() => {
      this.connect().catch(() => this.scheduleReconnect());
    }, 3000);
  }

  private send(e: Envelope) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(e));
  }

  private onMessage(raw: string) {
    let e: Envelope;
    try { e = JSON.parse(raw); } catch { return; }
    switch (e.type) {
      case Msg.NotifyPush:
        void pl.notify(e.body?.title || 'VEDA', e.body?.body || '', e.body?.app || '').then(() => {
          this.send(env(Msg.NotifyAck, '', { instanceId: e.body?.instanceId ?? randomUUID() }));
        });
        break;
      case Msg.ConsentRequest:
        this.onConsentRequest(e.body as ConsentRequest);
        break;
      case Msg.ControlRequest:
        this.onControlRequest(e.body as ControlRequest, e.from || '');
        break;
    }
  }

  /** Confirm a risky remote action with the local user (OS-level consent). */
  private async onConsentRequest(r: ConsentRequest) {
    const ok = await pl.userConfirm(`${r.source} wants to ${r.action.toUpperCase()} this device.\nAllow?`, r.action);
    if (ok) this.rememberGrant(r.controlId);
    this.send(env(Msg.ConsentResult, '', { controlId: r.controlId, ok }));
    audit('consent', { controlId: r.controlId, ok, action: r.action, source: r.source });
  }

  private async onControlRequest(r: ControlRequest, from: string) {
    // Consent counts only if this device granted it, for this control id, just
    // now. r.consent is the requester's own claim and carries no weight.
    if (CRITICAL_ACTIONS.has(r.action) && !this.consumeGrant(r.controlId)) {
      const ok = await pl.userConfirm(`${from} wants to ${r.action.toUpperCase()} ${hostname()}.\nPermit?`, r.action);
      if (!ok) {
        this.send(env(Msg.ControlResult, from, { controlId: r.controlId, ok: false, error: 'denied by user' }));
        audit('denied', { controlId: r.controlId, action: r.action, from });
        return;
      }
    }
    audit('action', { controlId: r.controlId, action: r.action, from });
    try {
      const out = await this.execute(r.action, r.args || {});
      this.send(env(Msg.ControlResult, from, { controlId: r.controlId, ok: true, data: out || undefined }));
    } catch (err: any) {
      this.send(env(Msg.ControlResult, from, { controlId: r.controlId, ok: false, error: String(err?.message || err) }));
    }
  }

  private async execute(action: string, args: Record<string, any>): Promise<string | undefined> {
    switch (action) {
      case 'open_app': return pl.openApp(args.app || args.appPath || '', args.url);
      case 'lock': return await pl.lock();
      case 'sleep': return await pl.sleep();
      case 'restart': return await pl.restart(Number(args.seconds) || 10);
      case 'shutdown': return await pl.shutdown(Number(args.seconds) || 10);
      case 'set_volume': return await pl.setVolume(Number(args.volume ?? 50));
      case 'send_notify': await pl.notify(args.title || 'VEDA', args.body || '', args.app || ''); return 'sent';
      case 'run_command': {
        const r = await pl.runCommand(args.command || '');
        return `${r.ok ? 'ok' : 'err'}: ${r.stdout} ${r.stderr}`.trim();
      }
      default: throw new Error(`unknown action ${action}`);
    }
  }

  get connected(): boolean { return !!(this.ws && this.ws.readyState === WebSocket.OPEN); }

  close() { this.closed = true; this.ws?.close(); }
}

// Simple default-export + CLI entry, so the binary can be run directly.
if (process.argv[1] && (process.argv[1].endsWith('index.ts') || process.argv[1].endsWith('index.js'))) {
  const relay = process.env.VEDA_RELAY || 'ws://127.0.0.1';
  const token = process.env.VEDA_TOKEN || 'vayu-dev';
  const port = Number(process.env.VEDA_PORT || 8080);
  const agent = new Agent({
    relay,
    token,
    port,
    device: {
      id: `host-${hostname().replace(/[^a-zA-Z0-9]/gi, '-').toLowerCase()}`,
      name: hostname(),
      platform: pl.platform,
      os: process.platform,
      version: process.versions.node,
      capabilities: ['apps.open', 'system.lock', 'system.sleep', 'system.restart', 'system.shutdown', 'media.master', 'notify.send', 'terminal'],
    },
  });
  agent.connect().then(() => console.log(`VEDA agent connected to ${relay}:${port}`));
  const stop = () => { agent.close(); process.exit(0); };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  console.log(`VEDA agent (${process.platform}) — connect via VEDA_RELAY/VD_TOKEN/VD_PORT env or args`);
}