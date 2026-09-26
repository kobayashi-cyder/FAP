package jp.fap.runtime;

import android.content.Context;
import android.content.SharedPreferences;

public final class GenerationPreferences {
    private static final String PREFS = "fap_generation";
    private static final String KEY_QUALITY = "quality";
    private static final String KEY_IMAGE_ENDPOINT = "image_endpoint";

    private GenerationPreferences() {}

    public static String quality(Context context) {
        String value = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_QUALITY, "standard");
        if ("draft".equals(value) || "high".equals(value)) return value;
        return "standard";
    }

    public static String label(Context context) {
        String value = quality(context);
        if ("draft".equals(value)) return "軽量";
        if ("high".equals(value)) return "高品質";
        return "標準";
    }

    public static String cycle(Context context) {
        String current = quality(context);
        String next = "draft".equals(current)
                ? "standard"
                : ("standard".equals(current) ? "high" : "draft");
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_QUALITY, next)
                .apply();
        return next;
    }

    public static String endpoint(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_IMAGE_ENDPOINT, "")
                .trim();
    }

    public static void setEndpoint(Context context, String endpoint) {
        String value = endpoint == null ? "" : endpoint.trim();
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_IMAGE_ENDPOINT, value)
                .apply();
    }

    public static String directive(Context context) {
        return "[FAP_MEDIA quality=" + quality(context) + "] ";
    }
}
