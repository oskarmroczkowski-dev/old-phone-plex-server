package pl.serwerplex.status;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.media.AudioAttributes;
import android.media.AudioDeviceInfo;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.wifi.WifiManager;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashSet;

/**
 * Internet radio, controlled from the status page through ControlServer (port 8098).
 * Station list: http://127.0.0.1:8099/radio.json (a copy is kept in the app's storage in case the page server is down).
 * Plays with the screen off, reconnects when the stream breaks, stops when the Bluetooth speaker disconnects,
 * on the sleep timer and at 23:00.
 * Failsafe (1.3.3): backup addresses ("alt" field in radio.json and the current address from Radio Browser,
 * tried on 3 servers); after 6 quick attempts without internet it waits for the network to return (no limit),
 * and with a working network it retries less often for about 30 min, re-reading the addresses each time
 * (a fixed radio.json or a new Radio Browser address).
 */
final class RadioPlayer {
    private static final String TAG = "StatusRadio";
    private static final String LIST_URL = "http://127.0.0.1:8099/radio.json";
    private static final String[] RB_HOSTS = {"de1", "nl1", "at1"};   // Radio Browser servers, in order
    private static final int MAX_ATTEMPTS = 6;                         // quick attempts, every 5 s
    private static final long RETRY_MS = 5_000;
    // slow attempts when the network works but the station does not respond: about 30 min in total
    private static final long[] SLOW_RETRY_MS = {30_000, 60_000, 120_000, 300_000, 300_000, 300_000, 300_000, 300_000};
    private static final long NIGHT_SLEEP_MS = 60 * 60_000L;
    private static RadioPlayer instance;

    private final Context ctx;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final AudioManager audio;
    private final WifiManager.WifiLock wifiLock;
    private final AudioAttributes attrs = new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();
    private MediaPlayer mp;
    private AudioFocusRequest focus;
    private boolean noisyRegistered;

    // state (access under synchronized)
    private String state = "stopped";   // stopped | connecting | playing | error
    private String id = "";
    private String name = "";
    private String info = "";
    private String[] urls = new String[0];
    private int attempt;
    private int slowAttempt;            // slow attempts after the quick ones are used up
    private boolean waitingForNet;      // no internet: waiting for the network
    private long sleepUntil;
    private boolean wanted;
    private final ConnectivityManager conn;
    private boolean netCallbackOn;

    // the network is back: if we are waiting for it, connect right away (with refreshed addresses)
    private final ConnectivityManager.NetworkCallback netCallback = new ConnectivityManager.NetworkCallback() {
        @Override
        public void onAvailable(Network n) {
            boolean resume;
            synchronized (RadioPlayer.this) {
                resume = wanted && waitingForNet;
            }
            if (resume) {
                main.removeCallbacks(resolveAndStart);
                main.postDelayed(resolveAndStart, 3_000);   // give DNS and routing a moment after Wi-Fi returns
            }
        }
    };

    // re-read the station addresses (network: separate thread), then start
    private final Runnable resolveAndStart = new Runnable() {
        @Override
        public void run() {
            final String sid;
            synchronized (RadioPlayer.this) {
                if (!wanted) return;
                sid = id;
            }
            new Thread(new Runnable() {
                @Override
                public void run() {
                    String[] list = resolveUrls(sid);
                    synchronized (RadioPlayer.this) {
                        if (!wanted || !sid.equals(id)) return;
                        if (list != null) urls = list;
                        attempt = 0;
                        waitingForNet = false;
                    }
                    main.post(startRunnable);
                }
            }).start();
        }
    };

    private final Runnable startRunnable = new Runnable() {
        @Override
        public void run() {
            start();
        }
    };

    private final Runnable sleepRunnable = new Runnable() {
        @Override
        public void run() {
            stop("sleep timer");
        }
    };

    private final BroadcastReceiver noisy = new BroadcastReceiver() {
        @Override
        public void onReceive(Context c, Intent i) {
            stop("speaker disconnected");
        }
    };

    private final AudioManager.OnAudioFocusChangeListener focusListener = new AudioManager.OnAudioFocusChangeListener() {
        @Override
        public void onAudioFocusChange(int change) {
            if (change == AudioManager.AUDIOFOCUS_LOSS) {
                stop("another app took the audio");
            } else if (change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {
                if (mp != null && mp.isPlaying()) mp.pause();
            } else if (change == AudioManager.AUDIOFOCUS_GAIN) {
                if (mp != null && isWanted()) mp.start();
            }
        }
    };

    static synchronized RadioPlayer get(Context c) {
        if (instance == null) instance = new RadioPlayer(c.getApplicationContext());
        return instance;
    }

    private RadioPlayer(Context c) {
        ctx = c;
        audio = c.getSystemService(AudioManager.class);
        WifiManager wm = (WifiManager) c.getSystemService(Context.WIFI_SERVICE);
        wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "status:radio");
        wifiLock.setReferenceCounted(false);
        conn = c.getSystemService(ConnectivityManager.class);
    }

    private synchronized boolean isWanted() {
        return wanted;
    }

    /** Starts a station (called from the server thread: network access is allowed here). */
    void play(String sid) {
        JSONObject st = findStation(sid);
        String[] list = st == null ? null : urlsFor(st);
        if (list == null) {
            synchronized (this) {
                state = "error";
                info = "unknown station: " + sid;
            }
            return;
        }
        synchronized (this) {
            id = sid;
            name = st.optString("name");
            urls = list;
            attempt = 0;
            slowAttempt = 0;
            waitingForNet = false;
            wanted = true;
            info = "";
            if (sleepUntil == 0 && !Schedule.isDay()) sleepUntil = System.currentTimeMillis() + NIGHT_SLEEP_MS;
        }
        main.removeCallbacks(startRunnable);
        main.removeCallbacks(resolveAndStart);
        main.post(startRunnable);
    }

    void stop(final String reason) {
        synchronized (this) {
            wanted = false;
            state = "stopped";
            info = reason;
            sleepUntil = 0;
        }
        main.post(new Runnable() {
            @Override
            public void run() {
                main.removeCallbacks(startRunnable);
                main.removeCallbacks(resolveAndStart);
                main.removeCallbacks(sleepRunnable);
                releaseAll();
            }
        });
    }

    /** At 23:00 (AlarmReceiver): stop if something is playing. */
    void stopIfActive(String reason) {
        if (isWanted()) stop(reason);
    }

    void setSleep(int minutes) {
        synchronized (this) {
            sleepUntil = minutes > 0 ? System.currentTimeMillis() + minutes * 60_000L : 0;
        }
        main.post(new Runnable() {
            @Override
            public void run() {
                scheduleSleep();
            }
        });
    }

    void setVolume(int percent) {
        int max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        int idx = Math.round(Math.max(0, Math.min(100, percent)) * max / 100f);
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, idx, 0);
    }

    synchronized String stateJson() {
        try {
            JSONObject o = new JSONObject();
            o.put("state", state);
            o.put("id", id);
            o.put("name", name);
            o.put("info", info);
            o.put("sleepUntil", sleepUntil);
            o.put("now", System.currentTimeMillis());
            int max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
            o.put("volume", Math.round(audio.getStreamVolume(AudioManager.STREAM_MUSIC) * 100f / max));
            o.put("output", output());
            return o.toString();
        } catch (Exception e) {
            return "{\"state\":\"error\"}";
        }
    }

    // ---------- playback (main thread) ----------

    private void start() {
        String url;
        synchronized (this) {
            if (!wanted || urls.length == 0) return;
            url = urls[attempt % urls.length];
            state = "connecting";
        }
        releasePlayer();
        main.removeCallbacks(connectTimeout);
        if (!url.contains(".m3u8")) {
            startWeb(url);
            return;
        }
        if (!requestFocus()) {
            stop("no audio focus");
            return;
        }
        final MediaPlayer p = new MediaPlayer();
        mp = p;
        p.setAudioAttributes(attrs);
        p.setWakeMode(ctx, PowerManager.PARTIAL_WAKE_LOCK);
        p.setOnPreparedListener(new MediaPlayer.OnPreparedListener() {
            @Override
            public void onPrepared(MediaPlayer m) {
                if (m != mp) return;
                m.start();
                synchronized (RadioPlayer.this) {
                    state = "playing";
                    attempt = 0;
                    slowAttempt = 0;
                    info = "";
                }
            }
        });
        p.setOnErrorListener(new MediaPlayer.OnErrorListener() {
            @Override
            public boolean onError(MediaPlayer m, int what, int extra) {
                if (m == mp) retry("stream error " + what + "/" + extra);
                return true;
            }
        });
        p.setOnCompletionListener(new MediaPlayer.OnCompletionListener() {
            @Override
            public void onCompletion(MediaPlayer m) {
                if (m == mp) retry("stream ended");
            }
        });
        try {
            p.setDataSource(url);
            p.prepareAsync();
            if (!wifiLock.isHeld()) wifiLock.acquire();
            registerNoisy();
            scheduleSleep();
        } catch (Exception e) {
            retry("bad stream address");
        }
    }

    private void retry(String why) {
        Log.w(TAG, why);
        boolean giveUp = false, fast, noNet = false;
        long delay = RETRY_MS;
        synchronized (this) {
            if (!wanted) return;
            attempt++;
            fast = attempt < MAX_ATTEMPTS;
            if (fast) {
                state = "connecting";
                info = "reconnecting (" + attempt + ")";
            } else if (!hasInternet()) {
                // no internet: wait for the network with no limit (ends with Stop, the sleep timer or 23:00)
                noNet = true;
                waitingForNet = true;
                state = "connecting";
                info = "no internet, waiting for network";
            } else if (slowAttempt < SLOW_RETRY_MS.length) {
                delay = SLOW_RETRY_MS[slowAttempt++];
                state = "connecting";
                info = "station not responding, retrying in " + (delay >= 60_000 ? delay / 60_000 + " min" : delay / 1000 + " s");
            } else {
                giveUp = true;
                wanted = false;
                state = "error";
                info = why;
            }
        }
        releasePlayer();
        main.removeCallbacks(resolveAndStart);
        if (giveUp) {
            releaseAll();
        } else if (fast) {
            main.postDelayed(startRunnable, RETRY_MS);
        } else if (noNet) {
            registerNetCallback();
            main.postDelayed(resolveAndStart, 60_000);   // also every minute, just in case
        } else {
            main.postDelayed(resolveAndStart, delay);
        }
    }

    private boolean hasInternet() {
        try {
            NetworkCapabilities c = conn.getNetworkCapabilities(conn.getActiveNetwork());
            return c != null && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        } catch (Exception e) {
            return true;   // unknown: treat as a working network (slow attempts with a limit)
        }
    }

    private void registerNetCallback() {
        if (netCallbackOn) return;
        try {
            conn.registerDefaultNetworkCallback(netCallback);
            netCallbackOn = true;
        } catch (Exception e) {
            Log.w(TAG, "NetworkCallback not available", e);
        }
    }

    private void unregisterNetCallback() {
        if (!netCallbackOn) return;
        try {
            conn.unregisterNetworkCallback(netCallback);
        } catch (Exception ignored) {
        }
        netCallbackOn = false;
    }

    // ---------- Chromium engine (plain MP3/AAC streams: Android's player on realme never prepares them) ----------

    // g = playback number: events from the previous stream (e.g. an error while it is being stopped) are ignored
    private static final String PLAYER_HTML = "<!doctype html><html><body><audio id='a' preload='none'></audio><script>"
            + "var a=document.getElementById('a'),g=-1;"
            + "function play(u,n){g=n;a.src=u;a.load();var p=a.play();if(p)p.catch(function(e){if(g==n)Radio.onEvent('error',String(e),n);});}"
            + "function stop(){g=-1;a.pause();a.removeAttribute('src');a.load();}"
            + "['playing','waiting','stalled','error','ended'].forEach(function(t){a.addEventListener(t,function(){"
            + "if(g>=0)Radio.onEvent(t,a.error?String(a.error.code):'',g);});});"
            + "</script></body></html>";
    private static final long CONNECT_TIMEOUT_MS = 20_000;
    private WebView web;
    private boolean webReady;
    private String webPending;
    private int webGen;

    private final Runnable connectTimeout = new Runnable() {
        @Override
        public void run() {
            retry("no audio after 20 s");
        }
    };

    private void startWeb(String url) {
        // Chromium manages audio focus itself; release our native request so it does not take focus away right away
        if (focus != null) audio.abandonAudioFocusRequest(focus);
        if (!wifiLock.isHeld()) wifiLock.acquire();
        registerNoisy();
        scheduleSleep();
        main.postDelayed(connectTimeout, CONNECT_TIMEOUT_MS);
        if (web == null) {
            web = new WebView(ctx);
            WebSettings s = web.getSettings();
            s.setJavaScriptEnabled(true);
            s.setMediaPlaybackRequiresUserGesture(false);
            web.addJavascriptInterface(new Object() {
                @JavascriptInterface
                public void onEvent(final String type, final String detail, final int gen) {
                    main.post(new Runnable() {
                        @Override
                        public void run() {
                            onWebEvent(type, detail, gen);
                        }
                    });
                }
            }, "Radio");
            web.setWebViewClient(new WebViewClient() {
                @Override
                public void onPageFinished(WebView v, String u) {
                    webReady = true;
                    if (webPending != null) {
                        v.evaluateJavascript("play(" + JSONObject.quote(webPending) + "," + webGen + ")", null);
                        webPending = null;
                    }
                }
            });
            webReady = false;
            webGen++;
            webPending = url;
            web.loadDataWithBaseURL("http://localhost/", PLAYER_HTML, "text/html", "utf-8", null);
        } else if (!webReady) {
            webGen++;
            webPending = url;
        } else {
            webGen++;
            web.evaluateJavascript("play(" + JSONObject.quote(url) + "," + webGen + ")", null);
        }
    }

    private void onWebEvent(String type, String detail, int gen) {
        if (!isWanted() || gen != webGen) return;
        if ("playing".equals(type)) {
            main.removeCallbacks(connectTimeout);
            synchronized (this) {
                state = "playing";
                attempt = 0;
                slowAttempt = 0;
                info = "";
            }
        } else if ("error".equals(type) || "ended".equals(type)) {
            webGen++;   // further events of the same playback no longer count as new errors
            retry("ended".equals(type) ? "stream ended" : "stream error " + detail);
        } else {   // waiting / stalled: buffering; if it lasts more than 20 s, reconnect
            synchronized (this) {
                if ("playing".equals(state)) {
                    state = "connecting";
                    info = "buffering";
                }
            }
            main.removeCallbacks(connectTimeout);
            main.postDelayed(connectTimeout, CONNECT_TIMEOUT_MS);
        }
    }

    private void stopWeb() {
        webPending = null;
        if (web != null && webReady) web.evaluateJavascript("stop()", null);
    }

    private void scheduleSleep() {
        main.removeCallbacks(sleepRunnable);
        long until;
        synchronized (this) {
            until = sleepUntil;
        }
        if (until > 0) main.postDelayed(sleepRunnable, Math.max(0, until - System.currentTimeMillis()));
    }

    private boolean requestFocus() {
        if (focus == null) {
            focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attrs)
                    .setOnAudioFocusChangeListener(focusListener, main).build();
        }
        return audio.requestAudioFocus(focus) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED;
    }

    private void registerNoisy() {
        if (!noisyRegistered) {
            ctx.registerReceiver(noisy, new IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY));
            noisyRegistered = true;
        }
    }

    /** Stops both engines (native and Chromium). */
    private void releasePlayer() {
        main.removeCallbacks(connectTimeout);
        stopWeb();
        if (mp != null) {
            MediaPlayer old = mp;
            mp = null;
            try {
                old.reset();
            } catch (Exception ignored) {
            }
            old.release();
        }
    }

    private void releaseAll() {
        releasePlayer();
        unregisterNetCallback();
        if (focus != null) audio.abandonAudioFocusRequest(focus);
        if (wifiLock.isHeld()) wifiLock.release();
        if (noisyRegistered) {
            try {
                ctx.unregisterReceiver(noisy);
            } catch (Exception ignored) {
            }
            noisyRegistered = false;
        }
    }

    /** Where the sound goes: "bt:Name", "wired" or "speaker". */
    private String output() {
        for (AudioDeviceInfo d : audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            int t = d.getType();
            if (t == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP) return "bt:" + d.getProductName();
            if (t == AudioDeviceInfo.TYPE_WIRED_HEADPHONES || t == AudioDeviceInfo.TYPE_WIRED_HEADSET) return "wired";
        }
        return "speaker";
    }

    // ---------- station list ----------

    /** Addresses for consecutive attempts: url, then "alt" from radio.json, then the current Radio Browser address (by uuid). */
    private String[] resolveUrls(String sid) {
        JSONObject st = findStation(sid);
        return st == null ? null : urlsFor(st);
    }

    private String[] urlsFor(JSONObject st) {
        LinkedHashSet<String> list = new LinkedHashSet<>();
        String url = st.optString("url");
        if (!url.isEmpty()) list.add(url);
        JSONArray alt = st.optJSONArray("alt");
        if (alt != null) {
            for (int i = 0; i < alt.length(); i++) {
                if (!alt.optString(i).isEmpty()) list.add(alt.optString(i));
            }
        }
        String uuid = st.optString("uuid", "");
        if (!uuid.isEmpty()) {
            for (String host : RB_HOSTS) {
                try {
                    String rb = new JSONObject(httpGet("https://" + host + ".api.radio-browser.info/json/url/" + uuid, 4000))
                            .optString("url", "");
                    if (!rb.isEmpty()) list.add(rb);
                    break;
                } catch (Exception ignored) {
                    // this Radio Browser server does not respond: try the next one
                }
            }
        }
        return list.isEmpty() ? null : list.toArray(new String[0]);
    }

    /** The station entry from radio.json, or null. */
    private JSONObject findStation(String sid) {
        String json;
        File cache = new File(ctx.getFilesDir(), "radio.json");
        try {
            json = httpGet(LIST_URL, 5000);
            FileOutputStream out = new FileOutputStream(cache);
            out.write(json.getBytes(StandardCharsets.UTF_8));
            out.close();
        } catch (Exception e) {
            json = readFile(cache);
        }
        if (json == null) return null;
        try {
            JSONArray groups = new JSONObject(json).getJSONArray("groups");
            for (int g = 0; g < groups.length(); g++) {
                JSONArray st = groups.getJSONObject(g).getJSONArray("stations");
                for (int i = 0; i < st.length(); i++) {
                    JSONObject s = st.getJSONObject(i);
                    if (sid.equals(s.optString("id"))) return s;
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "bad radio.json", e);
        }
        return null;
    }

    private static String httpGet(String url, int timeoutMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(timeoutMs);
        c.setReadTimeout(timeoutMs);
        c.setRequestProperty("User-Agent", "ServerStatus/1.3.3");
        try {
            if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
            return readAll(c.getInputStream());
        } finally {
            c.disconnect();
        }
    }

    private static String readFile(File f) {
        try {
            return readAll(new FileInputStream(f));
        } catch (Exception e) {
            return null;
        }
    }

    private static String readAll(InputStream in) throws Exception {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
        in.close();
        return new String(b.toByteArray(), StandardCharsets.UTF_8);
    }
}
