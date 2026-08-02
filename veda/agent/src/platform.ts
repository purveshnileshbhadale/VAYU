// Platform adapters: notification + control execution per OS.
// All remote actions run through the OS's own APIs/CLIs; the agent never
// elevates privilege, and dangerous actions come back gated by consent.
import { exec } from 'node:child_process';
import { hostname } from 'node:os';

export type Platform = 'win32' | 'darwin' | 'linux';

export const platform: Platform = process.platform as Platform;

/** Show a desktop notification. */
export async function notify(title: string, body: string, app: string): Promise<void> {
  const t = title.slice(0, 128).replace(/["\r\n]/g, ' ');
  const b = body.slice(0, 512).replace(/["\r\n]/g, ' ');
  const cmd =
    platform === 'win32'
      ? `powershell -NoProfile -Command "$x=New-Object -ComObject WScript.Shell;$x.Popup('${b}',8,'${app ? app.toUpperCase() + ' - ' : ''}${t}',48)"`
      : platform === 'darwin'
        ? `osascript -e 'display notification "${b}" with title "${t}"'`
        : `notify-send "${t}" "${b}"`;
  return run(cmd).then(() => undefined);
}

/** Open an app (by name/candidate path or URL) on the local OS. */
export async function openApp(app: string, url?: string): Promise<string> {
  const target = url || app;
  const cmd =
    platform === 'darwin' ? `open -a "${safe(target)}"` :
      platform === 'win32' ? `start "" "${safe(target)}"` :
        target.startsWith('http') ? `xdg-open "${safe(target)}"` : `gtk-launch "${safe(target)}" 2>/dev/null || xdg-open "${safe(target)}"`;
  return run(cmd).then(() => `launched ${target}`);
}

/** Lock the workstation. */
export function lock(): Promise<string> {
  const cmd =
    platform === 'win32' ? `rundll32.exe user32.dll,LockWorkStation` :
      platform === 'darwin' ? `osascript -e 'tell app "System Events" to keystroke "q" using {control down, command down}'` :
        // best-effort on X11 session
        `loginctl lock-session || true; xdg-screensaver lock 2>/dev/null || true`;
  return run(cmd).then(() => 'locked');
}

/** Suspend the machine. */
export function sleep(): Promise<string> {
  const cmd =
    platform === 'win32' ? `rundll32.exe powrprof.dll,SetSuspendState 0,1,0` :
      platform === 'darwin' ? `pmset sleepnow` :
        `loginctl suspend || systemctl suspend`;
  return run(cmd).then(() => 'sleeping');
}

/** Restart. NOTE: caller must have consent. */
export function restart(seconds = 10): Promise<string> {
  const cmd =
    platform === 'win32' ? `shutdown /r /t ${seconds}` :
      platform === 'darwin' ? `osascript -e 'tell app "System Events" to restart'` :
        `shutdown -r +${Math.max(0, Math.ceil(seconds / 60)) || 1}`;
  return run(cmd).then(() => `restart in ${seconds}s`);
}

/** Shutdown. NOTE: caller must have consent. */
export function shutdown(seconds = 10): Promise<string> {
  const cmd =
    platform === 'win32' ? `shutdown /s /t ${seconds}` :
      platform === 'darwin' ? `osascript -e 'tell app "System Events" to shut down'` :
        `shutdown -h +${Math.max(1, Math.ceil(seconds / 60))}`;
  return run(cmd).then(() => `shutdown in ${seconds}s`);
}

/** Set master volume 0..100. Best-effort, never fails the request chain. */
export function setVolume(v: number): Promise<string> {
  const k = Math.max(0, Math.min(100, Math.round(v)));
  const cmd =
    platform === 'win32'
      ? `powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; for($i=0;$i -lt ${k};$i+=2){$ws.SendKeys([char]175)} for($i=100;$i -gt ${k};$i-=2){$ws.SendKeys([char]174)}"`
      : platform === 'darwin'
        ? `osascript -e 'set volume output volume ${k}'`
        : `amixer set Master ${k}% 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ ${k}%`;
  return run(cmd).then(() => `volume ${k}`);
}

/** Run a shell command (confirmation-gated upstream). */
export async function runCommand(cmd: string): Promise<{ ok: boolean; stdout: string; stderr: string; exit: number }> {
  return new Promise((resolve) => {
    exec(cmd, { timeout: 5000, encoding: 'utf8', windowsHide: true }, (err, stdout, stderr) => {
      resolve({ ok: !err, stdout: (stdout || '').slice(0, 2000), stderr: (stderr || '').slice(0, 2000), exit: err ? 1 : 0 });
    });
  });
}

/** Read lightweight device stats to report as `status`. */
export async function collectStatus(): Promise<Record<string, unknown>> {
  // v1 status = reachability + identity. CPU/RAM/battery come in the status milestone.
  return { ts: new Date().toISOString(), platform, host: hostname() };
}

/** Ask the local user to approve a remote action (OS-native consent dialog). */
export function userConfirm(prompt: string, tag: string): Promise<boolean> {
  const t = prompt.slice(0, 220).replace(/["\r\n]/g, ' ');
  const cmd =
    platform === 'win32'
      ? `powershell -NoProfile -Command "$a=(New-Object -ComObject WScript.Shell).Popup('${t}',0,'VEDA - consent (${tag})',52); if($a -eq 6){exit 0}else{exit 1}"`
      : platform === 'darwin'
        ? `osascript -e 'display dialog "${t}" buttons {"Deny","Allow"} default button "Allow" with title "VEDA (${tag})"'`
        : `notify-send -A allow=Allow -A deny=Deny "${tag}: ${t}" . && read -n1`;

  return new Promise((resolve) => {
    exec(cmd, { timeout: 15000, windowsHide: true }, (err) => resolve(err === null));
  });
}

function safe(s: string): string {
  return s.replace(/["'\\$`]/g, '').slice(0, 256);
}

function run(cmd: string): Promise<string> {
  return new Promise((resolve, reject) => {
    exec(cmd, { timeout: 10000, windowsHide: true }, (err) => (err ? reject(err) : resolve('')));
  });
}