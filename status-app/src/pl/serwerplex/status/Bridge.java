package pl.serwerplex.status;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.webkit.JavascriptInterface;

/** Phone data for the page (window.StatusApp): battery level, charging and battery temperature. */
final class Bridge {
    private final Context ctx;

    Bridge(Context ctx) {
        this.ctx = ctx.getApplicationContext();
    }

    @JavascriptInterface
    public String battery() {
        Intent b = ctx.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (b == null) return "null";
        int level = b.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = b.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
        int plugged = b.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
        int temp = b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0);
        return "{\"level\":" + Math.round(level * 100f / scale)
                + ",\"charging\":" + (plugged != 0)
                + ",\"temp\":" + Math.round(temp / 10f) + "}";
    }
}
