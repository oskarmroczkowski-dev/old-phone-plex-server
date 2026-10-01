package pl.serwerplex.status;

import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Log;

import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Termux watchdog. Every minute it requests the status page (this is also the app's heartbeat for check-app.sh).
 * If the page does not respond 3 times in a row (Termux killed or force-stopped), it asks Termux to run
 * ~/start-server.sh (RUN_COMMAND mechanism; needs allow-external-apps = true in Termux).
 */
final class Watchdog {
    private static final String TAG = "StatusWatchdog";
    private static final String PING = "http://127.0.0.1:8099/ping?app=1";
    private static final String SCRIPT = "/data/data/com.termux/files/home/start-server.sh";
    static final String RUN_COMMAND_PERMISSION = "com.termux.permission.RUN_COMMAND";
    private static final long INTERVAL_MS = 60_000;
    private static final int FAILS_BEFORE_RESTART = 3;
    private static final long RESTART_PAUSE_MS = 10 * 60_000;

    private final Context ctx;
    private HandlerThread thread;
    private Handler handler;
    private int fails;
    private long lastRestart;

    private final Runnable check = new Runnable() {
        @Override
        public void run() {
            if (ping()) {
                fails = 0;
            } else if (++fails >= FAILS_BEFORE_RESTART
                    && System.currentTimeMillis() - lastRestart > RESTART_PAUSE_MS) {
                restartTermux();
                lastRestart = System.currentTimeMillis();
                fails = 0;
            }
            if (handler != null) handler.postDelayed(this, INTERVAL_MS);
        }
    };

    Watchdog(Context ctx) {
        this.ctx = ctx.getApplicationContext();
    }

    void start() {
        if (thread != null) return;
        thread = new HandlerThread("watchdog");
        thread.start();
        handler = new Handler(thread.getLooper());
        handler.postDelayed(check, INTERVAL_MS);
    }

    void stop() {
        if (thread == null) return;
        handler.removeCallbacksAndMessages(null);
        handler = null;
        thread.quitSafely();
        thread = null;
    }

    private static boolean ping() {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(PING).openConnection();
            c.setConnectTimeout(5000);
            c.setReadTimeout(5000);
            c.setUseCaches(false);
            return c.getResponseCode() == 200;
        } catch (Exception e) {
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private void restartTermux() {
        Intent i = new Intent("com.termux.RUN_COMMAND");
        i.setClassName("com.termux", "com.termux.app.RunCommandService");
        i.putExtra("com.termux.RUN_COMMAND_PATH", SCRIPT);
        i.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"status-app"});
        i.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
        i.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
        try {
            ctx.startForegroundService(i);
            Log.i(TAG, "status page silent: running start-server.sh in Termux");
        } catch (RuntimeException e) {
            Log.w(TAG, "could not start Termux", e);
        }
    }
}
