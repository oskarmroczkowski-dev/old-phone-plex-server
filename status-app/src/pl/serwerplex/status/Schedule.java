package pl.serwerplex.status;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;

import java.util.Calendar;

/** Screen schedule: on 6:00-23:00. A system alarm is set for the nearest of these times. */
final class Schedule {
    static final int DAY_FROM = 6;
    static final int DAY_TO = 23;

    private Schedule() {
    }

    static boolean isDay() {
        int h = Calendar.getInstance().get(Calendar.HOUR_OF_DAY);
        return h >= DAY_FROM && h < DAY_TO;
    }

    /** Sets an alarm for the nearest 6:00 or 23:00 (AlarmReceiver then sets the next one). */
    static void scheduleNext(Context ctx) {
        Calendar now = Calendar.getInstance();
        Calendar next = (Calendar) now.clone();
        next.set(Calendar.MINUTE, 0);
        next.set(Calendar.SECOND, 0);
        next.set(Calendar.MILLISECOND, 0);
        int h = now.get(Calendar.HOUR_OF_DAY);
        if (h < DAY_FROM) {
            next.set(Calendar.HOUR_OF_DAY, DAY_FROM);
        } else if (h < DAY_TO) {
            next.set(Calendar.HOUR_OF_DAY, DAY_TO);
        } else {
            next.add(Calendar.DAY_OF_MONTH, 1);
            next.set(Calendar.HOUR_OF_DAY, DAY_FROM);
        }

        PendingIntent pi = PendingIntent.getBroadcast(ctx, 0, new Intent(ctx, AlarmReceiver.class),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        AlarmManager am = ctx.getSystemService(AlarmManager.class);
        if (am.canScheduleExactAlarms()) {
            // "alarm clock" type: realme does not delay it (a plain exact alarm got a window of up to 1 h)
            PendingIntent show = PendingIntent.getActivity(ctx, 1, new Intent(ctx, MainActivity.class),
                    PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            am.setAlarmClock(new AlarmManager.AlarmClockInfo(next.getTimeInMillis(), show), pi);
        } else {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next.getTimeInMillis(), pi);
        }
    }

    /** Brings the status screen to the front (needs the "Display over other apps" permission). */
    static void openStatus(Context ctx) {
        Intent i = new Intent(ctx, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        try {
            ctx.startActivity(i);
        } catch (RuntimeException ignored) {
            // without permission to start from the background Android refuses; the screen returns when opened manually
        }
    }
}
