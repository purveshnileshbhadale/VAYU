// Shared VEDA wire protocol types (mirrors docs/PROTOCOL.md + relay-go/internal/message).
// This module is imported by agents and the dashboard; it must be kept in lockstep
// with the Go structs.

export interface Envelope {
  v: number;
  type: string;
  from: string;
  to?: string;
  id?: string;
  ts?: string;
  auth?: string;
  body?: any;
}

export interface Device {
  id: string;
  name: string;
  platform: string; // windows|macos|linux|android|ios|raspberrypi|tv|iot
  os?: string;
  version?: string;
  capabilities: string[];
}

export interface Hello { token: string; device: Device; }
export interface HelloAck { device: Device; devices: Device[]; }
export interface Status {
  cpu?: number; ram?: number; disk?: number; battery?: number;
  temp?: number; fans?: number; net?: string; app?: string; clipboard?: string; ts?: string;
}
export interface Presence { device: Device; online: boolean; }

export interface Notify { title: string; body?: string; app?: string; priority?: number; tags?: string; }
export interface NotifyAck { instanceId: string; }
export interface Dismiss { instanceId: string; }

export interface ControlRequest {
  controlId: string;
  action: string;
  args?: Record<string, any>;
  permission?: string;
  consent?: string; // requested | granted | denied
}
export interface ConsentRequest { controlId: string; action: string; source: string; seconds?: number; }
export interface ConsentResult { controlId: string; ok: boolean; }
export interface ControlResult { controlId: string; ok: boolean; data?: string; error?: string; }

export interface TerminalRequest { command: string; }
export interface TerminalResult { ok: boolean; exit?: number; stdout?: string; stderr?: string; }

export interface Fault { code: string; fault: string; msg?: string; }

// Message type constants used across the stack.
export const Msg = {
  Hello: 'hello',
  HelloAck: 'hello.ack',
  Status: 'status',
  Presence: 'presence',
  NotifyRequest: 'notify.request',
  NotifyPush: 'notify.push',
  NotifyAck: 'notify.ack',
  NotifyDismiss: 'notify.dismiss',
  ControlRequest: 'control.request',
  ControlResult: 'control.result',
  ConsentRequest: 'control.consent.request',
  ConsentResult: 'control.consent.result',
  TerminalRequest: 'terminal.request',
  Ping: 'ping',
  Pong: 'pong',
} as const;

export function env(type: string, to: string, body?: any, from = ''): Envelope {
  return { v: 1, type, from, to, body, ts: new Date().toISOString() };
}