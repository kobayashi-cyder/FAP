package jp.fap.runtime;

import android.accessibilityservice.AccessibilityService;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class PixelBrowserAccessibilityService extends AccessibilityService {
    private static final long INPUT_TIMEOUT_MS = 120_000L;
    private static final long RESPONSE_TIMEOUT_MS = 240_000L;
    private static final String KEY_BASELINE = "baseline";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean pumpScheduled = false;
    private final Runnable agentHeartbeat = new Runnable() {
        @Override public void run() {
            try {
                AgentOrchestrator.get(PixelBrowserAccessibilityService.this).reconcileAsync();
            } catch (Throwable ignored) {
            }
            handler.postDelayed(this, 3000L);
        }
    };

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        AgentOrchestrator.get(this).reconcileAsync();
        handler.removeCallbacks(agentHeartbeat);
        handler.postDelayed(agentHeartbeat, 800L);
        schedulePump(120);
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null || event.getPackageName() == null) return;
        if (!"com.android.chrome".contentEquals(event.getPackageName())) return;
        schedulePump(180);
    }

    @Override
    public void onInterrupt() {
        // Keep queued state intact. Android may interrupt accessibility feedback
        // transiently while Chrome changes windows.
    }

    private void schedulePump(long delayMs) {
        if (pumpScheduled) return;
        pumpScheduled = true;
        handler.postDelayed(() -> {
            pumpScheduled = false;
            pump();
        }, delayMs);
    }

    private void pump() {
        String command = PixelBrowserController.prefs(this).getString(
                PixelBrowserController.KEY_COMMAND,
                PixelBrowserController.CMD_NONE);
        if (!PixelBrowserController.CMD_ASK_CHATGPT.equals(command)) return;

        String state = PixelBrowserController.state(this);
        long started = PixelBrowserController.prefs(this).getLong(
                PixelBrowserController.KEY_STARTED_AT, 0L);
        long age = started > 0 ? Math.max(0L, System.currentTimeMillis() - started) : 0L;

        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) {
            if (age > INPUT_TIMEOUT_MS) {
                fail("Chrome accessibility tree is unavailable.");
            } else {
                schedulePump(500);
            }
            return;
        }

        if (PixelBrowserController.STATE_QUEUED.equals(state)
                || PixelBrowserController.STATE_WAITING_INPUT.equals(state)) {
            if (age > INPUT_TIMEOUT_MS) {
                fail("Timed out waiting for the ChatGPT input field.");
                return;
            }
            PixelBrowserController.prefs(this).edit()
                    .putString(PixelBrowserController.KEY_STATE,
                            PixelBrowserController.STATE_WAITING_INPUT)
                    .apply();

            AccessibilityNodeInfo editor = findBestEditor(root);
            if (editor == null) {
                schedulePump(500);
                return;
            }

            String prompt = PixelBrowserController.prefs(this).getString(
                    PixelBrowserController.KEY_PROMPT, "");
            if (prompt == null || prompt.trim().isEmpty()) {
                fail("Browser task has an empty prompt.");
                return;
            }

            String baseline = bestResponseCandidate(root, prompt, "");
            if (!setText(editor, prompt)) {
                schedulePump(500);
                return;
            }

            PixelBrowserController.prefs(this).edit()
                    .putString(KEY_BASELINE, baseline)
                    .putString(PixelBrowserController.KEY_STATE,
                            PixelBrowserController.STATE_WAITING_RESPONSE)
                    .putLong(PixelBrowserController.KEY_STARTED_AT, System.currentTimeMillis())
                    .putString(PixelBrowserController.KEY_CANDIDATE, "")
                    .putInt(PixelBrowserController.KEY_STABLE, 0)
                    .apply();

            handler.postDelayed(() -> {
                AccessibilityNodeInfo current = getRootInActiveWindow();
                if (current == null) {
                    schedulePump(500);
                    return;
                }
                AccessibilityNodeInfo currentEditor = findBestEditor(current);
                boolean sent = clickSend(current);
                if (!sent && currentEditor != null && Build.VERSION.SDK_INT >= 30) {
                    sent = currentEditor.performAction(
                            AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId());
                }
                if (!sent) {
                    // Some web UIs expose the send button only after another
                    // accessibility tree update.
                    schedulePump(500);
                    return;
                }
                schedulePump(900);
            }, 350);
            return;
        }

        if (PixelBrowserController.STATE_WAITING_RESPONSE.equals(state)) {
            if (age > RESPONSE_TIMEOUT_MS) {
                fail("Timed out waiting for a stable ChatGPT response.");
                return;
            }
            if (age < 1_500L) {
                schedulePump(700);
                return;
            }

            String prompt = PixelBrowserController.prefs(this).getString(
                    PixelBrowserController.KEY_PROMPT, "");
            String baseline = PixelBrowserController.prefs(this).getString(KEY_BASELINE, "");
            String candidate = bestResponseCandidate(root, prompt, baseline);
            if (candidate.isEmpty()) {
                schedulePump(800);
                return;
            }

            String previous = PixelBrowserController.prefs(this).getString(
                    PixelBrowserController.KEY_CANDIDATE, "");
            int stable = PixelBrowserController.prefs(this).getInt(
                    PixelBrowserController.KEY_STABLE, 0);
            if (candidate.equals(previous)) {
                stable += 1;
            } else {
                previous = candidate;
                stable = 0;
            }

            if (stable >= 2) {
                boolean autoReturn = PixelBrowserController.prefs(this)
                        .getBoolean(PixelBrowserController.KEY_AUTO_RETURN, false);
                PixelBrowserController.prefs(this).edit()
                        .putString(PixelBrowserController.KEY_RESPONSE, candidate)
                        .putString(PixelBrowserController.KEY_STATE,
                                PixelBrowserController.STATE_RESPONSE_READY)
                        .putString(PixelBrowserController.KEY_COMMAND,
                                PixelBrowserController.CMD_NONE)
                        .putString(PixelBrowserController.KEY_ERROR, "")
                        .putString(PixelBrowserController.KEY_CANDIDATE, "")
                        .putBoolean(PixelBrowserController.KEY_AUTO_RETURN, false)
                        .putInt(PixelBrowserController.KEY_STABLE, 0)
                        .apply();

                AgentOrchestrator.get(this).onBrowserResult(prompt, candidate);
                if (autoReturn) {
                    handler.postDelayed(
                            () -> performGlobalAction(GLOBAL_ACTION_BACK),
                            350L);
                }
                return;
            }

            PixelBrowserController.prefs(this).edit()
                    .putString(PixelBrowserController.KEY_CANDIDATE, previous)
                    .putInt(PixelBrowserController.KEY_STABLE, stable)
                    .apply();
            schedulePump(850);
        }
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacks(agentHeartbeat);
        super.onDestroy();
    }

    private void fail(String message) {
        PixelBrowserController.prefs(this).edit()
                .putString(PixelBrowserController.KEY_STATE, PixelBrowserController.STATE_ERROR)
                .putString(PixelBrowserController.KEY_ERROR, message)
                .putString(PixelBrowserController.KEY_COMMAND, PixelBrowserController.CMD_NONE)
                .apply();
    }

    private static boolean setText(AccessibilityNodeInfo node, String value) {
        try {
            node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            Bundle args = new Bundle();
            args.putCharSequence(
                    AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                    value);
            return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static AccessibilityNodeInfo findBestEditor(AccessibilityNodeInfo root) {
        List<AccessibilityNodeInfo> nodes = flatten(root, 900);
        AccessibilityNodeInfo best = null;
        int bestScore = Integer.MIN_VALUE;

        for (AccessibilityNodeInfo node : nodes) {
            if (node == null) continue;
            String viewId = safe(node.getViewIdResourceName()).toLowerCase(Locale.ROOT);
            if (viewId.contains("url_bar")) continue;

            boolean editable = node.isEditable();
            boolean setText = hasAction(node, AccessibilityNodeInfo.ACTION_SET_TEXT);
            if (!editable && !setText) continue;

            String text = safe(node.getText());
            String hint = Build.VERSION.SDK_INT >= 26 ? safe(node.getHintText()) : "";
            String desc = safe(node.getContentDescription());
            String joined = (text + " " + hint + " " + desc).toLowerCase(Locale.ROOT);

            int score = editable ? 20 : 10;
            if (node.isFocused()) score += 3;
            if (joined.contains("message")) score += 18;
            if (joined.contains("chatgpt")) score += 18;
            if (joined.contains("prompt")) score += 14;
            if (joined.contains("質問")) score += 14;
            if (joined.contains("メッセージ")) score += 18;
            if (joined.contains("url") || joined.contains("検索")) score -= 20;

            if (score > bestScore) {
                bestScore = score;
                best = node;
            }
        }
        return bestScore >= 10 ? best : null;
    }

    private static boolean clickSend(AccessibilityNodeInfo root) {
        for (AccessibilityNodeInfo node : flatten(root, 900)) {
            String text = safe(node.getText()).toLowerCase(Locale.ROOT);
            String desc = safe(node.getContentDescription()).toLowerCase(Locale.ROOT);
            String joined = text + " " + desc;

            boolean looksLikeSend =
                    joined.contains("send")
                    || joined.contains("送信")
                    || joined.contains("送る");
            if (!looksLikeSend) continue;

            AccessibilityNodeInfo clickable = node;
            for (int i = 0; i < 3 && clickable != null; i++) {
                if (clickable.isClickable()
                        && clickable.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                    return true;
                }
                clickable = clickable.getParent();
            }
        }
        return false;
    }

    private static String bestResponseCandidate(
            AccessibilityNodeInfo root,
            String prompt,
            String baseline) {
        List<AccessibilityNodeInfo> nodes = flatten(root, 1200);
        String cleanPrompt = normalize(prompt);
        String cleanBaseline = normalize(baseline);
        String best = "";
        double bestScore = -1.0;

        for (int i = 0; i < nodes.size(); i++) {
            AccessibilityNodeInfo node = nodes.get(i);
            if (node == null || node.isEditable()) continue;
            String value = safe(node.getText()).trim();
            if (value.length() < 20 || value.length() > 16_000) continue;

            String normalized = normalize(value);
            if (normalized.isEmpty()
                    || normalized.equals(cleanPrompt)
                    || normalized.equals(cleanBaseline)
                    || isStaticChromeOrChatGptText(normalized)) {
                continue;
            }

            double position = nodes.isEmpty() ? 0.0 : ((double) i / (double) nodes.size());
            double score = Math.min(value.length(), 3000) + (position * 700.0);

            String desc = normalize(safe(node.getContentDescription()));
            if (desc.contains("assistant") || desc.contains("chatgpt")) score += 500.0;

            if (score > bestScore) {
                bestScore = score;
                best = value;
            }
        }
        return best;
    }

    private static boolean isStaticChromeOrChatGptText(String value) {
        String[] blocked = {
                "chatgpt can make mistakes",
                "chatgptは間違いを犯す",
                "new chat",
                "新しいチャット",
                "search chats",
                "チャットを検索",
                "log in",
                "ログイン",
                "sign up",
                "登録する",
                "temporary chat",
                "一時チャット"
        };
        for (String token : blocked) {
            if (value.equals(token) || value.startsWith(token + " ")) return true;
        }
        return false;
    }

    private static boolean hasAction(AccessibilityNodeInfo node, int actionId) {
        try {
            for (AccessibilityNodeInfo.AccessibilityAction action : node.getActionList()) {
                if (action.getId() == actionId) return true;
            }
        } catch (Throwable ignored) {
        }
        return false;
    }

    private static List<AccessibilityNodeInfo> flatten(
            AccessibilityNodeInfo root,
            int maxNodes) {
        ArrayList<AccessibilityNodeInfo> out = new ArrayList<>();
        ArrayList<AccessibilityNodeInfo> queue = new ArrayList<>();
        queue.add(root);

        for (int cursor = 0; cursor < queue.size() && out.size() < maxNodes; cursor++) {
            AccessibilityNodeInfo node = queue.get(cursor);
            if (node == null) continue;
            out.add(node);
            int children;
            try {
                children = node.getChildCount();
            } catch (Throwable ignored) {
                continue;
            }
            for (int i = 0; i < children && queue.size() < maxNodes; i++) {
                try {
                    AccessibilityNodeInfo child = node.getChild(i);
                    if (child != null) queue.add(child);
                } catch (Throwable ignored) {
                }
            }
        }
        return out;
    }

    private static String safe(CharSequence value) {
        return value == null ? "" : value.toString();
    }

    private static String normalize(String value) {
        return safe(value)
                .replace('\u00a0', ' ')
                .replaceAll("\\s+", " ")
                .trim()
                .toLowerCase(Locale.ROOT);
    }
}
