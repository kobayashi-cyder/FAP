package jp.fap.runtime;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.provider.Settings;
import android.view.accessibility.AccessibilityManager;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

public final class PixelBrowserController {
    static final String PREFS = "fap_pixel_browser";
    static final String KEY_COMMAND = "command";
    static final String KEY_PROMPT = "prompt";
    static final String KEY_STATE = "state";
    static final String KEY_RESPONSE = "response";
    static final String KEY_ERROR = "error";
    static final String KEY_STARTED_AT = "started_at";
    static final String KEY_CANDIDATE = "candidate";
    static final String KEY_STABLE = "stable";
    static final String KEY_AUTO_RETURN = "auto_return";

    static final String CMD_NONE = "";
    static final String CMD_ASK_CHATGPT = "ask_chatgpt";

    public static final String STATE_IDLE = "idle";
    public static final String STATE_QUEUED = "queued";
    public static final String STATE_WAITING_INPUT = "waiting_input";
    public static final String STATE_WAITING_RESPONSE = "waiting_response";
    public static final String STATE_RESPONSE_READY = "response_ready";
    public static final String STATE_ERROR = "error";

    private PixelBrowserController() {}

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static boolean isAccessibilityEnabled(Context context) {
        AccessibilityManager manager =
                (AccessibilityManager) context.getSystemService(Context.ACCESSIBILITY_SERVICE);
        if (manager == null || !manager.isEnabled()) return false;

        List<AccessibilityServiceInfo> enabled =
                manager.getEnabledAccessibilityServiceList(
                        AccessibilityServiceInfo.FEEDBACK_ALL_MASK);
        String expectedPackage = context.getPackageName();
        String expectedClass = PixelBrowserAccessibilityService.class.getName();

        for (AccessibilityServiceInfo info : enabled) {
            String id = info.getId();
            if (id == null) continue;
            ComponentName component = ComponentName.unflattenFromString(id);
            if (component == null) continue;
            if (expectedPackage.equals(component.getPackageName())
                    && expectedClass.equals(component.getClassName())) {
                return true;
            }
        }
        return false;
    }

    public static void openAccessibilitySettings(Context context) {
        Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    public static boolean askChatGpt(Context context, String prompt) {
        return askChatGpt(context, prompt, false);
    }

    public static boolean askChatGpt(
            Context context,
            String prompt,
            boolean autoReturn) {
        String clean = prompt == null ? "" : prompt.trim();
        if (clean.isEmpty()) return false;

        prefs(context).edit()
                .putString(KEY_COMMAND, CMD_ASK_CHATGPT)
                .putString(KEY_PROMPT, clean)
                .putString(KEY_STATE, STATE_QUEUED)
                .putString(KEY_RESPONSE, "")
                .putString(KEY_ERROR, "")
                .putString(KEY_CANDIDATE, "")
                .putBoolean(KEY_AUTO_RETURN, autoReturn)
                .putInt(KEY_STABLE, 0)
                .putLong(KEY_STARTED_AT, System.currentTimeMillis())
                .apply();

        return openUrl(context, "https://chatgpt.com/");
    }

    public static boolean openSearch(Context context, String query) {
        String clean = query == null ? "" : query.trim();
        if (clean.isEmpty()) return false;
        String encoded = URLEncoder.encode(clean, StandardCharsets.UTF_8);
        return openUrl(context, "https://www.google.com/search?q=" + encoded);
    }

    public static boolean openUrl(Context context, String url) {
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

        Intent chrome = new Intent(intent);
        chrome.setPackage("com.android.chrome");
        try {
            context.startActivity(chrome);
            return true;
        } catch (Exception ignored) {
            try {
                context.startActivity(intent);
                return true;
            } catch (Exception ignoredAgain) {
                prefs(context).edit()
                        .putString(KEY_STATE, STATE_ERROR)
                        .putString(KEY_ERROR, "No browser could open the requested URL.")
                        .apply();
                return false;
            }
        }
    }

    public static String state(Context context) {
        return prefs(context).getString(KEY_STATE, STATE_IDLE);
    }

    public static String lastResponse(Context context) {
        return prefs(context).getString(KEY_RESPONSE, "");
    }

    public static String lastError(Context context) {
        return prefs(context).getString(KEY_ERROR, "");
    }

    public static void clear(Context context) {
        prefs(context).edit()
                .putString(KEY_COMMAND, CMD_NONE)
                .putString(KEY_PROMPT, "")
                .putString(KEY_STATE, STATE_IDLE)
                .putString(KEY_RESPONSE, "")
                .putString(KEY_ERROR, "")
                .putString(KEY_CANDIDATE, "")
                .putBoolean(KEY_AUTO_RETURN, false)
                .putInt(KEY_STABLE, 0)
                .remove(KEY_STARTED_AT)
                .apply();
    }
}
