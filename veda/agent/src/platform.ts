// Platform adapters: notification + control execution per OS.
// All remote actions run through the OS's own APIs/CLIs; the agent never
// elevates privilege, and dangerous actions come back gated by consent.
//
// Nothing in this file builds a shell command string out of remote input.
// Every helper spawns a binary directly with an argv array (execFile), so
// quoting is never the thing standing between a notification title and code
// execution. Where a scripting host is unavoidable (PowerShell, osascript),
// remote values are passed as environment variables or as script arguments
// and read back by name inside the script — never interpolated into it.
import { execFile } from 'node:child_process';
import { hostname } from 'node:os';

export type Platform = 'win32' | 'darwin' | 'linux';

export const platform: Platform = process.platform as Platform;

/** Spawn a binary with an argv array. Rejects on non-zero exit. */
function run(file: string, args: string[], opts: { timeout?: number; env?: NodeJS.ProcessEnv } = {}): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(
      file,
      args,
      { timeout: opts.timeout ?? 10_000, windowsHide: true, env: opts.env ?? process.env, encoding: 'utf8' },
      (err, stdout) => (err ? reject(err) : resolve(stdout || '')),
    );
  });
}

/** Like run(), but resolves false instead of rejecting. */
function tryRun(file: string, args: string[], opts?: { timeout?: number; env?: NodeJS.ProcessEnv }): Promise<boolean> {
  return run(file, args, opts).then(() => true, () => false);
}

/**
 * Run a PowerShell script that reads its inputs from the environment.
 * The script text is a constant; `vars` carries the untrusted values.
 */
function powershell(script: string, vars: Record<string, string> = {}, timeout = 10_000): Promise<string> {
  return run('powershell', ['-NoProfile', '-NonInteractive', '-Command', script], {
    timeout,
    env: { ...process.env, ...vars },
  });
}

/**
 * Run an AppleScript that takes its inputs as arguments.
 * `body` is wrapped in `on run argv`, so values arrive as `item N of argv`
 * rather than as text spliced into the script.
 */
function osascript(body: string, args: string[] = [], timeout = 10_000): Promise<string> {
  const script = `on run argv\n${body}\nend run`;
  return run('osascript', ['-e', script, ...args], { timeout });
}

/** Show a desktop notification. */
export async function notify(title: string, body: string, app: string): Promise<void> {
  const t = (app ? `${app.toUpperCase()} - ${title}` : title).slice(0, 128);
  const b = body.slice(0, 512);

  if (platform === 'win32') {
    await powershell(
      '$x = New-Object -ComObject WScript.Shell; $x.Popup($env:VEDA_BODY, 8, $env:VEDA_TITLE, 48)',
      { VEDA_TITLE: t, VEDA_BODY: b },
    ).catch(() => undefined);
    return;
  }
  if (platform === 'darwin') {
    await osascript('display notification (item 1 of argv) with title (item 2 of argv)', [b, t]).catch(() => undefined);
    return;
  }
  await tryRun('notify-send', ['--', t, b]);
}

/** Open an app (by name/candidate path or URL) on the local OS. */
export async function openApp(app: string, url?: string): Promise<string> {
  const target = (url || app).slice(0, 512);
  if (!target) throw new Error('no app or url given');

  if (platform === 'darwin') {
    await run('open', ['-a', target]);
  } else if (platform === 'win32') {
    // `start` is a cmd builtin; the empty string is the window title slot.
    await run('cmd', ['/c', 'start', '', target]);
  } else if (/^https?:\/\//i.test(target)) {
    await run('xdg-open', [target]);
  } else if (!(await tryRun('gtk-launch', [target]))) {
    await run('xdg-open', [target]);
  }
  return `launched ${target}`;
}

/** Lock the workstation. */
export async function lock(): Promise<string> {
  if (platform === 'win32') {
    await run('rundll32.exe', ['user32.dll,LockWorkStation']);
  } else if (platform === 'darwin') {
    await osascript('tell application "System Events" to keystroke "q" using {control down, command down}');
  } else if (!(await tryRun('loginctl', ['lock-session']))) {
    await tryRun('xdg-screensaver', ['lock']);
  }
  return 'locked';
}

/** Suspend the machine. */
export async function sleep(): Promise<string> {
  if (platform === 'win32') {
    await run('rundll32.exe', ['powrprof.dll,SetSuspendState', '0,1,0']);
  } else if (platform === 'darwin') {
    await run('pmset', ['sleepnow']);
  } else if (!(await tryRun('loginctl', ['suspend']))) {
    await tryRun('systemctl', ['suspend']);
  }
  return 'sleeping';
}

/** Restart. NOTE: caller must have consent. */
export async function restart(seconds = 10): Promise<string> {
  const s = clampSeconds(seconds);
  if (platform === 'win32') {
    await run('shutdown', ['/r', '/t', String(s)]);
  } else if (platform === 'darwin') {
    await osascript('tell application "System Events" to restart');
  } else {
    await run('shutdown', ['-r', `+${toMinutes(s)}`]);
  }
  return `restart in ${s}s`;
}

/** Shutdown. NOTE: caller must have consent. */
export async function shutdown(seconds = 10): Promise<string> {
  const s = clampSeconds(seconds);
  if (platform === 'win32') {
    await run('shutdown', ['/s', '/t', String(s)]);
  } else if (platform === 'darwin') {
    await osascript('tell application "System Events" to shut down');
  } else {
    await run('shutdown', ['-h', `+${Math.max(1, toMinutes(s))}`]);
  }
  return `shutdown in ${s}s`;
}

/** Set master volume 0..100. Best-effort, never fails the request chain. */
export async function setVolume(v: number): Promise<string> {
  const k = Math.max(0, Math.min(100, Math.round(Number(v) || 0)));
  if (platform === 'win32') {
    await powershell(
      '$k = [int]$env:VEDA_VOL; $ws = New-Object -ComObject WScript.Shell;' +
        ' for ($i = 0; $i -lt $k; $i += 2) { $ws.SendKeys([char]175) }' +
        ' for ($i = 100; $i -gt $k; $i -= 2) { $ws.SendKeys([char]174) }',
      { VEDA_VOL: String(k) },
    ).catch(() => undefined);
  } else if (platform === 'darwin') {
    await osascript('set volume output volume (item 1 of argv as integer)', [String(k)]).catch(() => undefined);
  } else if (!(await tryRun('amixer', ['set', 'Master', `${k}%`]))) {
    await tryRun('pactl', ['set-sink-volume', '@DEFAULT_SINK@', `${k}%`]);
  }
  return `volume ${k}`;
}

/** Run a shell command (confirmation-gated upstream). */
export async function runCommand(cmd: string): Promise<{ ok: boolean; stdout: string; stderr: string; exit: number }> {
  // This is the one place a shell is the point of the call rather than an
  // accident of string building, so it stays explicit: the caller is asking
  // for a shell. Every other export in this file avoids one.
  const shell = platform === 'win32' ? process.env.ComSpec || 'cmd.exe' : '/bin/sh';
  const args = platform === 'win32' ? ['/d', '/s', '/c', cmd] : ['-c', cmd];
  return new Promise((resolve) => {
    execFile(shell, args, { timeout: 5000, encoding: 'utf8', windowsHide: true }, (err, stdout, stderr) => {
      resolve({
        ok: !err,
        stdout: (stdout || '').slice(0, 2000),
        stderr: (stderr || '').slice(0, 2000),
        exit: err ? 1 : 0,
      });
    });
  });
}

/** Read lightweight device stats to report as `status`. */
export async function collectStatus(): Promise<Record<string, unknown>> {
  // v1 status = reachability + identity. CPU/RAM/battery come in the status milestone.
  return { ts: new Date().toISOString(), platform, host: hostname() };
}

/**
 * Ask the local user to approve a remote action (OS-native consent dialog).
 *
 * Fails closed: if no dialog can be shown, the answer is "no". A consent
 * prompt that cannot be displayed must never read as approval.
 */
export function userConfirm(prompt: string, tag: string): Promise<boolean> {
  const text = prompt.slice(0, 220);
  const title = `VEDA - consent (${tag.slice(0, 40)})`;

  if (platform === 'win32') {
    // Popup returns 6 for Yes; exit non-zero for anything else.
    return powershell(
      '$a = (New-Object -ComObject WScript.Shell).Popup($env:VEDA_PROMPT, 0, $env:VEDA_TITLE, 52);' +
        ' if ($a -eq 6) { exit 0 } else { exit 1 }',
      { VEDA_PROMPT: text, VEDA_TITLE: title },
      20_000,
    ).then(() => true, () => false);
  }

  if (platform === 'darwin') {
    // Default to Deny: the safe button should be the one a stray Return hits.
    return osascript(
      'display dialog (item 1 of argv) buttons {"Deny", "Allow"} default button "Deny"' +
        ' with title (item 2 of argv) with icon caution',
      [text, title],
      20_000,
    ).then((out) => /button returned:Allow/.test(out), () => false);
  }

  return linuxConfirm(text, title);
}

/** Linux consent via whichever dialog helper is installed; denies if none is. */
async function linuxConfirm(text: string, title: string): Promise<boolean> {
  if (await tryRun('zenity', ['--question', '--title', title, '--text', text], { timeout: 20_000 })) return true;
  if (await tryRun('kdialog', ['--title', title, '--yesno', text], { timeout: 20_000 })) return true;
  // No dialog helper available — surface the attempt, then deny.
  await tryRun('notify-send', ['--', title, `${text} (denied: no consent dialog available)`]);
  return false;
}

function clampSeconds(seconds: number): number {
  const s = Math.round(Number(seconds));
  return Number.isFinite(s) ? Math.max(0, Math.min(86_400, s)) : 10;
}

function toMinutes(seconds: number): number {
  return Math.max(0, Math.ceil(seconds / 60)) || 1;
}
