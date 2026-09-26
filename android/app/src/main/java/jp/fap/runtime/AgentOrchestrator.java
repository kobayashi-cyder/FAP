package jp.fap.runtime;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class AgentOrchestrator {
    public interface Listener {
        void onStatus(String message);
        void onReply(PythonFapEngine.Result result, String channel);
    }

    private static final String PREFS = "fap_agent_state";
    private static final String KEY_ENABLED = "enabled";
    private static final String KEY_LAST_USER_ID = "last_user_id";
    private static final String KEY_LAST_BROWSER_ID = "last_browser_id";
    private static final String KEY_PENDING_USER_ID = "pending_browser_user_id";
    private static final String KEY_PENDING_PROMPT = "pending_browser_prompt";
    private static final String KEY_PENDING_CHANNEL = "pending_browser_channel";
    private static final String KEY_INFLIGHT_USER_ID = "inflight_user_id";
    private static final String KEY_INFLIGHT_STARTED_AT = "inflight_started_at";

    private static final int MAX_CONTEXT_LOGS = 48;
    private static final int MAX_RECOVERY_SCAN = 96;

    private static AgentOrchestrator instance;

    public static synchronized AgentOrchestrator get(Context context) {
        if (instance == null) {
            instance = new AgentOrchestrator(context.getApplicationContext());
        }
        return instance;
    }

    private final Context app;
    private final SharedPreferences prefs;
    private final ChatLogStore chatLog;
    private final PythonFapEngine engine;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "fap-agent-orchestrator");
        t.setDaemon(true);
        return t;
    });

    private volatile Listener pendingBrowserListener;

    private AgentOrchestrator(Context context) {
        app = context;
        prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        chatLog = new ChatLogStore(app);
        engine = new PythonFapEngine(app);
    }

    public PythonFapEngine engine() {
        return engine;
    }

    public ChatLogStore chatLog() {
        return chatLog;
    }

    public boolean isAgentModeEnabled() {
        return prefs.getBoolean(KEY_ENABLED, true);
    }

    public void setAgentModeEnabled(boolean enabled) {
        prefs.edit().putBoolean(KEY_ENABLED, enabled).apply();
        chatLog.appendBack(
                "system",
                "agent",
                enabled ? "Agent mode: ON" : "Agent mode: OFF");
    }

    public String stateSummary() {
        long pending = prefs.getLong(KEY_PENDING_USER_ID, 0L);
        return "agent=" + (isAgentModeEnabled() ? "ON" : "OFF")
                + " · cursor=" + prefs.getLong(KEY_LAST_USER_ID, 0L)
                + " · browserCursor=" + prefs.getLong(KEY_LAST_BROWSER_ID, 0L)
                + (pending > 0L ? " · pendingBrowser=#" + pending : "");
    }

    public void submitUserTurn(
            String channel,
            String text,
            Listener listener) {
        String clean = text == null ? "" : text.trim();
        if (clean.isEmpty()) return;

        ChatLogStore.Entry entry = chatLog.appendFront("user", channel, clean);
        if (entry == null) return;
        prefs.edit()
                .putLong(KEY_LAST_USER_ID, Math.max(
                        prefs.getLong(KEY_LAST_USER_ID, 0L),
                        entry.id))
                .putLong(KEY_INFLIGHT_USER_ID, entry.id)
                .putLong(KEY_INFLIGHT_STARTED_AT, System.currentTimeMillis())
                .apply();
        processUserEntryAsync(entry, listener, true);
    }

    public void reconcileAsync() {
        GitContextProvider.refreshIfDueAsync(app, chatLog);
        executor.execute(this::reconcileBlocking);
    }

    public void refreshGitContextAsync(boolean force) {
        if (force) {
            GitContextProvider.forceRefreshAsync(app, chatLog);
        } else {
            GitContextProvider.refreshIfDueAsync(app, chatLog);
        }
    }

    public void onBrowserResult(String originalPrompt, String response) {
        String cleanResponse = response == null ? "" : response.trim();
        if (cleanResponse.isEmpty()) return;

        executor.execute(() -> {
            String logged = cleanResponse + "\n[core] pixel_browser:chatgpt_web";
            if (!chatLog.containsRecent(
                    "system",
                    "browser-raw",
                    ChatLogStore.SURFACE_BACK,
                    logged,
                    32)) {
                chatLog.appendBack("system", "browser-raw", logged);
            }

            long pendingUserId = prefs.getLong(KEY_PENDING_USER_ID, 0L);
            String pendingPrompt = prefs.getString(KEY_PENDING_PROMPT, "");
            String pendingChannel = prefs.getString(KEY_PENDING_CHANNEL, "agent");
            Listener listener = pendingBrowserListener;
            pendingBrowserListener = null;

            if (pendingUserId <= 0L) {
                prefs.edit()
                        .putLong(KEY_LAST_BROWSER_ID, chatLog.lastId())
                        .apply();
                return;
            }

            String prompt = pendingPrompt == null || pendingPrompt.trim().isEmpty()
                    ? (originalPrompt == null ? "" : originalPrompt.trim())
                    : pendingPrompt.trim();

            status(listener, "ブラウザ結果をFAPへ戻して統合中…");

            String synthesis = "元のユーザー依頼:\n"
                    + prompt
                    + "\n\nブラウザから取得した外部回答:\n"
                    + cleanResponse
                    + "\n\nこの外部回答を根拠候補として使い、"
                    + "元の依頼へ直接答えてください。"
                    + "外部回答にない事実は作らず、不確実ならその旨を示してください。";

            PythonFapEngine.Result result = engine.processAgent(
                    synthesis,
                    chatLog.recentConversationJson(MAX_CONTEXT_LOGS),
                    "browser-synthesis");

            appendAgentReply(result, "agent:web");
            clearPendingBrowser();
            prefs.edit()
                    .putLong(KEY_LAST_BROWSER_ID, chatLog.lastId())
                    .putLong(KEY_LAST_USER_ID, Math.max(
                            prefs.getLong(KEY_LAST_USER_ID, 0L),
                            pendingUserId))
                    .remove(KEY_INFLIGHT_USER_ID)
                    .remove(KEY_INFLIGHT_STARTED_AT)
                    .apply();
            reply(listener, result, pendingChannel);
        });
    }

    private void processUserEntryAsync(
            ChatLogStore.Entry entry,
            Listener listener,
            boolean allowBrowser) {
        executor.execute(() -> processUserEntryBlocking(entry, listener, allowBrowser));
    }

    private void processUserEntryBlocking(
            ChatLogStore.Entry entry,
            Listener listener,
            boolean allowBrowser) {
        status(listener, "Chatログ #" + entry.id + " をFAPが処理中…");

        PythonFapEngine.Result result = engine.processAgent(
                entry.text,
                chatLog.recentConversationJson(MAX_CONTEXT_LOGS),
                entry.channel);

        if (allowBrowser
                && isAgentModeEnabled()
                && result.needsExternalHelp()
                && PixelBrowserController.isAccessibilityEnabled(app)) {
            prefs.edit()
                    .putLong(KEY_PENDING_USER_ID, entry.id)
                    .putString(KEY_PENDING_PROMPT, entry.text)
                    .putString(KEY_PENDING_CHANNEL, entry.channel)
                    .putLong(KEY_LAST_USER_ID, Math.max(
                            prefs.getLong(KEY_LAST_USER_ID, 0L),
                            entry.id))
                    .apply();
            pendingBrowserListener = listener;

            chatLog.appendBack(
                    "system",
                    "agent",
                    "Chrome/ChatGPTへ外部調査を1回だけ委譲"
                            + " · user=#" + entry.id
                            + " · localSkill=" + result.skill
                            + " · confidence=" + String.format("%.2f", result.confidence)
                            + " · state=" + result.state);

            boolean opened = PixelBrowserController.askChatGpt(
                    app,
                    buildBrowserResearchPrompt(entry.text),
                    true);
            if (opened) {
                status(listener, "Chrome/ChatGPTへ調査を委譲しました");
                return;
            }

            clearPendingBrowser();
            pendingBrowserListener = null;
        }

        appendAgentReply(result, entry.channel);
        prefs.edit()
                .putLong(KEY_LAST_USER_ID, Math.max(
                        prefs.getLong(KEY_LAST_USER_ID, 0L),
                        entry.id))
                .remove(KEY_INFLIGHT_USER_ID)
                .remove(KEY_INFLIGHT_STARTED_AT)
                .apply();
        reply(listener, result, entry.channel);
    }

    private void reconcileBlocking() {
        long cursor = prefs.getLong(KEY_LAST_USER_ID, 0L);
        long inflightId = prefs.getLong(KEY_INFLIGHT_USER_ID, 0L);

        if (inflightId > 0L) {
            ChatLogStore.Entry inflight = findEntry(inflightId);
            if (inflight == null || chatLog.hasFrontAssistantAfter(inflightId)) {
                prefs.edit()
                        .remove(KEY_INFLIGHT_USER_ID)
                        .remove(KEY_INFLIGHT_STARTED_AT)
                        .apply();
            } else if (prefs.getLong(KEY_PENDING_USER_ID, 0L) <= 0L) {
                processUserEntryBlocking(inflight, null, true);
            }
        }

        cursor = prefs.getLong(KEY_LAST_USER_ID, cursor);
        List<ChatLogStore.Entry> rows = chatLog.entriesAfter(cursor, MAX_RECOVERY_SCAN);

        for (ChatLogStore.Entry entry : rows) {
            if (!"user".equals(entry.role)) continue;
            cursor = Math.max(cursor, entry.id);
            prefs.edit().putLong(KEY_LAST_USER_ID, cursor).apply();

            if ("browser".equals(entry.channel)) continue;
            if (chatLog.hasFrontAssistantAfter(entry.id)) continue;

            prefs.edit()
                    .putLong(KEY_INFLIGHT_USER_ID, entry.id)
                    .putLong(KEY_INFLIGHT_STARTED_AT, System.currentTimeMillis())
                    .apply();
            processUserEntryBlocking(entry, null, true);

            // A browser delegation is now pending. Wait for AccessibilityService
            // rather than consuming later user events out of order.
            if (prefs.getLong(KEY_PENDING_USER_ID, 0L) > 0L) break;
        }

        if (prefs.getLong(KEY_PENDING_USER_ID, 0L) > 0L) {
            long browserCursor = prefs.getLong(KEY_LAST_BROWSER_ID, 0L);
            for (ChatLogStore.Entry entry
                    : chatLog.entriesAfter(browserCursor, MAX_RECOVERY_SCAN)) {
                if (ChatLogStore.SURFACE_BACK.equals(entry.surface)
                        && "system".equals(entry.role)
                        && "browser-raw".equals(entry.channel)) {
                    String text = stripBrowserCore(entry.text);
                    onBrowserResult(
                            prefs.getString(KEY_PENDING_PROMPT, ""),
                            text);
                    break;
                }
            }
        }
    }

    private ChatLogStore.Entry findEntry(long id) {
        if (id <= 0L) return null;
        for (ChatLogStore.Entry entry : chatLog.entriesAfter(id - 1L, 2)) {
            if (entry.id == id) return entry;
        }
        return null;
    }

    public void resetDurableState() {
        clearPendingBrowser();
        pendingBrowserListener = null;
        prefs.edit()
                .remove(KEY_LAST_USER_ID)
                .remove(KEY_LAST_BROWSER_ID)
                .remove(KEY_INFLIGHT_USER_ID)
                .remove(KEY_INFLIGHT_STARTED_AT)
                .apply();
    }

    private void appendAgentReply(PythonFapEngine.Result result, String sourceChannel) {
        String answer = result.answer == null ? "" : result.answer.trim();
        if (answer.isEmpty()) {
            answer = "このターンでは確定回答を生成できませんでした。";
        }
        chatLog.appendFront(
                "assistant",
                "agent:" + normalizeChannel(sourceChannel),
                answer);
        chatLog.appendBack(
                "system",
                "agent-result",
                "finalized"
                        + " · source=" + normalizeChannel(sourceChannel)
                        + " · skill=" + result.skill
                        + " · confidence=" + String.format("%.2f", result.confidence)
                        + " · state=" + result.state);
    }

    private void clearPendingBrowser() {
        prefs.edit()
                .remove(KEY_PENDING_USER_ID)
                .remove(KEY_PENDING_PROMPT)
                .remove(KEY_PENDING_CHANNEL)
                .apply();
    }

    private static String buildBrowserResearchPrompt(String userText) {
        return "次のユーザー依頼について、必要な事実を確認し、"
                + "簡潔で直接的な回答を作ってください。"
                + "不明な点は推測せず明示してください。\n\n"
                + userText;
    }

    private static String stripBrowserCore(String text) {
        if (text == null) return "";
        int marker = text.indexOf("\n[core] pixel_browser:");
        return marker >= 0 ? text.substring(0, marker).trim() : text.trim();
    }

    private static String normalizeChannel(String channel) {
        String value = channel == null ? "chat" : channel.trim().toLowerCase();
        return value.replaceAll("[^a-z0-9_.:-]", "_");
    }

    private void status(Listener listener, String message) {
        if (listener == null) return;
        main.post(() -> listener.onStatus(message));
    }

    private void reply(
            Listener listener,
            PythonFapEngine.Result result,
            String channel) {
        if (listener == null) return;
        main.post(() -> listener.onReply(result, channel));
    }
}
