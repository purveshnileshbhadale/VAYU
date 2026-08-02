// Node relay — protocol mirror of relay-go, for dev/test machines without Go.
// Connect dashboard & agents here and the same envelopes work against both.
import { WebSocketServer } from 'ws';
import { randomUUID } from 'node:crypto';
import type { Envelope, Device, Hello, HelloAck, Notify, Dismiss, ControlRequest, ConsentResult, ControlResult, Fault } from '../../protocol/index.js';
import { Msg, env } from '../../protocol/index.js';

interface Peer {
  ws: WebSocket;
  kind: 'device' | 'unknown';
  deviceId?: string;
  device?: Device;
}

const CLAIMS = process.env.VEDA_TOKEN || (process.argv.find((a) => a.startsWith('--token='))?.split('=')[1]) || 'vayu-dev';

const peers = new Map<string, Peer>();       // deviceId -> peer
const byId = new Map<any, Peer>();
const consents = new Map<string, (ok: boolean) => void>();

function send(p: Peer | undefined, e: Envelope) {
  if (!p || p.ws.readyState !== 1) return;
  p.ws.send(JSON.stringify(e));
}

function handle(e: Envelope, ws: any) {
  const p = byId.get(ws);
  switch (e.type) {
    case Msg.Hello: {
      const h = e.body as Hello;
      if (h.token !== CLAIMS) {
        send(p, { v: 1, type: 'fault', from: 'relay', body: { code: '401', fault: 'bad_token' } } as Envelope);
        return;
      }
      const id = h.device.id || randomUUID();
      const np: Peer = { ws, kind: 'device', deviceId: id, device: h.device };
      byId.set(ws, np);
      peers.set(id, np);
      const ack: HelloAck = {
        device: h.device,
        devices: [...peers.values()].filter((x) => x.device).map((x) => x.device!),
      };
      send(np, { v: 1, type: Msg.HelloAck, to: id, body: ack, from: 'relay' } as Envelope);
      broadcastPresence();
      break;
    }
    case Msg.ControlRequest: {
      if (!p?.deviceId) break;
      const cr = e.body as ControlRequest;
      const target = peers.get(e.to || '');
      if (!target) {
        send(p, { v: 1, type: 'fault', from: 'relay', to: p.deviceId, body: { code: '503', fault: 'target_offline' } } as Envelope);
        break;
      }
      if (cr.consent !== 'granted' && isCritical(cr.action)) {
        const gate = (ok: boolean) => {
          if (!ok) {
            send(p, { v: 1, type: Msg.ControlResult, from: 'relay', to: p.deviceId, body: { controlId: cr.controlId, ok: false, error: 'consent denied' } } as Envelope);
            return;
          }
          send(target, { v: 1, type: Msg.ControlRequest, from: p.deviceId, to: target.deviceId, body: { ...cr, consent: 'granted' } } as Envelope);
        };
        consents.set(cr.controlId, gate);
        send(target, { v: 1, type: Msg.ConsentRequest, from: p.deviceId, to: target.deviceId, body: { controlId: cr.controlId, action: cr.action, source: p.deviceId } } as Envelope);
        setTimeout(() => {
          if (consents.has(cr.controlId)) {
            consents.delete(cr.controlId);
            send(p, { v: 1, type: Msg.ControlResult, from: 'relay', to: p.deviceId, body: { controlId: cr.controlId, ok: false, error: 'consent timeout' } } as Envelope);
          }
        }, 30000);
      } else {
        send(target, { v: 1, type: Msg.ControlRequest, from: p.deviceId, to: target.deviceId, body: { ...cr, consent: 'granted' } } as Envelope);
      }
      break;
    }
    case Msg.ConsentResult: {
      const r = e.body as ConsentResult;
      const gate = consents.get(r.controlId);
      if (gate) { consents.delete(r.controlId); gate(r.ok); }
      break;
    }
    case Msg.ControlResult: {
      if (!p?.deviceId) break;
      const r = e.body as ControlResult;
      const requester = peers.get(e.to || '');
      send(requester, { v: 1, type: Msg.ControlResult, from: p.deviceId, to: requester?.deviceId, body: r } as Envelope);
      break;
    }
    case Msg.NotifyRequest: {
      if (!p?.deviceId) break;
      const n = e.body as Notify;
      const target = peers.get(e.to || '');
      if (!target) { send(p, { v: 1, type: 'fault', from: 'relay', to: p.deviceId, body: { code: '503', fault: 'target_offline' } } as Envelope); break; }
      send(target, { v: 1, type: Msg.NotifyPush, from: p.deviceId, to: target.deviceId, body: n } as Envelope);
      break;
    }
    case Msg.NotifyDismiss: {
      if (!p?.deviceId) break;
      const n = e.body as Dismiss;
      for (const q of peers.values()) send(q, { v: 1, type: Msg.NotifyDismiss, from: p.deviceId, to: q.deviceId, body: n } as Envelope);
      break;
    }
  }
}

// Aligned with relay-go/internal/policy: only destructive/system actions gate.
function isCritical(action: string) {
  return ['restart', 'shutdown', 'run_command'].includes(action);
}

function broadcastPresence(): void {
  const list = [...peers.values()].filter((x) => x.device).map((x) => x.device!);
  for (const q of peers.values()) {
    send(q, { v: 1, type: Msg.Presence, from: 'relay', to: q.deviceId, body: { devices: list } } as Envelope);
  }
}

export function start(port = 8080) {
  const wss = new WebSocketServer({ port });
  wss.on('connection', (ws) => {
    byId.set(ws, { ws, kind: 'unknown' } as unknown as Peer);
    ws.on('message', (raw) => {
      let e: Envelope;
      try { e = JSON.parse(String(raw)); } catch { return; }
      handle(e, ws);
    });
    ws.on('close', () => {
      const p = byId.get(ws);
      if (p?.deviceId) peers.delete(p.deviceId);
      byId.delete(ws);
    });
  });
  console.log(`VEDA node relay listening on :${port} (claim token '${CLAIMS}')`);
  return wss;
}

if (process.argv[1] && (process.argv[1].endsWith('server.ts') || process.argv[1].endsWith('server.js'))) start();