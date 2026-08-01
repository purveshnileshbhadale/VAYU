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
    private static final int PHONE_LINK_PORT = 8080;

    private static final java.util.Map<String, String[]> KNOWN_APPS = buildKnownApps();
    private static java.util.Map<String, String[]> buildKnownApps() {
        java.util.Map<String, String[]> m = new java.util.HashMap<>();
        m.put("whatsapp", new String[]{"com.whatsapp", "com.whatsapp.w4b"});
        m.put("instagram", new String[]{"com.instagram.android"});
        m.put("youtube", new String[]{"com.google.android.youtube", "org.videolan.vlc"});
        m.put("youtube music", new String[]{"com.google.android.apps.youtube.music"});
        m.put("spotify", new String[]{"com.spotify.music"});
        m.put("music", new String[]{"com.google.android.apps.youtube.music", "com.spotify.music"});
        m.put("chrome", new String[]{"com.android.chrome"});
        m.put("browser", new String[]{"com.android.chrome", "com.microsoft.emmx"});
        m.put("gmail", new String[]{"com.google.android.gm"});
        m.put("maps", new String[]{"com.google.android.apps.maps"});
        m.put("google maps", new String[]{"com.google.android.apps.maps"});
        m.put("camera", new String[]{"com.android.camera", "com.sec.android.app.camera",
                "com.miui.camera", "com.google.android.GoogleCamera", "org.lineageos.snap"});
        m.put("gallery", new String[]{"com.google.android.apps.photos", "com.android.gallery3d",
                "com.sec.android.gallery3d", "com.miui.gallery"});
        m.put("photos", new String[]{"com.google.android.apps.photos"});
        m.put("phone", new String[]{"com.android.dialer", "com.google.android.dialer",
                "com.sec.android.app.dialertab", "com.samsung.android.dialer"});
        m.put("dialer", new String[]{"com.android.dialer", "com.google.android.dialer"});
        m.put("messages", new String[]{"com.google.android.apps.messaging", "com.android.mms"});
        m.put("sms", new String[]{"com.google.android.apps.messaging", "com.android.mms"});
        m.put("settings", new String[]{"com.android.settings", "com.google.android.settings"});
        m.put("play store", new String[]{"com.android.vending"});
        m.put("playstore", new String[]{"com.android.vending"});
        m.put("store", new String[]{"com.android.vending"});
        m.put("telegram", new String[]{"org.telegram.messenger"});
        m.put("x", new String[]{"com.twitter.android"});
        m.put("twitter", new String[]{"com.twitter.android"});
        m.put("facebook", new String[]{"com.facebook.katana"});
        m.put("snapchat", new String[]{"com.snapchat.android"});
        m.put("linkedin", new String[]{"com.linkedin.android"});
        m.put("netflix", new String[]{"com.netflix.mediaclient"});
        m.put("prime video", new String[]{"com.amazon.avod.thirdpartyclient"});
        m.put("amazon", new String[]{"com.amazon.mShop.android.shopping"});
        m.put("flipkart", new String[]{"com.flipkart.android"});
        m.put("meesho", new String[]{"com.meesho.supply"});
        m.put("paytm", new String[]{"net.one97.paytm"});
        m.put("phonepe", new String[]{"com.phonepe.app"});
        m.put("gpay", new String[]{"com.google.android.apps.nbu.paisa.user"});
        m.put("google pay", new String[]{"com.google.android.apps.nbu.paisa.user"});
        m.put("truecaller", new String[]{"com.truecaller"});
        m.put("calculator", new String[]{"com.google.android.calculator", "com.sec.android.app.popupcalculator",
                "com.miui.calculator", "com.android.calculator2"});
        m.put("clock", new String[]{"com.google.android.deskclock", "com.sec.android.app.clockpackage"});
        m.put("alarm", new String[]{"com.google.android.deskclock", "com.sec.android.app.clockpackage"});
        m.put("calendar", new String[]{"com.google.android.calendar", "com.samsung.android.calendar"});
        m.put("files", new String[]{"com.google.android.apps.nbu.files", "com.android.documentsui",
                "com.sec.android.app.myfiles", "com.mi.android.globalFileexplorer"});
        m.put("file manager", new String[]{"com.google.android.apps.nbu.files", "com.android.documentsui"});
        m.put("notes", new String[]{"com.google.android.keep", "com.samsung.android.app.notes"});
        m.put("keep", new String[]{"com.google.android.keep"});
        m.put("drive", new String[]{"com.google.android.apps.docs"});
        m.put("docs", new String[]{"com.google.android.apps.docs.editors.docs"});
        m.put("sheets", new String[]{"com.google.android.apps.docs.editors.sheets"});
        m.put("slides", new String[]{"com.google.android.apps.docs.editors.slides"});
        m.put("meet", new String[]{"com.google.android.apps.meetings", "com.google.android.apps.tachyon"});
        m.put("zoom", new String[]{"us.zoom.videomeetings"});
        m.put("weather", new String[]{"com.google.android.apps.weather", "com.samsung.android.weather"});
        m.put("hotstar", new String[]{"in.startv.hotstar"});
        m.put("hot star", new String[]{"in.startv.hotstar"});
        m.put("shareit", new String[]{"com.lenovo.anyshare.gps"});
        m.put("viber", new String[]{"com.viber.voip"});
        m.put("discord", new String[]{"com.discord"});
        m.put("signal", new String[]{"org.thoughtcrime.securesms"});
        m.put("reddit", new String[]{"com.reddit.frontpage"});
        m.put("pinterest", new String[]{"com.pinterest"});
        m.put("tiktok", new String[]{"com.zhiliaoapp.musically"});
        m.put("duolingo", new String[]{"com.duolingo"});
        m.put("chatgpt", new String[]{"com.openai.chatgpt"});
        m.put("chat gpt", new String[]{"com.openai.chatgpt"});
        m.put("gemini", new String[]{"com.google.android.apps.bard"});
        m.put("google", new String[]{"com.google.android.googlequicksearchbox"});
        m.put("google assistant", new String[]{"com.google.android.googlequicksearchbox"});
        m.put("youtube kids", new String[]{"com.google.android.apps.youtube.kids"});
        m.put("pubg", new String[]{"com.tencent.ig", "com.pubg.imobile"});
        m.put("bgmi", new String[]{"com.pubg.imobile"});
        m.put("free fire", new String[]{"com.dts.freefireth"});
        m.put("canva", new String[]{"com.canva.editor"});
        m.put("capcut", new String[]{"com.lemon.lvoverseas"});
        m.put("inshot", new String[]{"com.camerasideas.instashot"});
        m.put("vsco", new String[]{"com.vsco.cam"});
        m.put("shazam", new String[]{"com.shazam.android"});
        m.put("soundcloud", new String[]{"com.soundcloud.android"});
        m.put("audible", new String[]{"com.audible.application"});
        m.put("kindle", new String[]{"com.amazon.kindle"});
        m.put("swiggy", new String[]{"in.swiggy.android"});
        m.put("zomato", new String[]{"com.application.zomato"});
        m.put("uber", new String[]{"com.ubercab"});
        m.put("ola", new String[]{"com.olacabs.customer"});
        m.put("irctc", new String[]{"cris.org.in.prs.ima"});
        m.put("paytm money", new String[]{"com.paytm.money"});
        m.put("upi", new String[]{"com.google.android.apps.nbu.paisa.user", "com.phonepe.app", "net.one97.paytm"});
        m.put("youtube tv", new String[]{"com.google.android.apps.youtube.unplugged"});
        m.put("maps gps", new String[]{"com.google.android.apps.maps"});
        m.put("recorder", new String[]{"com.google.android.apps.recorder", "com.samsung.android.voice recorder"});
        m.put("voice recorder", new String[]{"com.google.android.apps.recorder", "com.samsung.android.voice recorder"});
        m.put("health", new String[]{"com.google.android.apps.fitness", "com.samsung.android.service.health"});
        m.put("samsung health", new String[]{"com.samsung.android.service.health"});
        return m;
    }

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
    private PhoneLinkServer phoneServer;
    private String linkPin = "8421";

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
        linkPin = getSharedPreferences("vayu_prefs", MODE_PRIVATE)
                .getString("link_pin", "8421");
        if (getSharedPreferences("vayu_prefs", MODE_PRIVATE).getBoolean("phone_link", true)) {
            startPhoneLink();
        }
        notifyUpdateIfNew();
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

        @JavascriptInterface
        public void setPhoneLink(boolean enabled) {
            getSharedPreferences("vayu_prefs", MODE_PRIVATE)
                    .edit().putBoolean("phone_link", enabled).apply();
            runOnUiThread(() -> {
                if (enabled) startPhoneLink();
                else stopPhoneLink();
            });
        }

        @JavascriptInterface
        public void setLinkPin(String pin) {
            if (pin != null && !pin.trim().isEmpty()) {
                linkPin = pin.trim();
                getSharedPreferences("vayu_prefs", MODE_PRIVATE)
                        .edit().putString("link_pin", linkPin).apply();
                if (phoneServer != null) phoneServer.setPin(linkPin);
            }
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
                String app = args.optString("app_name", "").trim();
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
                for (ResolveInfo ri : ris) {
                    String label = ri.loadLabel(getPackageManager()).toString();
                    arr.put(label + "|" + ri.activityInfo.packageName);
                }
                return "Installed apps (name|package): " + arr.toString();
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
                try {
                    startActivity(new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(target))));
                    return "Dialing " + target;
                } catch (ActivityNotFoundException e) {
                    return "No dialer app found on this device (tablets and Chromebooks may not support calls)";
                }
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
                try {
                    for (String cid : cm.getCameraIdList()) {
                        CameraCharacteristics cc = cm.getCameraCharacteristics(cid);
                        Integer facing = cc.get(CameraCharacteristics.LENS_FACING);
                        Boolean hasFlash = cc.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                        if (hasFlash != null && hasFlash
                                && (facing == null
                                || facing == CameraCharacteristics.LENS_FACING_BACK)) {
                            id = cid; break;
                        }
                    }
                    if (id == null && cm.getCameraIdList().length > 0) {
                        id = cm.getCameraIdList()[0];
                    }
                } catch (CameraAccessException | IllegalArgumentException e) {
                    return "No camera available on this device";
                }
                if (id == null) return "This device has no camera or flashlight";
                try {
                    cm.setTorchMode(id, on);
                } catch (CameraAccessException | SecurityException e) {
                    return "Flashlight unavailable right now";
                }
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
            case "rotate": {
                boolean on = args.optBoolean("on", true);
                if (Build.VERSION.SDK_INT >= 23 && !Settings.System.canWrite(this)) {
                    try {
                        startActivity(new Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS,
                                Uri.parse("package:" + getPackageName())));
                    } catch (Exception ignored) {}
                    return "Permission needed — please allow 'Modify system settings' for VAYU, then ask again";
                }
                Settings.System.putInt(getContentResolver(),
                        Settings.System.ACCELEROMETER_ROTATION, on ? 1 : 0);
                return "Auto-rotate turned " + (on ? "on" : "off");
            }
            case "dnd": {
                boolean on = args.optBoolean("on", true);
                NotificationManager nm = getSystemService(NotificationManager.class);
                if (Build.VERSION.SDK_INT >= 23 && nm != null) {
                    if (!nm.isNotificationPolicyAccessGranted()) {
                        try {
                            startActivity(new Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS));
                        } catch (Exception ignored) {}
                        return "Permission needed — please allow 'Do Not Disturb access' for VAYU, then ask again";
                    }
                    int filter = on
                            ? NotificationManager.INTERRUPTION_FILTER_PRIORITY
                            : NotificationManager.INTERRUPTION_FILTER_ALL;
                    nm.setInterruptionFilter(filter);
                    return "Do Not Disturb " + (on ? "on" : "off");
                }
                try {
                    startActivity(new Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS));
                } catch (Exception ignored) {}
                return "Opened Do Not Disturb settings";
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

    /* ---------------- Phone link: laptop controls this phone ---------------- */
    private void startPhoneLink() {
        if (phoneServer != null && phoneServer.isRunning()) return;
        try {
            phoneServer = new PhoneLinkServer(PHONE_LINK_PORT, linkPin);
            phoneServer.start();
            Log.i(TAG, "Phone link on " + getLanIp() + ":" + PHONE_LINK_PORT);
        } catch (Exception e) {
            Log.e(TAG, "phone link start: " + e);
        }
    }

    private void stopPhoneLink() {
        if (phoneServer != null) {
            phoneServer.stop();
            phoneServer = null;
        }
    }

    private String getLanIp() {
        try {
            java.util.Enumeration<java.net.NetworkInterface> nis =
                    java.net.NetworkInterface.getNetworkInterfaces();
            while (nis != null && nis.hasMoreElements()) {
                java.net.NetworkInterface ni = nis.nextElement();
                if (!ni.isUp() || ni.isLoopback()) continue;
                java.util.Enumeration<java.net.InetAddress> as = ni.getInetAddresses();
                while (as.hasMoreElements()) {
                    java.net.InetAddress a = as.nextElement();
                    if (!a.isLoopbackAddress() && a instanceof java.net.Inet4Address) {
                        return a.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) {}
        return "127.0.0.1";
    }

    private String phoneLinkUrl() {
        return (phoneServer != null && phoneServer.isRunning())
                ? "http://" + getLanIp() + ":" + PHONE_LINK_PORT : "";
    }

    private void notifyUpdateIfNew() {
        try {
            android.content.SharedPreferences prefs =
                    getSharedPreferences("vayu_prefs", MODE_PRIVATE);
            int lastVer = prefs.getInt("last_version", 0);
            int curVer = appVersionCode();
            if (curVer <= lastVer) return;
            prefs.edit().putInt("last_version", curVer).apply();
            if (curVer >= 4) {
                notify("VAYU 1.3.0 — Jarvis Edition installed",
                        "Jarvis-style voice, Bixby-like app opening on any Android device, auto-rotate, Do Not Disturb and cross-device control. Open VAYU to see what's new.",
                        3001);
            }
        } catch (Exception ignored) {}
    }

    private int appVersionCode() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
        } catch (Exception e) {
            return 0;
        }
    }

    private String appVersionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "1.3.0";
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        notifyUpdateIfNew();
    }

    /* ---- tiny stdlib HTTP server: GET /status, GET /auth?pin=, POST /tool ---- */
    private class PhoneLinkServer {
        private final int port;
        private volatile boolean running = false;
        private volatile String pin;
        private volatile String token;
        private java.net.ServerSocket socket;
        private Thread thread;

        PhoneLinkServer(int port, String pin) {
            this.port = port;
            this.pin = pin;
        }

        boolean isRunning() { return running; }

        void setPin(String p) { this.pin = p; }

        void start() throws Exception {
            socket = new java.net.ServerSocket(port);
            running = true;
            thread = new Thread(this::acceptLoop, "vayu-phone-link");
            thread.setDaemon(true);
            thread.start();
        }

        void stop() {
            running = false;
            try { if (socket != null) socket.close(); } catch (Exception ignored) {}
        }

        private void acceptLoop() {
            while (running) {
                try {
                    java.net.Socket s = socket.accept();
                    handle(s);
                } catch (Exception ignored) {}
            }
        }

        private void handle(java.net.Socket s) {
            try {
                s.setSoTimeout(8000);
                java.io.BufferedReader in = new java.io.BufferedReader(
                        new java.io.InputStreamReader(s.getInputStream()));
                java.io.OutputStream out = s.getOutputStream();

                String requestLine = in.readLine();
                if (requestLine == null) { s.close(); return; }
                String[] parts = requestLine.split(" ");
                String method = parts.length > 0 ? parts[0] : "";
                String path = parts.length > 1 ? parts[1] : "/";

                String line;
                int contentLength = 0;
                while ((line = in.readLine()) != null && !line.isEmpty()) {
                    String lower = line.toLowerCase();
                    if (lower.startsWith("content-length:")) {
                        try { contentLength = Integer.parseInt(line.split(":")[1].trim()); }
                        catch (Exception ignored) {}
                    }
                }
                String body = "";
                if (contentLength > 0 && contentLength < 4096) {
                    char[] buf = new char[contentLength];
                    int n = in.read(buf, 0, contentLength);
                    if (n > 0) body = new String(buf, 0, n);
                }

                String response;
                String status = "200 OK";

                String q = "";
                if (path.contains("?")) {
                    int qi = path.indexOf('?');
                    q = path.substring(qi + 1);
                    path = path.substring(0, qi);
                }

                if ("GET".equals(method) && "/status".equals(path)) {
                    JSONObject o = new JSONObject(buildSysInfoJson());
                    o.put("phoneLink", phoneLinkUrl());
                    o.put("version", appVersionName());
                    response = o.toString();
                } else if ("GET".equals(method) && "/auth".equals(path)) {
                    String given = param(q, "pin");
                    if (given != null && given.equals(pin)) {
                        token = java.util.UUID.randomUUID().toString().replace("-", "");
                        response = "{\"token\":\"" + token + "\"}";
                    } else {
                        status = "401 Unauthorized";
                        response = "{\"error\":\"wrong pin\"}";
                    }
                } else if ("POST".equals(method) && "/tool".equals(path)) {
                    if (!authorized(s, q)) {
                        status = "401 Unauthorized";
                        response = "{\"error\":\"unauthorized\"}";
                    } else {
                        try {
                            JSONObject req = new JSONObject(body);
                            String name = req.optString("name", "");
                            JSONObject args = req.optJSONObject("args");
                            if (args == null) args = new JSONObject();
                            String result = runTool(name, args);
                            recentTools.add(name);
                            response = new JSONObject().put("ok", true)
                                    .put("result", result).toString();
                        } catch (Exception e) {
                            status = "200 OK";
                            response = "{\"ok\":false,\"error\":\"" +
                                    JSONObject.quote(e.getMessage() == null
                                            ? "tool failed" : e.getMessage()) + "\"}";
                        }
                    }
                } else {
                    status = "404 Not Found";
                    response = "{\"error\":\"not found\"}";
                }

                byte[] bytes = response.getBytes("UTF-8");
                String head = "HTTP/1.1 " + status + "\r\n"
                        + "Content-Type: application/json\r\n"
                        + "Content-Length: " + bytes.length + "\r\n"
                        + "Access-Control-Allow-Origin: *\r\n"
                        + "Access-Control-Allow-Headers: X-Vayu-Token, Content-Type\r\n"
                        + "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                        + "Connection: close\r\n\r\n";
                out.write(head.getBytes("UTF-8"));
                out.write(bytes);
                out.flush();
                s.close();
            } catch (Exception ignored) {
                try { s.close(); } catch (Exception ignored2) {}
            }
        }

        private boolean authorized(java.net.Socket s, String q) {
            return token != null && token.length() > 0 && param(q, "token") != null
                    && param(q, "token").equals(token);
        }

        private String param(String q, String key) {
            try {
                for (String pair : q.split("&")) {
                    String[] kv = pair.split("=", 2);
                    if (kv.length == 2 && kv[0].equals(key)) {
                        return java.net.URLDecoder.decode(kv[1], "UTF-8");
                    }
                }
            } catch (Exception ignored) {}
            return null;
        }
    }

    private String findAppPackage(String name) {        String lower = name.toLowerCase(Locale.ROOT).trim();
        if (lower.isEmpty()) return null;
        String[] curated = KNOWN_APPS.get(lower);
        if (curated != null) {
            for (String pkg : curated) {
                if (getPackageManager().getLaunchIntentForPackage(pkg) != null) return pkg;
            }
        }
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> ris = getPackageManager().queryIntentActivities(launcher, 0);
        ResolveInfo best = null;
        int bestScore = 0;
        String plain = lower.replaceAll("[^a-z0-9]", "");
        for (ResolveInfo ri : ris) {
            String label = ri.loadLabel(getPackageManager()).toString().toLowerCase(Locale.ROOT);
            String pkg = ri.activityInfo.packageName;
            if (label.equals(lower) || pkg.equals(lower)) return ri.activityInfo.packageName;
            if (label.contains(lower) || lower.contains(label)) {
                int score = Math.min(label.length(), lower.length());
                if (score > bestScore) { bestScore = score; best = ri; }
            }
            String pkgPlain = pkg.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
            if (plain.length() >= 3 && (pkgPlain.contains(plain)
                    || pkgPlain.endsWith(plain))) {
                int score = Math.min(pkgPlain.length(), plain.length());
                if (score > bestScore) { bestScore = score; best = ri; }
            }
        }
        return best == null ? null : best.activityInfo.packageName;
    }

    private String suggestApp(String name) {
        String lower = name.toLowerCase(Locale.ROOT).trim();
        String[] common = {
                "whatsapp", "instagram", "youtube", "settings", "spotify", "camera",
                "gallery", "photos", "phone", "dialer", "messages", "chrome", "gmail",
                "maps", "calculator", "clock", "calendar", "files", "notes", "music",
                "telegram", "twitter", "facebook", "snapchat", "netflix", "paytm",
                "phonepe", "gpay", "truecaller", "play store", "hotstar", "zoom", "meet"
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
            o.put("phoneLink", phoneLinkUrl());
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
        stopPhoneLink();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
