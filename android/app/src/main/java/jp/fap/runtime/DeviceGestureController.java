package jp.fap.runtime;

import android.content.Context;
import android.util.DisplayMetrics;

import java.util.Locale;

public final class DeviceGestureController {
    public static final class CommandResult {
        public final boolean handled;
        public final boolean accepted;
        public final String message;

        CommandResult(boolean handled, boolean accepted, String message) {
            this.handled = handled;
            this.accepted = accepted;
            this.message = message;
        }
    }

    private DeviceGestureController() {}

    public static boolean tap(Context context, float x, float y) {
        if (!ready(context)) return false;
        boolean accepted = PixelBrowserAccessibilityService.dispatchTap(x, y, 80L);
        ScreenTeachController.recordAction(
                context,
                "tap",
                x,
                y,
                x,
                y,
                80L,
                accepted);
        return accepted;
    }

    public static boolean drag(
            Context context,
            float x1,
            float y1,
            float x2,
            float y2,
            long durationMs) {
        if (!ready(context)) return false;
        long duration = Math.max(120L, Math.min(5000L, durationMs));
        boolean accepted = PixelBrowserAccessibilityService.dispatchDrag(
                x1,
                y1,
                x2,
                y2,
                duration);
        ScreenTeachController.recordAction(
                context,
                "drag",
                x1,
                y1,
                x2,
                y2,
                duration,
                accepted);
        return accepted;
    }

    public static boolean tapNormalized(Context context, float nx, float ny) {
        DisplayMetrics m = context.getResources().getDisplayMetrics();
        return tap(
                context,
                clamp01(nx) * m.widthPixels,
                clamp01(ny) * m.heightPixels);
    }

    public static boolean dragNormalized(
            Context context,
            float nx1,
            float ny1,
            float nx2,
            float ny2,
            long durationMs) {
        DisplayMetrics m = context.getResources().getDisplayMetrics();
        return drag(
                context,
                clamp01(nx1) * m.widthPixels,
                clamp01(ny1) * m.heightPixels,
                clamp01(nx2) * m.widthPixels,
                clamp01(ny2) * m.heightPixels,
                durationMs);
    }

    public static CommandResult tryCommand(Context context, String input) {
        String text = input == null ? "" : input.trim();
        if (!text.startsWith("/")) {
            return new CommandResult(false, false, "");
        }

        String[] parts = text.split("\\s+");
        String command = parts[0].toLowerCase(Locale.ROOT);
        try {
            if ("/tap".equals(command) && parts.length == 3) {
                float x = Float.parseFloat(parts[1]);
                float y = Float.parseFloat(parts[2]);
                boolean accepted = tap(context, x, y);
                return new CommandResult(
                        true,
                        accepted,
                        accepted
                                ? "tap accepted · (" + x + ", " + y + ")"
                                : failureMessage(context));
            }
            if (("/drag".equals(command) || "/swipe".equals(command))
                    && (parts.length == 5 || parts.length == 6)) {
                float x1 = Float.parseFloat(parts[1]);
                float y1 = Float.parseFloat(parts[2]);
                float x2 = Float.parseFloat(parts[3]);
                float y2 = Float.parseFloat(parts[4]);
                long duration = parts.length == 6
                        ? Long.parseLong(parts[5])
                        : 650L;
                boolean accepted = drag(context, x1, y1, x2, y2, duration);
                return new CommandResult(
                        true,
                        accepted,
                        accepted
                                ? "drag accepted · (" + x1 + ", " + y1 + ") -> ("
                                    + x2 + ", " + y2 + ") · " + duration + "ms"
                                : failureMessage(context));
            }
            if ("/screen".equals(command) && parts.length == 1) {
                return new CommandResult(
                        true,
                        true,
                        ScreenTeachController.summary(context));
            }
            if ("/control".equals(command) && parts.length == 2) {
                boolean enabled = "on".equalsIgnoreCase(parts[1])
                        || "1".equals(parts[1])
                        || "true".equalsIgnoreCase(parts[1]);
                ScreenTeachController.setControlEnabled(context, enabled);
                return new CommandResult(
                        true,
                        true,
                        "control=" + (enabled ? "ON" : "OFF"));
            }
        } catch (NumberFormatException ignored) {
            return new CommandResult(true, false, ScreenTeachController.commandHelp());
        }

        return new CommandResult(
                true,
                false,
                ScreenTeachController.commandHelp()
                        + " · /screen · /control on|off");
    }

    public static boolean ready(Context context) {
        return context != null
                && ScreenTeachController.isControlEnabled(context)
                && PixelBrowserController.isAccessibilityEnabled(context)
                && PixelBrowserAccessibilityService.isConnected();
    }

    private static String failureMessage(Context context) {
        if (!ScreenTeachController.isControlEnabled(context)) {
            return "操作がOFFです。操作チップをONにしてください。";
        }
        if (!PixelBrowserController.isAccessibilityEnabled(context)) {
            return "ユーザー補助の『FAP Pixel Browser Control』を有効にしてください。";
        }
        if (!PixelBrowserAccessibilityService.isConnected()) {
            return "ユーザー補助サービスの接続待ちです。";
        }
        return "gesture dispatch was rejected";
    }

    private static float clamp01(float v) {
        return Math.max(0f, Math.min(1f, v));
    }
}
