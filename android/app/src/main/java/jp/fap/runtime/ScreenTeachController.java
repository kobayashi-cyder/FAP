package jp.fap.runtime;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import org.json.JSONObject;

import java.io.File;
import java.io.FileWriter;
import java.util.Locale;

public final class ScreenTeachController {
    static final String PREFS = "fap_screen_teach";
    static final String ACTION_START = "jp.fap.runtime.screen_teach.START";
    static final String ACTION_STOP = "jp.fap.runtime.screen_teach.STOP";
    static final String EXTRA_RESULT_CODE = "result_code";
    static final String EXTRA_RESULT_DATA = "result_data";

    private static final String KEY_SHARING = "sharing";
    private static final String KEY_CONTROL = "control";
    private static final String KEY_LAST_FRAME = "last_frame";
    private static final String KEY_FRAME_SEQ = "frame_seq";
    private static final String KEY_ACTION_SEQ = "action_seq";
    private static final String KEY_STARTED_AT = "started_at";
    private static final long MAX_TRACE_BYTES = 4L * 1024L * 1024L;

    private ScreenTeachController() {}

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static void startCapture(Context context, int resultCode, Intent resultData) {
        if (context == null || resultData == null) return;
        Intent intent = new Intent(context, ScreenShareCaptureService.class)
                .setAction(ACTION_START)
                .putExtra(EXTRA_RESULT_CODE, resultCode)
                .putExtra(EXTRA_RESULT_DATA, resultData);
        if (Build.VERSION.SDK_INT >= 26) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    public static void stopCapture(Context context) {
        if (context == null) return;
        Intent intent = new Intent(context, ScreenShareCaptureService.class)
                .setAction(ACTION_STOP);
        try {
            context.startService(intent);
        } catch (Throwable ignored) {
            try {
                context.stopService(new Intent(context, ScreenShareCaptureService.class));
            } catch (Throwable ignoredAgain) {
            }
        }
        prefs(context).edit().putBoolean(KEY_SHARING, false).apply();
    }

    public static boolean isSharing(Context context) {
        return context != null && prefs(context).getBoolean(KEY_SHARING, false);
    }

    static void markSharing(Context context, boolean sharing) {
        SharedPreferences.Editor editor = prefs(context).edit()
                .putBoolean(KEY_SHARING, sharing);
        if (sharing) {
            editor.putLong(KEY_STARTED_AT, System.currentTimeMillis());
        }
        editor.apply();
    }

    public static boolean isControlEnabled(Context context) {
        return context != null && prefs(context).getBoolean(KEY_CONTROL, false);
    }

    public static void setControlEnabled(Context context, boolean enabled) {
        if (context == null) return;
        prefs(context).edit().putBoolean(KEY_CONTROL, enabled).apply();
        appendTrace(context, eventJson(
                enabled ? "control_enabled" : "control_disabled",
                null));
    }

    public static File frameDirectory(Context context) {
        File dir = new File(context.getFilesDir(), "screen_teach/frames");
        if (!dir.exists()) dir.mkdirs();
        return dir;
    }

    public static File latestFrame(Context context) {
        String path = prefs(context).getString(KEY_LAST_FRAME, "");
        if (path == null || path.isEmpty()) return null;
        File file = new File(path);
        return file.isFile() ? file : null;
    }

    static long nextFrameSequence(Context context) {
        SharedPreferences p = prefs(context);
        long next = p.getLong(KEY_FRAME_SEQ, 0L) + 1L;
        p.edit().putLong(KEY_FRAME_SEQ, next).apply();
        return next;
    }

    static void recordFrame(
            Context context,
            File frame,
            int sourceWidth,
            int sourceHeight,
            int storedWidth,
            int storedHeight) {
        if (context == null || frame == null) return;
        prefs(context).edit()
                .putString(KEY_LAST_FRAME, frame.getAbsolutePath())
                .apply();

        JSONObject detail = new JSONObject();
        try {
            detail.put("path", frame.getAbsolutePath());
            detail.put("source_width", sourceWidth);
            detail.put("source_height", sourceHeight);
            detail.put("stored_width", storedWidth);
            detail.put("stored_height", storedHeight);
        } catch (Throwable ignored) {
        }
        appendTrace(context, eventJson("frame", detail));
    }

    public static void recordAction(
            Context context,
            String type,
            float x1,
            float y1,
            float x2,
            float y2,
            long durationMs,
            boolean accepted) {
        if (context == null) return;
        SharedPreferences p = prefs(context);
        long seq = p.getLong(KEY_ACTION_SEQ, 0L) + 1L;
        p.edit().putLong(KEY_ACTION_SEQ, seq).apply();

        JSONObject detail = new JSONObject();
        try {
            detail.put("seq", seq);
            detail.put("type", type == null ? "unknown" : type);
            detail.put("x1", round3(x1));
            detail.put("y1", round3(y1));
            detail.put("x2", round3(x2));
            detail.put("y2", round3(y2));
            detail.put("duration_ms", durationMs);
            detail.put("accepted", accepted);
            File latest = latestFrame(context);
            if (latest != null) detail.put("frame", latest.getAbsolutePath());
        } catch (Throwable ignored) {
        }
        appendTrace(context, eventJson("action", detail));
    }

    public static String summary(Context context) {
        SharedPreferences p = prefs(context);
        File frame = latestFrame(context);
        return "screen=" + (p.getBoolean(KEY_SHARING, false) ? "ON" : "OFF")
                + " · control=" + (p.getBoolean(KEY_CONTROL, false) ? "ON" : "OFF")
                + " · frames=" + p.getLong(KEY_FRAME_SEQ, 0L)
                + " · actions=" + p.getLong(KEY_ACTION_SEQ, 0L)
                + (frame == null ? "" : " · latest=" + frame.getName());
    }

    public static String commandHelp() {
        return "/tap x y  または  /drag x1 y1 x2 y2 [durationMs]";
    }

    private static JSONObject eventJson(String event, JSONObject detail) {
        JSONObject row = new JSONObject();
        try {
            row.put("timestamp_ms", System.currentTimeMillis());
            row.put("event", event);
            if (detail != null) row.put("detail", detail);
        } catch (Throwable ignored) {
        }
        return row;
    }

    private static synchronized void appendTrace(Context context, JSONObject row) {
        try {
            File dir = new File(context.getFilesDir(), "screen_teach");
            if (!dir.exists()) dir.mkdirs();
            File trace = new File(dir, "trace.jsonl");
            if (trace.isFile() && trace.length() > MAX_TRACE_BYTES) {
                File rotated = new File(dir, "trace.previous.jsonl");
                if (rotated.exists()) rotated.delete();
                trace.renameTo(rotated);
            }
            try (FileWriter writer = new FileWriter(trace, true)) {
                writer.write(row.toString());
                writer.write("\n");
            }
        } catch (Throwable ignored) {
        }
    }

    private static double round3(float value) {
        return Math.round(value * 1000.0) / 1000.0;
    }
}
