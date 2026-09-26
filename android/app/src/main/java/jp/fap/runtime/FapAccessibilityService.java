package jp.fap.runtime;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.view.accessibility.AccessibilityEvent;

public class FapAccessibilityService extends AccessibilityService {
    private static volatile FapAccessibilityService instance;

    @Override protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        // FAP can observe events here when a higher-level policy enables it.
    }

    @Override public void onInterrupt() {
        // No-op: gesture dispatch remains explicitly requested by FAP.
    }

    @Override public void onDestroy() {
        if (instance == this) instance = null;
        super.onDestroy();
    }

    public static boolean isReady() {
        return instance != null;
    }

    public static boolean tap(float x, float y) {
        FapAccessibilityService service = instance;
        if (service == null) return false;

        Path path = new Path();
        path.moveTo(x, y);
        GestureDescription.StrokeDescription stroke =
                new GestureDescription.StrokeDescription(path, 0, 60);
        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(stroke)
                .build();
        return service.dispatchGesture(gesture, null, null);
    }

    public static boolean drag(float startX, float startY, float endX, float endY, long durationMs) {
        FapAccessibilityService service = instance;
        if (service == null) return false;

        Path path = new Path();
        path.moveTo(startX, startY);
        path.lineTo(endX, endY);
        long duration = Math.max(100L, Math.min(durationMs, 10_000L));
        GestureDescription.StrokeDescription stroke =
                new GestureDescription.StrokeDescription(path, 0, duration);
        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(stroke)
                .build();
        return service.dispatchGesture(gesture, null, null);
    }
}
