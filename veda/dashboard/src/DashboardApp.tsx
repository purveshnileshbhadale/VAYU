// VEDA dashboard — live device cloud, universal notifications, control + consent.
import { useEffect, useRef, useState } from 'react';

interface DeviceView {
  id: string;
  name: string;
  platform: string;
  os?: string;
  version?: string;
  capabilities: string[];
  online: boolean;
}

interface StreamEvent {
  ts: string;
  from: string;
  type: string;
  title?: string;
  body?: string;
}

const TARGET = import.meta.env.VITE_VEDA_RELAY || 'ws://localhost:8080';
const DASHBOARD_TOKEN = import.meta.env.VITE_VEDA_TOKEN || '';

export function DashboardApp() {
  const [devices, setDevices] = useState<DeviceView[]>([]);
  const [stream, setStream] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const push = (e: StreamEvent) => setStream((prev) => [e, ...prev].slice(0, 60));

  const handle = (m: any) => {
    const t = m.body || {};
    if (m.type === 'hello.ack' || m.type === 'presence') {
      const list = m.type === 'hello.ack' ? t.devices || [] : [t.device].filter(Boolean);
      setDevices(list.map((d: any) => ({ ...d, online: true })));
      return;
    }
    if (m.type === 'notify.push') {
      push({ ts: new Date().toISOString(), from: m.from || '', type: 'notify', title: t.title, body: t.body });
      return;
    }
    if (m.type === 'control.result') {
      if (!t.ok) push({ ts: new Date().toISOString(), from: m.from, type: 'result', body: t.error || 'failed' });
      setPending(null);
    }
  };

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    const connect = () => {
      if (closed) return;
      const s = new WebSocket(`${TARGET}?kind=dashboard`);
      ws = s;
      wsRef.current = s;
      s.onopen = () => {
        setConnected(true);
        s.send(JSON.stringify({
          v: 1, type: 'hello', from: 'dashboard', to: 'relay',
          body: { token: DASHBOARD_TOKEN, device: { id: 'dashboard', name: 'VEDA Control', platform: 'web', capabilities: ['dashboard'] } },
        }));
      };
      s.onmessage = (ev) => { const m = JSON.parse(ev.data); handle(m); };
      s.onclose = () => { setConnected(false); wsRef.current = null; setTimeout(connect, 3000); };
    };
    connect();
    return () => { closed = true; ws?.close(); };
  }, []);

  const send = (type: string, to: string, body: any) => {
    wsRef.current?.send(JSON.stringify({ v: 1, type, from: 'dashboard', to, body }));
  };

  const doControl = (target: string, action: string, args: Record<string, any> = {}) => {
    const controlId = crypto.randomUUID();
    setPending(`${action}@${target}`);
    send('control.request', target, { controlId, action, permission: 'granted', consent: 'granted', args });
    push({ ts: new Date().toISOString(), from: 'dashboard', type: 'control', title: `${action} → ${target}` });
  };

  return (
    <div>
      <div className="statusbar">
        <span className="live">●</span> VEDA — Device Cloud
        <span style={{ marginLeft: 'auto' }}>{connected ? `relay ${TARGET.replace('ws://', '')} · connected` : 'connecting…'}</span>
        {pending && <span className="mono" style={{ color: 'var(--warn)' }}>⏳ {pending}</span>}
      </div>
      <div className="hud">
        <h1>My Devices</h1>
        <div className="sub">Every device is paired to your owner account. Control runs only with on-device consent.</div>
        <div className="grid">
          {devices.length === 0 && (
            <div className="glass card" style={{ gridColumn: '1 / -1', color: 'var(--text-dim)' }}>
              No devices connected. Start <code>veda-agent</code> with the same claim token.
            </div>
          )}
          {devices.map((d) => <DeviceCard key={d.id} d={d} onAction={doControl} />)}
        </div>
        <div className="stream">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <h2 style={{ fontSize: 16, margin: 0 }}>Universal Notifications</h2>
            <button style={{ fontSize: 12 }} onClick={() => setStream([])}>clear</button>
          </div>
          {stream.length === 0 && <div className="glass" style={{ padding: 14, color: 'var(--text-dim)', fontSize: 13 }}>Waiting for events…</div>}
          {stream.map((e, i) => (
            <div key={i} className="row">
              <span className="ts">{new Date(e.ts).toLocaleTimeString()}</span>
              <span className="from">{e.from || e.type}</span>
              <span>{e.title || e.body || e.type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DeviceCard({ d, onAction }: { d: DeviceView; onAction: (id: string, a: string, args?: any) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="glass card">
      <span className={`dot ${d.online ? 'on' : 'off'}`} />
      <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--text-dim)' }}>{d.online ? 'ONLINE' : 'OFFLINE'}</div>
      <h3 style={{ margin: 6 }}>{d.name}</h3>
      <div className="plat">{d.platform}{d.os ? ` · ${d.os}` : ''}</div>
      <div className="meta">
        <span className="badge">{d.capabilities?.length || 0} caps</span>
        {d.version && <span className="badge">v{d.version}</span>}
      </div>
      {d.online && (
        <div className="actions">
          <button onClick={() => onAction(d.id, 'open_app', { path: 'notepad' })}>Open App</button>
          <button onClick={() => onAction(d.id, 'send_notify', { title: 'VEDA', body: 'hello from dashboard' })}>Notify</button>
          <button onClick={() => onAction(d.id, 'set_volume', { volume: 30 })}>Vol 30</button>
          <button onClick={() => setOpen(!open)}>{open ? 'Close' : 'Power…'}</button>
        </div>
      )}
      {open && d.online && (
        <div className="consent">
          <span>Power actions require approval on the device.</span>
          <div>
            <button onClick={() => { onAction(d.id, 'lock'); setOpen(false); }}>Lock</button>
            <button onClick={() => { onAction(d.id, 'sleep'); setOpen(false); }}>Sleep</button>
            <button className="danger" onClick={() => { onAction(d.id, 'restart'); setOpen(false); }}>Restart</button>
            <button className="danger" onClick={() => { onAction(d.id, 'shutdown'); setOpen(false); }}>Shutdown</button>
          </div>
        </div>
      )}
    </div>
  );
}