// End-to-end smoke test for the node relay + agent flow (run with tsx).
// Simulates two devices + a dashboard, then exercises notify + consent-gated control.
import WebSocket from 'ws';
import { randomUUID } from 'node:crypto';

const URL = process.env.VEDA_RELAY_URL || 'ws://127.0.0.1:8080/ws';
const TOKEN = process.env.VEDA_TOKEN || 'vayu-dev';

interface Peer {
  id: string;
  ws: WebSocket;
  inbox: any[];
}

function connect(kind: 'device' | 'dashboard', id: string): Promise<Peer> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${URL}?kind=${kind}`);
    const inbox: any[] = [];
    ws.on('message', (raw) => inbox.push(JSON.parse(String(raw))));
    const send = (type: string, top: string, body: any, from = id) =>
      ws.send(JSON.stringify({ v: 1, type, from, to: top, body }));
    ws.on('open', () => resolve({ id, ws, inbox, send } as unknown as Peer));
    ws.on('error', reject);
  });
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function hello(p: Peer, platform: string, caps: string[]) {
  p.send('hello', 'relay', {
    token: TOKEN,
    device: { id: p.id, name: p.id, platform, capabilities: caps },
  });
}

export async function main() {
  const laptop = await connect('device', 'device-laptop');
  const phone = await connect('device', 'device-phone');
  const dash = await connect('dashboard', 'dashboard');
  await sleep(150);

  await hello(laptop, 'windows', ['core', 'notify.send', 'system.lock', 'system.sleep', 'system.restart']);
  await hello(phone, 'android', ['core', 'notify.receive', 'system.lock']);
  await hello(dash, 'web', ['dashboard', 'control.request']);
  await sleep(200);

  // 1) universal notification laptop -> phone
  laptop.send('notify.request', 'device-phone', { title: 'Build done', body: 'tests green' });
  await sleep(300);
  const push = phone.inbox.find((m) => m.type === 'notify.push');
  if (!push) throw new Error('phone did not receive notify');
  console.log('OK notify.request -> phone', push.body.title);

  // 1b) dismiss fan-out: phone dismisses, laptop should see it
  phone.send('notify.dismiss', '*', { instanceId: push.body.instanceId || 'x' });
  await sleep(200);

  // 2) consent-gated control: dashboard restarts phone (critical => consent gate)
  const controlId = randomUUID();
  dash.send('control.request', 'device-phone', { controlId, action: 'restart', permission: 'system.restart', consent: 'requested', args: {} });
  await sleep(300);
  const consentReq = phone.inbox.find((m) => m.type === 'control.consent.request');
  if (!consentReq) throw new Error('consent gate did not fire for restart');
  // user approves on the phone
  phone.send('control.consent.result', '', { controlId, ok: true });
  await sleep(300);
  const ctl = phone.inbox.find((m) => m.type === 'control.request' && m.body?.action === 'restart');
  if (!ctl) throw new Error('control not forwarded after consent');
  console.log('OK consent gate -> control forwarded to phone', ctl.body.action);

  // 3) control result back to dashboard
  phone.send('control.result', 'dashboard', { controlId, ok: true, data: 'restarting' });
  await sleep(300);
  const res = dash.inbox.find((m) => m.type === 'control.result');
  if (!res || !res.body?.ok) throw new Error('control.result missing');
  console.log('OK control result delivered:', res.body.data);

  // 4) non-critical action (lock) dispatches without the gate
  dash.send('control.request', 'device-phone', { controlId: randomUUID(), action: 'lock', permission: 'system.lock', consent: 'requested', args: {} });
  await sleep(300);
  const lk = phone.inbox.find((m) => m.type === 'control.request' && m.body?.action === 'lock');
  if (!lk) throw new Error('non-critical control did not dispatch without gate');
  console.log('OK non-critical control dispatched without consent gate');

  console.log('ALL PASS');
  laptop.ws.close(); phone.ws.close(); dash.ws.close();
}

if (process.argv[1] && (process.argv[1].endsWith('smoke.ts') || process.argv[1].endsWith('smoke.js'))) {
  main().then(() => process.exit(0)).catch((e) => { console.error('FAIL:', e.message); process.exit(1); });
}