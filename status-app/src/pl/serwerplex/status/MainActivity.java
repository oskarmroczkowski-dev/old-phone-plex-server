package pl.serwerplex.status;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Full-screen display of the server status page. */
public class MainActivity extends Activity {
    static final String URL = "http://127.0.0.1:8099/";
    private static final long RETRY_MS = 10_000;
    private static final String BLACK = "<html><body style='background:#000'></body></html>";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private WebView web;
    private boolean loadFailed;
    private Watchdog watchdog;

    private final Runnable retry = new Runnable() {
        @Override
        public void run() {
            if (web != null) {
                loadFailed = false;
                web.loadUrl(URL);
            }
        }
    };

    private final Runnable minuteTick = new Runnable() {
        @Override
        public void run() {
            applyDayNight();
            handler.postDelayed(this, 60_000);
        }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        Window w = getWindow();
        w.getAttributes().layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        w.setDecorFitsSystemWindows(false);
        w.getDecorView().setBackgroundColor(Color.BLACK);
        createWebView();
        Schedule.scheduleNext(this);
        watchdog = new Watchdog(this);
        watchdog.start();
        if (checkSelfPermission(Watchdog.RUN_COMMAND_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Watchdog.RUN_COMMAND_PERMISSION}, 1);
        }
    }

    private void createWebView() {
        web = new WebView(this);
        web.setBackgroundColor(Color.BLACK);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        web.setLongClickable(false);
        web.setOnLongClickListener(new android.view.View.OnLongClickListener() {
            @Override
            public boolean onLongClick(android.view.View v) {
                return true;
            }
        });
        web.setHapticFeedbackEnabled(false);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        web.addJavascriptInterface(new Bridge(this), "StatusApp");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) failed(v);
            }

            @Override
            public void onReceivedHttpError(WebView v, WebResourceRequest req, WebResourceResponse resp) {
                if (req.isForMainFrame()) failed(v);
            }

            @Override
            public boolean onRenderProcessGone(WebView v, RenderProcessGoneDetail detail) {
                // the page process died: create the WebView again
                setContentView(new android.view.View(MainActivity.this));
                v.destroy();
                createWebView();
                return true;
            }
        });
        setContentView(web);
        web.loadUrl(URL);
    }

    /** The status server is not running yet (e.g. right after a reboot): black screen, retry in 10 s. */
    private void failed(WebView v) {
        loadFailed = true;
        v.loadDataWithBaseURL(null, BLACK, "text/html", "utf-8", null);
        handler.removeCallbacks(retry);
        handler.postDelayed(retry, RETRY_MS);
    }

    @Override
    protected void onResume() {
        super.onResume();
        hideSystemBars();
        applyDayNight();
        handler.removeCallbacks(minuteTick);
        handler.postDelayed(minuteTick, 60_000);
        if (loadFailed) handler.post(retry);
    }

    @Override
    protected void onPause() {
        handler.removeCallbacks(minuteTick);
        super.onPause();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        hideSystemBars();
        applyDayNight();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemBars();
    }

    @Override
    public void onBackPressed() {
        // the Back button does not close the status screen; leave with the Home button
    }

    @Override
    protected void onDestroy() {
        if (watchdog != null) watchdog.stop();
        handler.removeCallbacksAndMessages(null);
        if (web != null) web.destroy();
        super.onDestroy();
    }

    /** Full screen: status bar and navigation buttons hidden; they only reappear briefly after a swipe from the edge. */
    private void hideSystemBars() {
        WindowInsetsController c = getWindow().getInsetsController();
        if (c == null) return;
        c.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
        c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }

    /** 6:00-23:00 the screen stays on; at night it turns off normally after the phone's screen timeout. */
    private void applyDayNight() {
        if (Schedule.isDay()) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
    }
}
