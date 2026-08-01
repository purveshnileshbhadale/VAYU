import json, threading, socket, os, sys, tempfile, time, queue, subprocess, urllib.request, zipfile, secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>VAYU Remote</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#05050a;color:#d0d0e0;min-height:100dvh;display:flex;flex-direction:column;overflow:hidden}
.hologram-banner{width:100%;height:100px;position:relative;flex-shrink:0;overflow:hidden;background:linear-gradient(180deg,#05050a 0%,#080818 50%,#0a0a1a 100%)}
.hologram-banner canvas{width:100%;height:100%;display:block}
.header{background:linear-gradient(135deg,#0a0a1a,#0d0d24);padding:8px 16px 8px;border-bottom:1px solid rgba(0,212,255,0.12);display:flex;align-items:center;gap:10px;flex-shrink:0}
.header svg{flex-shrink:0}
.header h1{font-size:16px;font-weight:700;letter-spacing:1px;background:linear-gradient(90deg,#00d4ff,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.status-badge{display:inline-flex;align-items:center;gap:5px;margin-left:auto;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;padding:3px 10px;border-radius:20px;background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.15)}
.status-dot{width:7px;height:7px;border-radius:50%;animation:pulse 1.5s infinite}
.status-dot.listening{background:#10b981;box-shadow:0 0 6px #10b981}
.status-dot.speaking{background:#f59e0b;box-shadow:0 0 6px #f59e0b}
.status-dot.thinking{background:#6366f1;box-shadow:0 0 6px #6366f1}
.status-dot.offline{background:#ef4444;box-shadow:0 0 6px #ef4444}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.quick-actions{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:10px 12px;flex-shrink:0}
.q-btn{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:8px 4px;color:#b0b0c8;font-size:10px;font-weight:500;text-align:center;cursor:pointer;transition:all 0.15s;-webkit-tap-highlight-color:transparent}
.q-btn:active{background:rgba(0,212,255,0.12);border-color:rgba(0,212,255,0.3);transform:scale(0.95)}
.q-btn .icon{font-size:18px;display:block;margin-bottom:2px}
.log-area{flex:1;overflow-y:auto;padding:10px 12px;display:flex;flex-direction:column;gap:6px;min-height:0}
.log-entry{background:rgba(255,255,255,0.03);border-radius:8px;padding:8px 10px;font-size:12px;line-height:1.4;border-left:3px solid transparent;word-break:break-word;animation:fadeIn 0.2s}
.log-entry.user{border-left-color:#00d4ff}
.log-entry.vayu{border-left-color:#a78bfa}
.log-entry .label{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px}
.log-entry.user .label{color:#00d4ff}
.log-entry.vayu .label{color:#a78bfa}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.input-area{background:#0a0a18;border-top:1px solid rgba(0,212,255,0.08);padding:10px 12px;display:flex;gap:8px;align-items:flex-end;flex-shrink:0}
.input-area input{flex:1;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:10px 14px;color:#d0d0e0;font-size:14px;outline:none;transition:border-color 0.2s}
.input-area input:focus{border-color:rgba(0,212,255,0.4)}
.input-area input::placeholder{color:#505070}
.input-area button{width:42px;height:42px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.15s;flex-shrink:0;-webkit-tap-highlight-color:transparent}
.btn-send{background:linear-gradient(135deg,#00d4ff,#0090cc);color:#fff}
.btn-send:active{transform:scale(0.9)}
.btn-mic{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);color:#b0b0c8}
.btn-mic.recording{background:rgba(239,68,68,0.2);border-color:#ef4444;color:#ef4444;animation:micPulse 0.8s infinite}
.btn-voice{background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);color:#34d399}
.btn-voice.listening{background:rgba(16,185,129,0.25);border-color:#10b981;color:#10b981;animation:micPulse 0.8s infinite}
@keyframes micPulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.3)}50%{box-shadow:0 0 0 8px rgba(239,68,68,0)}}
.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.85);color:#fff;padding:8px 16px;border-radius:20px;font-size:12px;pointer-events:none;opacity:0;transition:opacity 0.3s;z-index:100}
.touchpad{flex-shrink:0;padding:0 12px 6px;height:140px}
.touchpad-inner{width:100%;height:100%;background:rgba(0,212,255,0.03);border:1px solid rgba(0,212,255,0.12);border-radius:12px;display:flex;align-items:center;justify-content:center;position:relative;touch-action:none;cursor:crosshair}
.touchpad-hint{color:#404060;font-size:10px;pointer-events:none}
.cam-on{background:rgba(16,185,129,0.15)!important;border-color:#10b981!important;color:#10b981!important}
.cur-on{background:rgba(99,102,241,0.15)!important;border-color:#6366f1!important;color:#818cf8!important}
.gesture-bar{flex-shrink:0;padding:2px 12px 4px;display:flex;align-items:center;gap:6px;font-size:10px;color:#505070}
.gesture-bar .cur-gesture{color:#00d4ff;font-weight:600;font-size:11px}
.gesture-ref{flex-shrink:0;padding:0 12px;overflow:hidden;max-height:0;transition:max-height 0.3s;display:flex;flex-wrap:wrap;gap:3px}
.gesture-ref.open{max-height:400px;padding:6px 12px}
.g-ref-btn{font-size:9px;color:#404060;cursor:pointer;text-align:center;padding:2px 0 4px;flex-shrink:0}
.g-ref-btn:hover{color:#00d4ff}
.gesture-item{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:3px 6px;font-size:9px;display:flex;gap:4px;align-items:center;white-space:nowrap;color:#808098}
.gesture-item .g-name{color:#d0d0e0;font-weight:500}
.gesture-item .g-action{color:#505070}
.toast.show{opacity:1}
.server-ip{font-size:9px;color:#404060;text-align:center;padding:2px 0 4px;flex-shrink:0}

.screen-preview{flex-shrink:0;padding:0 12px 4px;height:130px}
.screen-preview .screen-img{width:100%;height:100%;object-fit:contain;border-radius:8px;background:rgba(0,0,0,0.3);border:1px solid rgba(0,212,255,0.08)}
.nowplaying-bar{flex-shrink:0;padding:2px 12px 4px;display:flex;align-items:center;gap:5px;font-size:10px;color:#606080;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.nowplaying-bar .np-icon{flex-shrink:0}
.nowplaying-bar .np-text{overflow:hidden;text-overflow:ellipsis}
.features-panel{flex-shrink:0;padding:0 12px 6px}
.fp-tabs{display:flex;gap:2px;margin-bottom:4px}
.fp-tab{padding:4px 8px;font-size:10px;border-radius:6px 6px 0 0;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);border-bottom:none;color:#505070;cursor:pointer;flex:1;text-align:center}
.fp-tab.active{background:rgba(0,212,255,0.06);border-color:rgba(0,212,255,0.12);color:#00d4ff}
.fp-content{padding:6px;background:rgba(0,212,255,0.02);border:1px solid rgba(0,212,255,0.06);border-radius:0 6px 6px 6px;min-height:80px;max-height:150px;overflow-y:auto}
.vol-slider-wrap{display:flex;align-items:center;gap:8px;padding:8px 0}
.vol-slider{flex:1;-webkit-appearance:none;height:6px;border-radius:3px;background:rgba(0,212,255,0.15);outline:none}
.vol-slider::-webkit-slider-thumb{-webkit-appearance:none;width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,#00d4ff,#0090cc);cursor:pointer}
.vol-label{font-size:16px;font-weight:700;color:#00d4ff;min-width:36px;text-align:center}
.app-list{display:flex;flex-direction:column;gap:3px}
.app-item{display:flex;justify-content:space-between;align-items:center;padding:4px 6px;background:rgba(255,255,255,0.03);border-radius:4px;cursor:pointer;font-size:10px}
.app-item:active{background:rgba(0,212,255,0.1)}
.app-item .ai-name{color:#d0d0e0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.app-item .ai-focus{color:#00d4ff;font-size:9px;flex-shrink:0;margin-left:4px}
.type-area{width:100%;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:6px 8px;color:#d0d0e0;font-size:12px;resize:none;outline:none;font-family:inherit}
.type-area:focus{border-color:rgba(0,212,255,0.3)}
.type-send{width:100%;margin-top:4px;padding:6px;background:linear-gradient(135deg,#00d4ff,#0090cc);border:none;border-radius:6px;color:#fff;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit}
.file-path-bar{display:flex;gap:4px;margin-bottom:4px}
.file-path-bar .fp-path{flex:1;font-size:9px;color:#505070;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;background:rgba(0,0,0,0.2);padding:3px 6px;border-radius:4px}
.file-path-bar .fp-up{padding:2px 8px;background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.15);border-radius:4px;color:#00d4ff;cursor:pointer;font-size:11px}
.file-list{display:flex;flex-direction:column;gap:2px;max-height:120px;overflow-y:auto}
.file-item{display:flex;align-items:center;gap:4px;padding:3px 6px;cursor:pointer;border-radius:4px;font-size:10px}
.file-item:active{background:rgba(0,212,255,0.08)}
.file-item .fi-icon{flex-shrink:0;font-size:12px}
.file-item .fi-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#b0b0c8}
.file-item .fi-size{flex-shrink:0;color:#404060;font-size:9px}

/* Login overlay */
.login-overlay{position:fixed;inset:0;background:#05050a;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1000;padding:24px}
.login-overlay.hidden{display:none}
.login-box{width:100%;max-width:320px;text-align:center}
.login-box h2{font-size:18px;font-weight:700;background:linear-gradient(90deg,#00d4ff,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}
.login-box p{font-size:11px;color:#505070;margin-bottom:20px}
.pin-input{width:100%;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:14px 16px;color:#d0d0e0;font-size:24px;font-weight:600;letter-spacing:8px;text-align:center;outline:none;transition:border-color 0.2s}
.pin-input:focus{border-color:rgba(0,212,255,0.4)}
.pin-submit{width:100%;margin-top:12px;background:linear-gradient(135deg,#00d4ff,#0090cc);border:none;border-radius:12px;padding:12px;color:#fff;font-size:14px;font-weight:600;cursor:pointer;transition:transform 0.15s}
.pin-submit:active{transform:scale(0.96)}
.pin-error{color:#ef4444;font-size:12px;margin-top:8px;min-height:18px}
</style>
</head>
<body>

<div class="login-overlay" id="loginOverlay">
<div class="login-box">
<h2>VAYU</h2>
<p>Enter device code to connect</p>
<input class="pin-input" type="password" id="pinInput" maxlength="10" autocomplete="off" onkeydown="if(event.key==='Enter')doLogin()" inputmode="text">
<button class="pin-submit" onclick="doLogin()">Connect</button>
<div class="pin-error" id="pinError"></div>
</div>
</div>

<div class="hologram-banner" id="hologramBanner"><canvas id="holoCanvas"></canvas></div>

<div class="header">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" fill="currentColor"/></svg>
<h1>VAYU remote</h1>
<div class="status-badge"><span class="status-dot offline" id="statusDot"></span><span id="statusText">OFFLINE</span></div>
</div>

<div class="quick-actions">
<div class="q-btn" onclick="sendCommand('mute')"><span class="icon">🔇</span>Mute</div>
<div class="q-btn" onclick="sendCommand('next mode')"><span class="icon">⏭️</span>Mode</div>
<div class="q-btn" onclick="sendCommand('volume up')"><span class="icon">🔊</span>Vol+</div>
<div class="q-btn" onclick="sendCommand('volume down')"><span class="icon">🔉</span>Vol-</div>
<div class="q-btn" onclick="toggleScreen()" id="scBtn"><span class="icon">🖥️</span>Screen</div>
<div class="q-btn" onclick="toggleCamera()" id="camBtn"><span class="icon">📷</span>Camera</div>
<div class="q-btn" onclick="toggleCursor()" id="curBtn"><span class="icon">🖱️</span>Cursor</div>
<div class="q-btn" onclick="toggleFeatures()" id="featBtn"><span class="icon">⚡</span>More</div>
</div>

<div class="screen-preview" id="screenPreview" style="display:none">
<img id="screenImg" class="screen-img" alt="Screen preview">
</div>

<div class="nowplaying-bar" id="nowplayingBar"><span class="np-icon">🎵</span><span class="np-text" id="npText">No media playing</span></div>

<div class="features-panel" id="featuresPanel" style="display:none">
<div class="fp-tabs">
<span class="fp-tab active" onclick="showFeatTab('vol',this)">🔊 Vol</span>
<span class="fp-tab" onclick="showFeatTab('apps',this)">📱 Apps</span>
<span class="fp-tab" onclick="showFeatTab('type',this)">⌨️ Type</span>
<span class="fp-tab" onclick="showFeatTab('files',this)">📁 Files</span>
</div>
<div class="fp-content" id="fpVol">
<div class="vol-slider-wrap"><input type="range" min="0" max="100" value="50" class="vol-slider" id="volSlider" oninput="setVolume(this.value)" onchange="setVolume(this.value)"><div class="vol-label" id="volLabel">50%</div></div>
</div>
<div class="fp-content" id="fpApps" style="display:none"><div class="app-list" id="appList">Loading...</div></div>
<div class="fp-content" id="fpType" style="display:none">
<textarea class="type-area" id="typeArea" placeholder="Type text to send to PC..." rows="2"></textarea>
<button class="type-send" onclick="sendType()">Type on PC</button>
</div>
<div class="fp-content" id="fpFiles" style="display:none">
<div class="file-path-bar"><span class="fp-path" id="fpPath">C:\</span><button class="fp-up" onclick="fileGoUp()">↑</button></div>
<div class="file-list" id="fileList">Loading...</div>
</div>
</div>

<div class="gesture-bar" id="gestureBar"><span>Gesture:</span><span class="cur-gesture" id="curGesture">--</span></div>

<div class="g-ref-btn" id="gRefBtn" onclick="toggleGestureRef()">+ Gesture Reference</div>
<div class="gesture-ref" id="gestureRef" style="overflow:hidden;max-height:0;padding:0 12px">
<div class="gesture-item"><span class="g-name">Fist</span><span class="g-action">Mute Toggle</span></div>
<div class="gesture-item"><span class="g-name">Open Palm</span><span class="g-action">Unmute</span></div>
<div class="gesture-item"><span class="g-name">Thumbs Up</span><span class="g-action">Next Mode</span></div>
<div class="gesture-item"><span class="g-name">Peace</span><span class="g-action">Prev Mode</span></div>
<div class="gesture-item"><span class="g-name">Point Up</span><span class="g-action">Vol+</span></div>
<div class="gesture-item"><span class="g-name">Pinch</span><span class="g-action">Vol-</span></div>
<div class="gesture-item"><span class="g-name">Swipe L/R</span><span class="g-action">Scroll</span></div>
<div class="gesture-item"><span class="g-name">Shake</span><span class="g-action">Alt+Tab</span></div>
<div class="gesture-item"><span class="g-name">OK</span><span class="g-action">Enter</span></div>
<div class="gesture-item"><span class="g-name">Three</span><span class="g-action">Desktop</span></div>
<div class="gesture-item"><span class="g-name">Four</span><span class="g-action">Task View</span></div>
<div class="gesture-item"><span class="g-name">Rock On</span><span class="g-action">Play/Pause</span></div>
</div>

<div class="touchpad" id="touchpad" style="display:none">
<div class="touchpad-inner" id="touchpadInner">
<div class="touchpad-hint">Drag to move mouse · Tap to click</div>
</div>
</div>

<div class="log-area" id="logArea"><div style="text-align:center;color:#404060;font-size:12px;margin-top:20px">Commands appear here</div></div>
<div class="server-ip" id="serverIp"></div>
<div class="server-ip" id="tunnelUrl" style="color:#10b981"></div>

<div class="input-area">
<button class="btn-voice" id="voiceBtn" onclick="toggleVoice()"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg></button>
<input type="text" id="textInput" placeholder="Type a command..." autocomplete="off" onkeydown="if(event.key==='Enter')sendText()">
<button class="btn-send" onclick="sendText()"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg></button>
</div>

<div class="toast" id="toast"></div>

<script>
let mediaRecorder = null, audioChunks = [], isRecording = false, logCount = 0;
let authToken = localStorage.getItem('vayu_token') || '';
let screenOn = false, screenInterval = null, curPath = 'C:\\';
let featuresOn = false, curFeatTab = 'vol';

function toggleScreen() {
  screenOn = !screenOn;
  document.getElementById('scBtn').className = 'q-btn' + (screenOn ? ' cam-on' : '');
  document.getElementById('screenPreview').style.display = screenOn ? 'block' : 'none';
  if (screenOn) { screenInterval = setInterval(refreshScreen, 3000); refreshScreen(); }
  else { clearInterval(screenInterval); }
}

function refreshScreen() {
  const img = document.getElementById('screenImg');
  img.src = '/screen?token=' + encodeURIComponent(authToken) + '&t=' + Date.now();
}

function toggleFeatures() {
  featuresOn = !featuresOn;
  document.getElementById('featBtn').className = 'q-btn' + (featuresOn ? ' cur-on' : '');
  document.getElementById('featuresPanel').style.display = featuresOn ? 'block' : 'none';
  if (featuresOn) { loadApps(); loadFiles(curPath); }
}

function showFeatTab(tab, el) {
  curFeatTab = tab;
  document.querySelectorAll('.fp-tab').forEach(t => t.className = 'fp-tab');
  if (el) el.className = 'fp-tab active';
  document.querySelectorAll('.fp-content').forEach(c => c.style.display = 'none');
  const t = document.getElementById('fp' + tab.charAt(0).toUpperCase() + tab.slice(1));
  if (t) t.style.display = 'block';
  if (tab === 'apps') loadApps();
  if (tab === 'files') loadFiles(curPath);
}

function setVolume(level) {
  document.getElementById('volLabel').textContent = level + '%';
  fetch('/volume', {method:'POST', headers:{'Content-Type':'application/json','X-Vayu-Token':authToken}, body:JSON.stringify({level:parseInt(level)})}).catch(()=>{});
}

function sendType() {
  const text = document.getElementById('typeArea').value;
  if (!text.trim()) return;
  fetch('/type', {method:'POST', headers:{'Content-Type':'application/json','X-Vayu-Token':authToken}, body:JSON.stringify({text:text})}).catch(()=>{});
  showToast('Typing on PC...');
}

function loadFiles(path) {
  curPath = path;
  document.getElementById('fpPath').textContent = path;
  const list = document.getElementById('fileList');
  list.textContent = 'Loading...';
  fetch('/files?token=' + encodeURIComponent(authToken) + '&path=' + encodeURIComponent(path)).then(r => r.json()).then(d => {
    if (!d.items) { list.textContent = 'Error'; return; }
    list.innerHTML = '';
    for (const item of d.items) {
      const el = document.createElement('div');
      el.className = 'file-item';
      const icon = item.is_dir ? '\uD83D\uDCC1' : '\uD83D\uDCC4';
      const sz = item.is_dir ? '' : (item.size > 1048576 ? (item.size/1048576).toFixed(1)+'MB' : item.size > 1024 ? (item.size/1024).toFixed(0)+'KB' : item.size+'B');
      el.innerHTML = '<span class="fi-icon">' + icon + '</span><span class="fi-name">' + escapeHtml(item.name) + '</span><span class="fi-size">' + sz + '</span>';
      el.onclick = function() {
        if (item.is_dir) loadFiles(item.path);
        else { window.open('/download?token=' + encodeURIComponent(authToken) + '&path=' + encodeURIComponent(item.path)); }
      };
      list.appendChild(el);
    }
    if (d.items.length === 0) list.innerHTML = '<div style="color:#404060;font-size:10px;text-align:center;padding:8px">Empty folder</div>';
  }).catch(() => { list.textContent = 'Error loading'; });
}

function fileGoUp() {
  const p = curPath.replace(/\\$/, '');
  const parent = p.substring(0, p.lastIndexOf('\\'));
  if (parent && parent.length >= 2) loadFiles(parent);
}

function loadApps() {
  const list = document.getElementById('appList');
  list.textContent = 'Loading...';
  fetch('/apps?token=' + encodeURIComponent(authToken)).then(r => r.json()).then(d => {
    if (!d.apps || d.apps.length === 0) { list.innerHTML = '<div style="color:#404060;font-size:10px;text-align:center;padding:8px">No open windows</div>'; return; }
    list.innerHTML = '';
    for (const app of d.apps) {
      const el = document.createElement('div');
      el.className = 'app-item';
      el.innerHTML = '<span class="ai-name">' + escapeHtml(app.title || app.name) + '</span><span class="ai-focus">Focus</span>';
      el.onclick = function() {
        fetch('/focus', {method:'POST', headers:{'Content-Type':'application/json','X-Vayu-Token':authToken}, body:JSON.stringify({title:app.title})}).catch(()=>{});
      };
      list.appendChild(el);
    }
  }).catch(() => { list.textContent = 'Error'; });
}

function addLog(type, text) {
  const area = document.getElementById('logArea');
  if (logCount === 0) area.innerHTML = '';
  const el = document.createElement('div');
  el.className = 'log-entry ' + type;
  el.innerHTML = '<div class="label">' + (type === 'user' ? 'you' : 'vayu') + '</div>' + escapeHtml(text);
  area.appendChild(el);
  area.scrollTop = area.scrollHeight;
  logCount++;
}

function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast show';
  setTimeout(() => t.className = 'toast', 2000);
}

async function doLogin() {
  const pin = document.getElementById('pinInput').value.trim();
  if (!pin) return;
  const err = document.getElementById('pinError');
  try {
    const r = await fetch('/auth', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pin:pin})});
    const data = await r.json();
    if (r.ok && data.token) {
      authToken = data.token;
      localStorage.setItem('vayu_token', authToken);
      document.getElementById('loginOverlay').className = 'login-overlay hidden';
      pollStatus();
    } else {
      err.textContent = data.error || 'Wrong code';
    }
  } catch(e) {
    err.textContent = 'Connection error';
  }
}

function checkAuth() {
  if (authToken) {
    fetch('/status').then(r => {
      if (r.ok) {
        document.getElementById('loginOverlay').className = 'login-overlay hidden';
        pollStatus();
      }
    }).catch(() => {});
  }
}

async function sendCommand(text) {
  if (!text.trim()) return;
  addLog('user', text);
  document.getElementById('textInput').value = '';
  try {
    const r = await fetch('/command', {method:'POST', headers:{'Content-Type':'application/json','X-Vayu-Token':authToken}, body:JSON.stringify({text:text})});
    if (!r.ok) { const d = await r.json(); showToast(d.error || 'Failed'); }
  } catch(e) { showToast('Connection error'); }
}

function sendText() {
  const inp = document.getElementById('textInput');
  sendCommand(inp.value);
}

async function toggleMic() {
  const btn = document.getElementById('micBtn');
  if (isRecording) {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    btn.className = 'btn-mic'; isRecording = false;
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio:{sampleRate:16000,channelCount:1}});
    mediaRecorder = new MediaRecorder(stream, {mimeType:'audio/webm;codecs=opus'});
    audioChunks = [];
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      btn.className = 'btn-mic'; isRecording = false;
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, {type:'audio/webm'});
      if (blob.size < 1000) return;
      addLog('user', 'Audio sent...');
      try {
        const r = await fetch('/audio', {method:'POST', headers:{'X-Vayu-Token':authToken}, body:blob});
        if (!r.ok) { const d = await r.json(); showToast(d.error || 'Audio failed'); }
      } catch(e) { showToast('Connection error'); }
    };
    mediaRecorder.start();
    btn.className = 'btn-mic recording'; isRecording = true;
    setTimeout(() => { if (isRecording) { mediaRecorder.stop(); } }, 5000);
  } catch(e) { showToast('Mic access denied'); }
}

let voiceRec = null, isVoiceOn = false;
function toggleVoice() {
  const btn = document.getElementById('voiceBtn');
  if (isVoiceOn) {
    if (voiceRec) { voiceRec.stop(); voiceRec = null; }
    btn.className = 'btn-voice'; isVoiceOn = false;
    return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { showToast('Voice not supported'); return; }
  voiceRec = new SR();
  voiceRec.lang = 'en-US';
  voiceRec.interimResults = true;
  voiceRec.continuous = true;
  voiceRec.onresult = function(e) {
    let interim = '', final = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) final += e.results[i][0].transcript;
      else interim += e.results[i][0].transcript;
    }
    const inp = document.getElementById('textInput');
    if (final) inp.value = final;
    else inp.value = interim;
    inp.selectionStart = inp.selectionEnd = inp.value.length;
  };
  voiceRec.onerror = function() { btn.className = 'btn-voice'; isVoiceOn = false; showToast('Voice error'); };
  voiceRec.start();
  btn.className = 'btn-voice listening'; isVoiceOn = true;
  showToast('Speak now...');
}

let cameraOn = false, cursorOn = false;

function toggleCamera() {
  cameraOn = !cameraOn;
  document.getElementById('camBtn').className = 'q-btn' + (cameraOn ? ' cam-on' : '');
  sendCommand(cameraOn ? 'camera on' : 'camera off');
}

function toggleCursor() {
  cursorOn = !cursorOn;
  const b = document.getElementById('curBtn');
  b.className = 'q-btn' + (cursorOn ? ' cur-on' : '');
  const tp = document.getElementById('touchpad');
  tp.style.display = cursorOn ? 'block' : 'none';
  sendCommand(cursorOn ? 'cursor on' : 'cursor off');
}

function toggleGestureRef() {
  const r = document.getElementById('gestureRef');
  const b = document.getElementById('gRefBtn');
  const open = r.classList.toggle('open');
  b.textContent = open ? '- Gesture Reference' : '+ Gesture Reference';
}

// Touchpad mouse control
(function() {
  const tp = document.getElementById('touchpadInner');
  if (!tp) return;
  let isDragging = false, lastX = 0, lastY = 0;
  function sendMouse(dx, dy) {
    fetch('/mouse', {method:'POST', headers:{'Content-Type':'application/json','X-Vayu-Token':authToken}, body:JSON.stringify({dx:dx, dy:dy})}).catch(()=>{});
  }
  function sendClick() {
    fetch('/click', {method:'POST', headers:{'Content-Type':'application/json','X-Vayu-Token':authToken}}).catch(()=>{});
  }
  tp.addEventListener('touchstart', function(e) {
    e.preventDefault();
    const t = e.touches[0];
    isDragging = true; lastX = t.clientX; lastY = t.clientY;
  });
  tp.addEventListener('touchmove', function(e) {
    e.preventDefault();
    if (!isDragging) return;
    const t = e.touches[0];
    const dx = t.clientX - lastX, dy = t.clientY - lastY;
    lastX = t.clientX; lastY = t.clientY;
    sendMouse(dx * 0.5, dy * 0.5);
  });
  tp.addEventListener('touchend', function(e) {
    e.preventDefault();
    isDragging = false;
    sendClick();
  });
})();

async function pollStatus() {
  try {
    const r = await fetch('/status?token=' + encodeURIComponent(authToken));
    if (!r.ok) {
      if (r.status === 401) { document.getElementById('loginOverlay').className = 'login-overlay'; localStorage.removeItem('vayu_token'); authToken = ''; }
      return;
    }
    const data = await r.json();
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    dot.className = 'status-dot ' + data.state.toLowerCase();
    txt.textContent = data.state;
    document.getElementById('serverIp').textContent = data.ip || '';
    document.getElementById('tunnelUrl').textContent = data.tunnel ? '\u{1F310} ' + data.tunnel : '';
    document.getElementById('curGesture').textContent = data.gesture || '--';
    if (data.nowplaying) {
      const np = data.nowplaying;
      document.getElementById('npText').textContent = np.title ? (np.playing ? '\u25B6 ' : '\u23F8 ') + np.title + (np.artist ? ' - ' + np.artist : '') : 'No media playing';
    }
    if (data.log && data.log.length > logCount) {
      for (let i = logCount; i < data.log.length; i++) {
        const entry = data.log[i];
        addLog(entry.role, entry.text);
      }
      logCount = data.log.length;
    }
  } catch(e) {
    document.getElementById('statusDot').className = 'status-dot offline';
    document.getElementById('statusText').textContent = 'OFFLINE';
  }
}
checkAuth();
setInterval(pollStatus, 1500);

// ─── 3D Hologram (VAYU atom) ───
(function() {
  const c = document.getElementById('holoCanvas');
  if (!c) return;
  const container = document.getElementById('hologramBanner');
  function resize() {
    c.width = container.clientWidth || 360;
    c.height = container.clientHeight || 100;
  }
  resize();
  const ctx = c.getContext('2d');
  let W = c.width, H = c.height, cx = W/2, cy = H/2;

  const electrons = [
    {a:0, s:0.02, r:30, tilt:0.5, sz:2.5},
    {a:1.5, s:-0.025, r:42, tilt:-0.6, sz:2},
    {a:3.0, s:0.018, r:55, tilt:0.4, sz:2.5},
    {a:0.8, s:-0.02, r:68, tilt:-0.5, sz:2}
  ];

  const particles = [];
  for (let i = 0; i < 20; i++) {
    particles.push({
      x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.3, vy: -0.1 - Math.random() * 0.2,
      s: 3 + Math.random() * 3, o: 0.1 + Math.random() * 0.3, v: Math.random() > 0.5 ? '1' : '0'
    });
  }

  function draw() {
    W = c.width; H = c.height; cx = W/2; cy = H/2;
    ctx.clearRect(0, 0, W, H);

    // binary particles
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy;
      if (p.y < -10) { p.y = H + 5; p.x = Math.random() * W; p.v = Math.random() > 0.5 ? '1' : '0'; }
      const d = Math.hypot(p.x - cx, p.y - cy);
      if (d < 80) {
        ctx.globalAlpha = p.o * (1 - d/90);
        ctx.font = p.s + 'px monospace';
        ctx.fillStyle = '#00d4ff';
        ctx.fillText(p.v, p.x, p.y);
      }
    }
    ctx.globalAlpha = 1;

    // orbit rings
    for (const e of electrons) {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(1, Math.max(0.2, Math.abs(Math.sin(e.tilt))));
      ctx.beginPath();
      ctx.arc(0, 0, e.r, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(0,212,255,' + (0.1 + Math.abs(Math.sin(e.tilt)) * 0.08) + ')';
      ctx.lineWidth = 0.8;
      ctx.stroke();
      ctx.restore();
    }

    // electrons
    for (const e of electrons) {
      e.a += e.s;
      const ex = cx + Math.cos(e.a) * e.r * Math.cos(e.tilt);
      const ey = cy + Math.sin(e.a) * e.r;
      const g = ctx.createRadialGradient(ex, ey, 0, ex, ey, e.sz * 2.5);
      g.addColorStop(0, 'rgba(0,212,255,0.85)');
      g.addColorStop(0.5, 'rgba(0,212,255,0.25)');
      g.addColorStop(1, 'rgba(0,212,255,0)');
      ctx.beginPath();
      ctx.arc(ex, ey, e.sz * 2.5, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(ex, ey, e.sz * 0.4, 0, Math.PI * 2);
      ctx.fillStyle = '#00d4ff';
      ctx.fill();
    }

    // nucleus glow
    const ng = ctx.createRadialGradient(cx, cy, 0, cx, cy, 30);
    ng.addColorStop(0, 'rgba(0,212,255,0.25)');
    ng.addColorStop(0.4, 'rgba(124,58,237,0.12)');
    ng.addColorStop(0.7, 'rgba(0,212,255,0.04)');
    ng.addColorStop(1, 'rgba(0,212,255,0)');
    ctx.beginPath(); ctx.arc(cx, cy, 30, 0, Math.PI * 2);
    ctx.fillStyle = ng; ctx.fill();

    // core
    const cg = ctx.createRadialGradient(cx-3, cy-3, 0, cx, cy, 12);
    cg.addColorStop(0, 'rgba(180,240,255,0.5)');
    cg.addColorStop(0.5, 'rgba(0,212,255,0.3)');
    cg.addColorStop(0.8, 'rgba(124,58,237,0.15)');
    cg.addColorStop(1, 'rgba(0,212,255,0)');
    ctx.beginPath(); ctx.arc(cx, cy, 12, 0, Math.PI * 2);
    ctx.fillStyle = cg; ctx.fill();

    // bright dot
    ctx.beginPath(); ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(200,240,255,0.5)'; ctx.fill();

    requestAnimationFrame(draw);
  }
  draw();
  window.addEventListener('resize', () => { resize(); });
})();
</script>
</body>
</html>"""

class WebControlServer:

    def __init__(self, on_command=None, port=5050, enable_tunnel=True):
        self._on_command = on_command
        self._port = port
        self._server = None
        self._thread = None
        self._state = "OFFLINE"
        self._log = []
        self._log_lock = threading.Lock()
        self._groq_client = None
        self._tunnel_url = None
        self._enable_tunnel = enable_tunnel
        self._ngrok_proc = None
        self._device_pin = self._load_pin()
        self._auth_token = secrets.token_hex(32)
        self._current_gesture = ""
        self._cursor_mode = False
        print(f"[WebControl] Device code: {self._device_pin}")
        print(f"[WebControl] Auth token: {self._auth_token[:8]}...")

    def _load_pin(self):
        try:
            p = Path(__file__).parent.parent / "config" / "api_keys.json"
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                return str(d.get("web_pin", ""))
        except Exception:
            pass
        return "8421"

    def _get_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def set_groq_client(self, client):
        self._groq_client = client

    def set_state(self, state: str):
        self._state = state

    def set_gesture(self, gesture: str):
        self._current_gesture = gesture

    def set_cursor_mode(self, enabled: bool):
        self._cursor_mode = enabled

    def add_log(self, role: str, text: str):
        with self._log_lock:
            self._log.append({"role": role, "text": text})
            if len(self._log) > 100:
                self._log = self._log[-100:]

    def _transcribe_audio(self, data: bytes) -> str:
        gc = self._groq_client
        if gc is None:
            try:
                from groq_client import GroqClient
                import json
                api_path = Path(__file__).parent.parent / "config" / "api_keys.json"
                if api_path.exists():
                    keys = json.loads(api_path.read_text(encoding="utf-8"))
                    key = keys.get("groq_api_key", "")
                    if key:
                        gc = GroqClient(api_key=key)
            except Exception:
                pass
        if gc is None:
            return ""
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
            tmp.write(data)
            tmp.close()
            text = gc.transcribe_from_file(tmp.name)
            os.unlink(tmp.name)
            return text
        except Exception as e:
            print(f"[WebControl] Transcription error: {e}")
            return ""

    def _capture_screen(self) -> bytes | None:
        try:
            from PIL import ImageGrab
            import io
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.thumbnail((640, 480))
            img.save(buf, "JPEG", quality=35)
            return buf.getvalue()
        except Exception:
            return None

    def _type_text(self, text: str):
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.02)
        except Exception as e:
            print(f"[WebControl] type error: {e}")

    def _list_apps(self) -> list:
        try:
            import subprocess
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object Id, ProcessName, @{N='Title';E={$_.MainWindowTitle}} | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            import json
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            return [{"id": d["Id"], "name": d.get("ProcessName", ""), "title": d.get("Title", "")} for d in data[:30]]
        except Exception:
            return []

    def _focus_app(self, title: str):
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].activate()
        except Exception:
            try:
                import subprocess
                subprocess.run(["powershell", "-NoProfile", "-Command",
                 f"(Get-Process | Where-Object {{$_.MainWindowTitle -eq '{title}'}}).MainWindowHandle | ForEach-Object {{[void][User32]::SetForegroundWindow($_)}}"],
                 capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass

    def _set_volume_level(self, level: int):
        level = max(0, min(100, level))
        try:
            import subprocess
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(New-Object -ComObject WScript.Shell).SendKeys([char]0) ; "
                 f"(New-Object -ComObject WScript.Shell).SendKeys([char]174 * 50) ; "
                 f"$obj = New-Object -ComObject WScript.Shell; "
                 f"for($i=0;$i -lt 50;$i++){{$obj.SendKeys([char]175)}} ; "
                 f"for($i=0;$i -lt {level//2};$i++){{$obj.SendKeys([char]175)}}"],
                capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass

    def _get_now_playing(self) -> dict:
        try:
            import subprocess
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                 "$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]; "
                 "Register-ObjectReference -ErrorAction Stop | Out-Null; "
                 "$mgr = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync().GetAwaiter().GetResult(); "
                 "$sess = $mgr.GetCurrentSession(); "
                 "if($sess){$info = $sess.TryGetMediaPropertiesAsync().GetAwaiter().GetResult(); "
                 "echo ($info.Title + '|' + $info.Artist + '|' + ($sess.GetPlaybackInfo().PlaybackStatus -eq 4))}"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            parts = r.stdout.strip().split("|")
            if len(parts) >= 3:
                return {"title": parts[0], "artist": parts[1], "playing": parts[2] == "True"}
        except Exception:
            pass
        return {"title": "", "artist": "", "playing": False}

    def _list_files(self, path: str) -> list:
        try:
            from pathlib import Path
            p = Path(path)
            if not p.exists() or not p.is_dir():
                return []
            items = []
            for item in sorted(p.iterdir()):
                try:
                    is_dir = item.is_dir()
                    size = item.stat().st_size if item.is_file() else 0
                    items.append({"name": item.name, "is_dir": is_dir, "size": size, "path": str(item)})
                except Exception:
                    pass
            return items[:50]
        except Exception:
            return []

    def _download_file(self, path: str) -> tuple[bytes, str] | None:
        try:
            p = Path(path)
            if p.exists() and p.is_file():
                content = p.read_bytes()
                ext = p.suffix or ".bin"
                if ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
                    ctype = f"image/{ext[1:]}"
                elif ext.lower() in (".txt", ".py", ".js", ".html", ".css", ".md", ".json", ".xml", ".csv"):
                    ctype = "text/plain"
                elif ext.lower() == ".pdf":
                    ctype = "application/pdf"
                else:
                    ctype = "application/octet-stream"
                return (content, ctype)
        except Exception:
            pass
        return None

    class _Handler(BaseHTTPRequestHandler):
        server_instance = None

        def _send_json(self, data, status=200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def _send_html(self, html):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode())

        def _check_auth(self, sv):
            if sv is None:
                return False
            token = self.headers.get("X-Vayu-Token", "")
            qs = parse_qs(urlparse(self.path).query)
            token = token or qs.get("token", [""])[0]
            return token == sv._auth_token

        def _do_mouse_move(self, sv, dx, dy):
            try:
                import pyautogui
                pyautogui.moveRel(dx, dy)
            except Exception:
                pass

        def _do_mouse_click(self, sv):
            try:
                import pyautogui
                pyautogui.click()
            except Exception:
                pass

        def do_GET(self):
            sv = self.server_instance
            if self.path == "/status":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                ip = sv._get_ip() if sv else "?"
                state = sv._state if sv else "OFFLINE"
                with sv._log_lock if sv else threading.Lock():
                    log_copy = list(sv._log) if sv else []
                tunnel = sv.tunnel_url if sv else ""
                np = sv._get_now_playing() if sv else {}
                self._send_json({"state": state, "ip": f"{ip}:{sv._port}", "tunnel": tunnel, "log": log_copy, "gesture": sv._current_gesture, "cursor": sv._cursor_mode, "nowplaying": np})
            elif self.path == "/screen":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                jpg = sv._capture_screen() if sv else None
                if jpg:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(jpg)
                else:
                    self._send_json({"error": "screen capture failed"}, 500)
            elif self.path.startswith("/files"):
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                qs = parse_qs(urlparse(self.path).query)
                path = qs.get("path", ["C:\\"])[0]
                items = sv._list_files(path) if sv else []
                self._send_json({"path": path, "items": items})
            elif self.path.startswith("/download"):
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                qs = parse_qs(urlparse(self.path).query)
                path = qs.get("path", [""])[0]
                if path and sv:
                    result = sv._download_file(path)
                    if result:
                        data, ctype = result
                        self.send_response(200)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Disposition", "attachment")
                        self.end_headers()
                        self.wfile.write(data)
                        return
                self._send_json({"error": "file not found"}, 404)
            elif self.path == "/apps":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                apps = sv._list_apps() if sv else []
                self._send_json({"apps": apps})
            elif self.path == "/nowplaying":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                np = sv._get_now_playing() if sv else {}
                self._send_json(np)
            else:
                self._send_html(HTML)

        def do_POST(self):
            sv = self.server_instance
            if sv is None:
                self._send_json({"error": "no server"}, 500)
                return
            parsed = urlparse(self.path)
            if parsed.path == "/auth":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    pin = data.get("pin", "")
                    if pin == sv._device_pin:
                        self._send_json({"ok": True, "token": sv._auth_token})
                    else:
                        self._send_json({"error": "Wrong device code"}, 401)
                except Exception as e:
                    self._send_json({"error": str(e)}, 400)
            elif parsed.path == "/command":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    text = data.get("text", "").strip()
                    if text and sv._on_command:
                        sv._on_command(text)
                        sv.add_log("user", text)
                    self._send_json({"ok": True})
                except Exception as e:
                    self._send_json({"error": str(e)}, 400)
            elif parsed.path == "/audio":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                length = int(self.headers.get("Content-Length", 0))
                data = self.rfile.read(length)
                if data and len(data) > 100:
                    text = sv._transcribe_audio(data)
                    if text:
                        sv._on_command(text)
                        sv.add_log("user", text)
                    self._send_json({"ok": True, "text": text})
                else:
                    self._send_json({"error": "no audio data"}, 400)
            elif parsed.path == "/mouse":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    self._do_mouse_move(sv, data.get("dx", 0), data.get("dy", 0))
                    self._send_json({"ok": True})
                except Exception as e:
                    self._send_json({"error": str(e)}, 400)
            elif parsed.path == "/click":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                self._do_mouse_click(sv)
                self._send_json({"ok": True})
            elif parsed.path == "/type":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    text = data.get("text", "")
                    if text and sv:
                        sv._type_text(text)
                    self._send_json({"ok": True})
                except Exception as e:
                    self._send_json({"error": str(e)}, 400)
            elif parsed.path == "/focus":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    title = data.get("title", "")
                    if title and sv:
                        sv._focus_app(title)
                    self._send_json({"ok": True})
                except Exception as e:
                    self._send_json({"error": str(e)}, 400)
            elif parsed.path == "/volume":
                if not self._check_auth(sv):
                    self._send_json({"error": "unauthorized"}, 401)
                    return
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    level = data.get("level", 50)
                    if sv:
                        sv._set_volume_level(level)
                    self._send_json({"ok": True})
                except Exception as e:
                    self._send_json({"error": str(e)}, 400)
            else:
                self._send_json({"error": "not found"}, 404)

        def log_message(self, fmt, *args):
            pass

    def start(self):
        self._Handler.server_instance = self
        try:
            self._server = HTTPServer(("0.0.0.0", self._port), self._Handler)
            self._server.timeout = 1.0
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            ip = self._get_ip()
            local_url = f"http://{ip}:{self._port}"
            print(f"[WebControl] Local: {local_url}")
            print(f"[WebControl] Open on phone (same Wi-Fi) or use tunnel for anywhere")
            if self._enable_tunnel:
                threading.Thread(target=self._start_tunnel, daemon=True).start()
            return True
        except OSError:
            print(f"[WebControl] Port {self._port} busy, trying {self._port + 1}")
            self._port += 1
            return self.start()

    def _base_dir(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).resolve().parent.parent

    def _find_ngrok(self) -> str | None:
        base = self._base_dir()
        for d in (base, base / "web", Path.home() / ".vayu"):
            p = d / ("ngrok.exe" if os.name == "nt" else "ngrok")
            if p.exists():
                return str(p)
        for p in os.environ.get("PATH", "").split(os.pathsep):
            exe = Path(p) / ("ngrok.exe" if os.name == "nt" else "ngrok")
            if exe.exists():
                return str(exe)
        return None

    def _download_ngrok(self) -> str | None:
        dest = self._base_dir() / ("ngrok.exe" if os.name == "nt" else "ngrok")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
        elif sys.platform == "darwin":
            url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-amd64.zip"
        else:
            url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip"
        try:
            print(f"[WebControl] Downloading ngrok...")
            zip_path = dest.with_suffix(".zip")
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extract(str(dest.name), dest.parent)
            zip_path.unlink()
            if os.name != "nt":
                dest.chmod(0o755)
            print(f"[WebControl] ngrok downloaded to {dest}")
            return str(dest)
        except Exception as e:
            print(f"[WebControl] ngrok download failed: {e}")
            return None

    def _start_tunnel(self):
        ngrok = self._find_ngrok()
        if ngrok is None:
            ngrok = self._download_ngrok()
        if ngrok is None:
            print(f"[WebControl] No ngrok — tunnel disabled")
            return
        try:
            self._ngrok_proc = subprocess.Popen(
                [ngrok, "http", str(self._port), "--log=stdout"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(3)
            for _ in range(20):
                try:
                    r = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3)
                    data = json.loads(r.read())
                    for t in data.get("tunnels", []):
                        if t.get("public_url", "").startswith("https://"):
                            self._tunnel_url = t["public_url"]
                            print(f"[WebControl] Tunnel: {self._tunnel_url}")
                            print(f"[WebControl] Open from ANYWHERE!")
                            return
                except Exception:
                    pass
                time.sleep(1)
            print(f"[WebControl] Tunnel URL not found")
        except Exception as e:
            print(f"[WebControl] Tunnel failed: {e}")

    @property
    def tunnel_url(self):
        return self._tunnel_url or ""

    def stop(self):
        if self._ngrok_proc:
            self._ngrok_proc.terminate()
        if self._server:
            self._server.shutdown()

    @property
    def port(self):
        return self._port

    @property
    def url(self):
        return f"http://{self._get_ip()}:{self._port}"
