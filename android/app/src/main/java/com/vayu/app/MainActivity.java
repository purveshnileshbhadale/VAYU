package com.vayu.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlarmManager;
import android.app.AlertDialog;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.media.AudioManager;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;
import android.os.SystemClock;
import android.os.Vibrator;
import android.provider.ContactsContract;
import android.provider.Settings;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Base64;
import android.util.Log;
import android.view.KeyEvent;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.Locale;

public class MainActivity extends AppCompatActivity {

    private static final String TAG = "VAYU";
    private static final String ACTION_ALARM = "com.vayu.app.ALARM_FIRE";
    private static final String ACTION_TIMER = "com.vayu.app.TIMER_FIRE";
    private static final int REQ_PERMS = 100;
    private static final int REQ_CAMERA = 200;
    private static final int REQ_SETTINGS = 300;

    private WebView webView;
    private AndroidBridge bridge;
    private SpeechRecognizer speechRecognizer;
    private Intent recognizerIntent;
    private boolean wakeWordMode = false;
    private boolean isNativeListening = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private TextToSpeech tts;
    private float ttsRate = 0.85f;
    private File cameraFile;
    private Runnable timerRunnable;
    private final List<String> recentTools = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        createChannels();
        initTts();
        initWebView();

        requestRuntimePermissions();
        if (ACTION_ALARM.equals(getIntent().getAction())) {
            fireAlarm(getIntent().getStringExtra("label"));
        }
    }

    /* ---------------- notifications ---------------- */
    private void createChannels() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm == null) return;
        NotificationChannel ch = new NotificationChannel("vayu", "VAYU",
                NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("VAYU alarms, timers and notifications");
        nm.createNotificationChannel(ch);
    }

    private void notify(String title, String text, int id) {
        if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        Notification n = new NotificationCompat.Builder(this, "vayu")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(text)
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .build();
        getSystemService(NotificationManager.class).notify(id, n);
    }

    /* ---------------- WebView ---------------- */
    private void initWebView() {
        webView = findViewById(R.id.webView);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setUserAgentString(s.getUserAgentString() + " VAYU-Android/1.1");

        bridge = new AndroidBridge();
        webView.addJavascriptInterface(bridge, "VayuAndroid");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                    } catch (Exception ignored) {}
                    return true;
                }
                view.loadUrl(url);
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> request.grant(request.getResources()));
            }
        });

        webView.loadUrl("file:///android_asset/vayu-app/index.html");
    }

    private void requestRuntimePermissions() {
        List<String> needed = new ArrayList<>();
        needed.add(Manifest.permission.RECORD_AUDIO);
        needed.add(Manifest.permission.CAMERA);
        if (Build.VERSION.SDK_INT >= 33) needed.add(Manifest.permission.POST_NOTIFICATIONS);
        List<String> missing = new ArrayList<>();
        for (String p : needed) {
            if (ContextCompat.checkSelfPermission(this, p) != PackageManager.PERMISSION_GRANTED) {
                missing.add(p);
            }
        }
        if (!missing.isEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toArray(new String[0]), REQ_PERMS);
        }
    }

    /* ---------------- JS bridge ---------------- */
    public class AndroidBridge {

        @JavascriptInterface
        public String platform() { return "android"; }

        @JavascriptInterface
        public void startSpeech() {
            runOnUiThread(() -> startRecognition(false));
        }

        @JavascriptInterface
        public void stopSpeech() {
            runOnUiThread(() -> {
                if (speechRecognizer != null) {
                    try { speechRecognizer.stopListening(); } catch (Exception ignored) {}
                }
                isNativeListening = false;
            });
        }

        @JavascriptInterface
        public void setWakeWord(boolean enabled) {
            runOnUiThread(() -> {
                wakeWordMode = enabled;
                if (enabled) startRecognition(true);
                else {
                    isNativeListening = false;
                    if (speechRecognizer != null) {
                        try { speechRecognizer.stopListening(); } catch (Exception ignored) {}
                    }
                }
            });
        }

        @JavascriptInterface
        public void speak(String text) {
            runOnUiThread(() -> speakTts(text));
        }

        @JavascriptInterface
        public void stopSpeaking() {
            runOnUiThread(() -> {
                if (tts != null) tts.stop();
            });
        }

        @JavascriptInterface
        public void setVoiceRate(float rate) {
            ttsRate = rate;
            if (tts != null) tts.setSpeechRate(rate);
        }

        @JavascriptInterface
        public void capturePhoto() {
            runOnUiThread(() -> openCamera());
        }

        @JavascriptInterface
        public void vibrate(long ms) {
            Vibrator v = (Vibrator) getSystemService(VIBRATOR_SERVICE);
            if (v != null && v.hasVibrator()) v.vibrate(ms);
        }

        @JavascriptInterface
        public void toast(String msg) {
            runOnUiThread(() -> android.widget.Toast.makeText(MainActivity.this, msg,
                    android.widget.Toast.LENGTH_SHORT).show());
        }

        @JavascriptInterface
        public void getSysInfo() {
            runOnUiThread(() -> callJs("window.VayuNative&&window.VayuNative.onSysInfo(" +
                    JSONObject.quote(buildSysInfoJson()) + ")"));
        }

        /* ---- device control: executed by Groq function calling ---- */
        @JavascriptInterface
        public String execTool(String name, String argsJson) {
            try {
                JSONObject args = argsJson == null ? new JSONObject() : new JSONObject(argsJson);
                String result = runTool(name, args);
                recentTools.add(name);
                return new JSONObject().put("ok", true).put("result", result).toString();
            } catch (Exception e) {
                Log.e(TAG, "Tool " + name + " failed: " + e);
                try {
                    return new JSONObject().put("ok", false).put("error", e.getMessage()).toString();
                } catch (Exception e2) {
                    return "{\"ok\":false,\"error\":\"tool failed\"}";
                }
            }
        }
    }

    private String runTool(String name, JSONObject args) throws Exception {
        switch (name) {
            case "open_app": {
                String app = args.optString("app_name", "");
                if (app.isEmpty()) return "No app name given";
                String pkg = findAppPackage(app);
                if (pkg == null) {
                    String suggestion = suggestApp(app);
                    return suggestion == null
                            ? "App '" + app + "' not found. Use list_apps to see installed apps."
                            : "App '" + app + "' not found. Did you mean '" + suggestion + "'?";
                }
                Intent i = getPackageManager().getLaunchIntentForPackage(pkg);
                if (i == null) return "App found but cannot be launched: " + pkg;
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(i);
                return "Opened " + app;
            }
            case "list_apps": {
                Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
                List<ResolveInfo> ris = getPackageManager().queryIntentActivities(launcher, 0);
                JSONArray arr = new JSONArray();
                for (ResolveInfo ri : ris) arr.put(ri.loadLabel(getPackageManager()).toString());
                return "Installed apps: " + arr.toString();
            }
            case "send_sms": {
                String num = args.optString("number", "");
                String msg = args.optString("message", "");
                try {
                    Intent i = new Intent(Intent.ACTION_SENDTO,
                            Uri.parse("smsto:" + Uri.encode(num)));
                    i.putExtra("sms_body", msg);
                    startActivity(i);
                    return "SMS compose opened for " + num;
                } catch (ActivityNotFoundException e) {
                    return "No SMS app found";
                }
            }
            case "make_call": {
                String target = args.optString("number", "").trim();
                if (target.isEmpty()) return "No number given";
                if (!target.matches("[0-9+\\-() ]+")) {
                    String num = lookupContact(target);
                    if (num != null) target = num;
                    else return "Contact '" + target + "' not found in contacts";
                }
                startActivity(new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(target))));
                return "Dialing " + target;
            }
            case "open_url": {
                String url = args.optString("url", "");
                if (!url.startsWith("http")) url = "https://" + url;
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                return "Opened " + url;
            }
            case "navigate": {
                String dest = args.optString("destination", "");
                Uri uri = Uri.parse("geo:0,0?q=" + Uri.encode(dest));
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
                return "Navigation opened to " + dest;
            }
            case "set_alarm": {
                int hour = args.optInt("hour", -1);
                int minute = args.optInt("minute", -1);
                String label = args.optString("label", "VAYU Alarm");
                if (hour < 0 || minute < 0) return "hour and minute required";
                Calendar c = Calendar.getInstance();
                c.set(Calendar.HOUR_OF_DAY, hour);
                c.set(Calendar.MINUTE, minute);
                c.set(Calendar.SECOND, 0);
                if (c.getTimeInMillis() <= System.currentTimeMillis()) c.add(Calendar.DAY_OF_YEAR, 1);
                Intent i = new Intent(this, MainActivity.class)
                        .setAction(ACTION_ALARM)
                        .putExtra("label", label);
                PendingIntent pi = PendingIntent.getActivity(this, 1001, i,
                        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
                AlarmManager am = (AlarmManager) getSystemService(ALARM_SERVICE);
                if (Build.VERSION.SDK_INT >= 31 && !am.canScheduleExactAlarms()) {
                    try {
                        startActivity(new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                                Uri.parse("package:" + getPackageName())));
                    } catch (Exception ignored) {}
                    return "Exact alarm permission needed — please allow alarms for VAYU";
                }
                am.setAlarmClock(new AlarmManager.AlarmClockInfo(c.getTimeInMillis(), pi), pi);
                String t = String.format(Locale.US, "%02d:%02d", hour, minute);
                return "Alarm set for " + t + " (" + label + ")";
            }
            case "set_timer": {
                int secs = args.optInt("seconds", 0);
                String label = args.optString("label", "Timer");
                if (secs <= 0) return "seconds required";
                if (timerRunnable != null) mainHandler.removeCallbacks(timerRunnable);
                final long end = SystemClock.elapsedRealtime() + secs * 1000L;
                timerRunnable = () -> {
                    long left = (end - SystemClock.elapsedRealtime());
                    if (left <= 0) {
                        fireTimer(label);
                    } else {
                        mainHandler.postDelayed(timerRunnable, Math.min(1000, left));
                    }
                };
                mainHandler.postDelayed(timerRunnable, secs * 1000L);
                return "Timer set for " + secs + " seconds (" + label + ")";
            }
            case "set_volume": {
                int level = Math.max(0, Math.min(100, args.optInt("level", 50)));
                AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
                int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
                am.setStreamVolume(AudioManager.STREAM_MUSIC, Math.round(max * level / 100f), 0);
                return "Volume set to " + level + "%";
            }
            case "media": {
                String action = args.optString("action", "play").toLowerCase();
                AudioManager am = (AudioManager) getSystemService(AUDIO_SERVICE);
                int key;
                switch (action) {
                    case "play": key = KeyEvent.KEYCODE_MEDIA_PLAY; break;
                    case "pause": key = KeyEvent.KEYCODE_MEDIA_PAUSE; break;
                    case "next": key = KeyEvent.KEYCODE_MEDIA_NEXT; break;
                    case "prev": key = KeyEvent.KEYCODE_MEDIA_PREVIOUS; break;
                    case "stop": key = KeyEvent.KEYCODE_MEDIA_STOP; break;
                    case "volume_up": key = KeyEvent.KEYCODE_VOLUME_UP; break;
                    case "volume_down": key = KeyEvent.KEYCODE_VOLUME_DOWN; break;
                    case "mute": key = KeyEvent.KEYCODE_VOLUME_MUTE; break;
                    default: return "Unknown media action: " + action;
                }
                am.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, key));
                am.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, key));
                return "Media: " + action;
            }
            case "flashlight": {
                boolean on = args.optBoolean("on", true);
                CameraManager cm = (CameraManager) getSystemService(CAMERA_SERVICE);
                String id = null;
                for (String cid : cm.getCameraIdList()) {
                    CameraCharacteristics cc = cm.getCameraCharacteristics(cid);
                    Integer facing = cc.get(CameraCharacteristics.LENS_FACING);
                    if (facing != null && facing == CameraCharacteristics.LENS_FACING_BACK) {
                        id = cid; break;
                    }
                }
                if (id == null) id = cm.getCameraIdList()[0];
                cm.setTorchMode(id, on);
                return "Flashlight " + (on ? "on" : "off");
            }
            case "set_wifi": {
                boolean on = args.optBoolean("on", true);
                android.net.wifi.WifiManager wm =
                        (android.net.wifi.WifiManager) getApplicationContext()
                                .getSystemService(WIFI_SERVICE);
                boolean ok = false;
                try {
                    if (Build.VERSION.SDK_INT >= 29) {
                        wm.setWifiEnabled(on);
                        ok = on == (wm.getWifiState() == android.net.wifi.WifiManager.WIFI_STATE_ENABLED);
                    } else {
                        ok = wm.setWifiEnabled(on);
                    }
                } catch (Exception e) {
                    return "WiFi control restricted on this Android version";
                }
                return (ok ? "WiFi turned " + (on ? "on" : "off")
                        : "WiFi change may need manual approval (Android 13+)");
            }
            case "set_bluetooth": {
                boolean on = args.optBoolean("on", true);
                android.bluetooth.BluetoothAdapter ba =
                        android.bluetooth.BluetoothAdapter.getDefaultAdapter();
                if (ba == null) return "No Bluetooth adapter";
                try {
                    if (Build.VERSION.SDK_INT >= 33) {
                        if (ContextCompat.checkSelfPermission(this,
                                Manifest.permission.BLUETOOTH_CONNECT)
                                != PackageManager.PERMISSION_GRANTED) {
                            return "Bluetooth permission needed";
                        }
                    }
                    boolean ok = on ? ba.enable() : ba.disable();
                    return (ok ? "Bluetooth turned " + (on ? "on" : "off")
                            : "Bluetooth change may need manual approval (Android 13+)");
                } catch (Exception e) {
                    return "Bluetooth control restricted on this Android version";
                }
            }
            case "set_brightness": {
                int level = Math.max(1, Math.min(100, args.optInt("level", 50)));
                if (Build.VERSION.SDK_INT >= 23 && !Settings.System.canWrite(this)) {
                    try {
                        startActivity(new Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS,
                                Uri.parse("package:" + getPackageName())));
                    } catch (Exception ignored) {}
                    return "Permission needed — please allow " +
                            "'Modify system settings' for VAYU, then ask again";
                }
                Settings.System.putInt(getContentResolver(),
                        Settings.System.SCREEN_BRIGHTNESS_MODE,
                        Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL);
                Settings.System.putInt(getContentResolver(),
                        Settings.System.SCREEN_BRIGHTNESS,
                        Math.round(level * 255f / 100f));
                return "Brightness set to " + level + "%";
            }
            case "vibrate": {
                int ms = Math.max(0, args.optInt("ms", 300));
                Vibrator v = (Vibrator) getSystemService(VIBRATOR_SERVICE);
                if (v != null && v.hasVibrator()) v.vibrate(ms);
                return "Vibrated";
            }
            case "share": {
                String text = args.optString("text", "");
                Intent i = new Intent(Intent.ACTION_SEND);
                i.setType("text/plain");
                i.putExtra(Intent.EXTRA_TEXT, text);
                startActivity(Intent.createChooser(i, "Share via VAYU"));
                return "Share sheet opened";
            }
            case "clipboard": {
                String action = args.optString("action", "read");
                ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                if ("write".equals(action)) {
                    String text = args.optString("text", "");
                    cm.setPrimaryClip(ClipData.newPlainText("vayu", text));
                    return "Copied to clipboard";
                }
                if (cm.hasPrimaryClip()) {
                    CharSequence t = cm.getPrimaryClip().getItemAt(0).coerceToText(this);
                    return t == null ? "Clipboard is empty" : t.toString();
                }
                return "Clipboard is empty";
            }
            case "battery": {
                BatteryManager bm = (BatteryManager) getSystemService(BATTERY_SERVICE);
                int level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
                Intent b = registerReceiver(null,
                        new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));
                int status = b == null ? 0 : b.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
                boolean charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                        || status == BatteryManager.BATTERY_STATUS_FULL;
                return "Battery " + level + "%" + (charging ? " (charging)" : "");
            }
            case "device_info": {
                JSONObject o = new JSONObject(buildSysInfoJson());
                return "Device: " + o.optString("device") + " · Android " + o.optString("android")
                        + " · RAM " + o.optString("ramPct") + "% used · Storage "
                        + o.optString("storage");
            }
            case "open_settings": {
                String page = args.optString("page", "").toLowerCase();
                Intent i = null;
                switch (page) {
                    case "wifi": i = new Intent(Settings.ACTION_WIFI_SETTINGS); break;
                    case "bluetooth": i = new Intent(Settings.ACTION_BLUETOOTH_SETTINGS); break;
                    case "battery": i = new Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS); break;
                    case "display": i = new Intent(Settings.ACTION_DISPLAY_SETTINGS); break;
                    case "sound": i = new Intent(Settings.ACTION_SOUND_SETTINGS); break;
                    case "storage": i = new Intent(Settings.ACTION_INTERNAL_STORAGE_SETTINGS); break;
                    case "apps": i = new Intent(Settings.ACTION_APPLICATION_SETTINGS); break;
                    case "location": i = new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS); break;
                    case "about": i = new Intent(Settings.ACTION_DEVICE_INFO_SETTINGS); break;
                    default:
                        return "Unknown settings page: " + page +
                                " (wifi|bluetooth|battery|display|sound|storage|apps|location|about)";
                }
                startActivity(i);
                return "Opened " + page + " settings";
            }
            default:
                return "Unknown tool: " + name;
        }
    }

    /* ---------------- helpers ---------------- */
    private String findAppPackage(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> ris = getPackageManager().queryIntentActivities(launcher, 0);
        ResolveInfo best = null;
        int bestScore = 0;
        for (ResolveInfo ri : ris) {
            String label = ri.loadLabel(getPackageManager()).toString().toLowerCase(Locale.ROOT);
            if (label.equals(lower)) return ri.activityInfo.packageName;
            if (label.contains(lower) || lower.contains(label)) {
                int score = Math.min(label.length(), lower.length());
                if (score > bestScore) { bestScore = score; best = ri; }
            }
        }
        return best == null ? null : best.activityInfo.packageName;
    }

    private String suggestApp(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        String[] common = {
                "whatsapp", "instagram", "youtube", "settings", "spotify", "camera",
                "gallery", "photos", "phone", "dialer", "messages", "chrome", "gmail",
                "maps", "calculator", "clock", "calendar", "files", "notes", "music"
        };
        for (String c : common) {
            if (c.contains(lower) || lower.contains(c)) return c;
        }
        return null;
    }

    private String lookupContact(String name) {
        try {
            android.database.Cursor c = getContentResolver().query(
                    ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                    new String[]{ContactsContract.CommonDataKinds.Phone.NUMBER},
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?",
                    new String[]{"%" + name + "%"}, null);
            if (c != null) {
                while (c.moveToNext()) {
                    String num = c.getString(0);
                    if (num != null && !num.trim().isEmpty()) {
                        c.close();
                        return num.trim();
                    }
                }
                c.close();
            }
        } catch (Exception ignored) {}
        return null;
    }

    private String buildSysInfoJson() {
        try {
            JSONObject o = new JSONObject();
            BatteryManager bm = (BatteryManager) getSystemService(BATTERY_SERVICE);
            int level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            Intent b = registerReceiver(null,
                    new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            int status = b == null ? 0 : b.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
            boolean charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                    || status == BatteryManager.BATTERY_STATUS_FULL;
            o.put("batteryPct", level);
            o.put("charging", charging);

            android.app.ActivityManager am = (android.app.ActivityManager) getSystemService(ACTIVITY_SERVICE);
            android.app.ActivityManager.MemoryInfo mi = new android.app.ActivityManager.MemoryInfo();
            am.getMemoryInfo(mi);
            long total = mi.totalMem, avail = mi.availMem;
            o.put("ramPct", Math.round((total - avail) * 100f / total));

            StatFs sf = new StatFs(Environment.getDataDirectory().getAbsolutePath());
            long stot = sf.getTotalBytes(), savail = sf.getAvailableBytes();
            o.put("storage", formatSize(savail) + " free of " + formatSize(stot));

            ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            NetworkInfo ni = cm == null ? null : cm.getActiveNetworkInfo();
            String net = "OFFLINE";
            if (ni != null && ni.isConnected()) {
                net = ni.getType() == ConnectivityManager.TYPE_WIFI ? "WIFI" : "MOBILE";
            }
            o.put("network", net);

            o.put("device", Build.MANUFACTURER + " " + Build.MODEL);
            o.put("model", Build.MODEL);
            o.put("android", Build.VERSION.RELEASE);
            long up = SystemClock.elapsedRealtime() / 1000;
            o.put("uptime", String.format(Locale.US, "%dh %02dm", up / 3600, (up % 3600) / 60));
            o.put("ramTotal", formatSize(total));
            return o.toString();
        } catch (Exception e) {
            return "{}";
        }
    }

    private String formatSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        int e = (int) (Math.log(bytes) / Math.log(1024));
        String[] u = {"KB", "MB", "GB", "TB"};
        return String.format(Locale.US, "%.1f %s", bytes / Math.pow(1024, e), u[e - 1]);
    }

    private void callJs(String js) {
        runOnUiThread(() -> {
            try {
                webView.evaluateJavascript(js, null);
            } catch (Exception e) {
                Log.e(TAG, "callJs: " + e);
            }
        });
    }

    /* ---------------- Speech recognition (STT) ---------------- */
    private void startRecognition(boolean wake) {
        if (speechRecognizer == null) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
            recognizerIntent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            recognizerIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            recognizerIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US");
            recognizerIntent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
            recognizerIntent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3);
            speechRecognizer.setRecognitionListener(new RecognitionListener() {
                @Override public void onReadyForSpeech(Bundle p) { }
                @Override public void onBeginningOfSpeech() { }
                @Override public void onRmsChanged(float rms) { }
                @Override public void onBufferReceived(byte[] b) { }
                @Override public void onEndOfSpeech() {
                    isNativeListening = false;
                }
                @Override public void onError(int error) {
                    isNativeListening = false;
                    if (wakeWordMode) {
                        mainHandler.postDelayed(() -> startRecognition(true), 1200);
                        return;
                    }
                    String msg = errorMessage(error);
                    callJs("window.VayuNative&&window.VayuNative.onSpeechError(" +
                            JSONObject.quote(msg) + ")");
                }
                @Override public void onResults(android.os.Bundle results) {
                    ArrayList<String> list = results
                            .getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if (list != null && !list.isEmpty()) {
                        String text = list.get(0);
                        if (wakeWordMode) {
                            callJs("window.VayuNative&&window.VayuNative.onWakeWord(" +
                                    JSONObject.quote(text) + ")");
                            mainHandler.postDelayed(() -> startRecognition(true), 1500);
                        } else {
                            isNativeListening = false;
                            callJs("window.VayuNative&&window.VayuNative.onSpeechResult(" +
                                    JSONObject.quote(text) + ")");
                        }
                    } else if (!wakeWordMode) {
                        callJs("window.VayuNative&&window.VayuNative.onSpeechError(" +
                                JSONObject.quote("No speech detected") + ")");
                    }
                }
                @Override public void onPartialResults(android.os.Bundle partial) { }
                @Override public void onEvent(int t, android.os.Bundle b) { }
            });
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestRuntimePermissions();
            callJs("window.VayuNative&&window.VayuNative.onSpeechError(" +
                    JSONObject.quote("Microphone permission needed") + ")");
            return;
        }
        try {
            speechRecognizer.startListening(recognizerIntent);
            isNativeListening = true;
            if (!wake) callJs("window.VayuNative&&window.VayuNative.onSpeechStart()");
        } catch (Exception e) {
            callJs("window.VayuNative&&window.VayuNative.onSpeechError(" +
                    JSONObject.quote("Speech engine unavailable") + ")");
        }
    }

    private String errorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_NO_MATCH: return "No speech detected";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT: return "Listening timed out";
            case SpeechRecognizer.ERROR_NETWORK: return "Network error";
            case SpeechRecognizer.ERROR_AUDIO: return "Microphone error";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS: return "Microphone permission needed";
            default: return "Voice error (" + error + ")";
        }
    }

    /* ---------------- TTS ---------------- */
    private void initTts() {
        tts = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS) {
                tts.setLanguage(Locale.US);
                tts.setSpeechRate(ttsRate);
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String id) {
                        callJs("window.VayuNative&&window.VayuNative.onSpeakStart()");
                    }
                    @Override public void onDone(String id) {
                        callJs("window.VayuNative&&window.VayuNative.onSpeakDone()");
                    }
                    @Override public void onError(String id) {
                        callJs("window.VayuNative&&window.VayuNative.onSpeakDone()");
                    }
                });
            }
        });
    }

    private void speakTts(String text) {
        if (tts == null) return;
        String clean = text.replaceAll("[#*`>_~\\[\\]]", "").trim();
        if (clean.isEmpty()) return;
        tts.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "vayu_" + System.currentTimeMillis());
    }

    /* ---------------- Camera ---------------- */
    private void openCamera() {
        try {
            cameraFile = new File(getExternalCacheDir(), "vayu_photo.jpg");
            Uri uri = FileProvider.getUriForFile(this, "com.vayu.app.fileprovider", cameraFile);
            Intent i = new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
            i.putExtra(android.provider.MediaStore.EXTRA_OUTPUT, uri);
            i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivityForResult(i, REQ_CAMERA);
        } catch (Exception e) {
            callJs("window.VayuNative&&window.VayuNative.onPhotoCancel()");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_CAMERA) {
            if (resultCode == Activity.RESULT_OK && cameraFile != null && cameraFile.exists()) {
                try {
                    BitmapFactory.Options opts = new BitmapFactory.Options();
                    opts.inSampleSize = 2;
                    Bitmap bmp = BitmapFactory.decodeFile(cameraFile.getAbsolutePath(), opts);
                    if (bmp == null) throw new Exception("decode failed");
                    int maxDim = 1280;
                    if (Math.max(bmp.getWidth(), bmp.getHeight()) > maxDim) {
                        float scale = maxDim / (float) Math.max(bmp.getWidth(), bmp.getHeight());
                        bmp = Bitmap.createScaledBitmap(bmp,
                                Math.round(bmp.getWidth() * scale),
                                Math.round(bmp.getHeight() * scale), true);
                    }
                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    bmp.compress(Bitmap.CompressFormat.JPEG, 82, out);
                    byte[] bytes = out.toByteArray();
                    String b64 = Base64.encodeToString(bytes, Base64.NO_WRAP);
                    callJs("window.VayuNative&&window.VayuNative.onPhoto(" +
                            JSONObject.quote(b64) + "," + JSONObject.quote("image/jpeg") + ")");
                } catch (Exception e) {
                    callJs("window.VayuNative&&window.VayuNative.onPhotoCancel()");
                }
            } else {
                callJs("window.VayuNative&&window.VayuNative.onPhotoCancel()");
            }
        }
    }

    /* ---------------- Alarm / timer fire ---------------- */
    private void fireAlarm(String label) {
        String msg = label == null || label.isEmpty() ? "VAYU Alarm" : label;
        speakTts("Alarm. " + msg);
        Vibrator v = (Vibrator) getSystemService(VIBRATOR_SERVICE);
        if (v != null) v.vibrate(new long[]{0, 400, 200, 400, 200, 800}, -1);
        notify("⏰ " + msg, "Alarm time!", 1001);
        runOnUiThread(() -> {
            try {
                AlertDialog d = new AlertDialog.Builder(this)
                        .setTitle("⏰ ALARM — " + msg)
                        .setMessage(new SimpleDateFormat("hh:mm a", Locale.US).format(new java.util.Date()))
                        .setPositiveButton("DISMISS", (di, w) -> {
                            if (v != null) v.cancel();
                        })
                        .setCancelable(false)
                        .create();
                d.getWindow().setType(android.view.WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY);
                d.show();
            } catch (Exception e) {
                Log.e(TAG, "alarm dialog: " + e);
            }
        });
    }

    private void fireTimer(String label) {
        String msg = label == null || label.isEmpty() ? "Timer done" : label;
        speakTts("Timer finished. " + msg);
        Vibrator v = (Vibrator) getSystemService(VIBRATOR_SERVICE);
        if (v != null) v.vibrate(new long[]{0, 300, 150, 300, 150, 600}, -1);
        notify("⏱ " + msg, "Timer finished!", 1002);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (ACTION_ALARM.equals(intent.getAction())) {
            fireAlarm(intent.getStringExtra("label"));
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (wakeWordMode) {
            try {
                if (speechRecognizer != null) speechRecognizer.stopListening();
            } catch (Exception ignored) {}
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (wakeWordMode && !isNativeListening) {
            mainHandler.postDelayed(() -> startRecognition(true), 400);
        }
    }

    @Override
    protected void onDestroy() {
        if (speechRecognizer != null) {
            try { speechRecognizer.destroy(); } catch (Exception ignored) {}
        }
        if (tts != null) tts.shutdown();
        if (timerRunnable != null) mainHandler.removeCallbacks(timerRunnable);
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
