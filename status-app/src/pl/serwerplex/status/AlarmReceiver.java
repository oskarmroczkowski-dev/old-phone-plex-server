package pl.serwerplex.status;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.PowerManager;

/**
 * Alarm at 6:00 (turns the screen on and shows the status) and at 23:00 (the screen turns off by itself,
 * the radio stops).
 */
public class AlarmReceiver extends BroadcastReceiver {
    @Override
    @SuppressWarnings("deprecation")
    public void onReceive(Context ctx, Intent intent) {
        Schedule.scheduleNext(ctx);
        if (!Schedule.isDay()) {
            RadioPlayer.get(ctx).stopIfActive("23:00 switch-off");
            return;
        }

        PowerManager pm = ctx.getSystemService(PowerManager.class);
        PowerManager.WakeLock wl = pm.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP, "status:morning");
        wl.acquire(15_000);
        Schedule.openStatus(ctx);
    }
}
