package pl.serwerplex.status;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** After the phone boots (and after the app is updated): set the 6:00/23:00 alarm and bring the status screen up. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        Schedule.scheduleNext(ctx);
        Schedule.openStatus(ctx);
    }
}
