package jp.fap.runtime;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

public final class AgentOrchestrator {
    public interface Listener {
        void onStatus(String message);
        void onReply(PythonFapEngine.Result result, String channel);
        default void onStream(String partial) {}
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
    private static final String KEY_PENDING_GENERATION = "pending_browser_generation";

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
    private final AtomicLong turnGeneration = new AtomicLong(0L);
    private volatile boolean processing = false;

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
                + " · processing=" + (processing ? "ON" : "OFF")
                + " · cursor=" + prefs.getLong(KEY_LAST_USER_ID, 0L)
                + " · browserCursor=" + prefs.getLong(KEY_LAST_BROWSER_ID, 0L)
                + (pending > 0L ? " · pendingBrowser=#" + pending : "");
    }

    public boolean isProcessing() {
        return processing;
    }

    public void stopCurrentTurn() {
        turnGeneration.incrementAndGet();
        processing = false;
        clearPendingBrowser();
        pendingBrowserListener = null;
        prefs.edit()
                .remove(KEY_INFLIGHT_USER_ID)
                .remove(KEY_INFLIGHT_STARTED_AT)
                .apply();
        chatLog.appendBack("system", "agent", "現在の回答処理を停止");
    }

    public void markCurrentLogAsSeen() {
        long last = chatLog.lastId();
        prefs.edit()
                .putLong(KEY_LAST_USER_ID, last)
                .putLong(KEY_LAST_BROWSER_ID, last)
                .remove(KEY_INFLIGHT_USER_ID)
                .remove(KEY_INFLIGHT_STARTED_AT)
                .apply();
    }

    public void submitUserTurn(
            String channel,
            String text,
            Listener listener) {
        submitUserTurn(channel, text, null, listener);
    }

    public void submitUserTurn(
            String channel,
            String text,
            java.util.List<AttachmentStore.Attachment> attachments,
            Listener listener) {
        submitUserTurnInternal(channel, text, attachments, listener, false);
    }

    public void submitWebResearch(String text, Listener listener) {
        submitUserTurnInternal("web", text, null, listener, true);
    }

    private void submitUserTurnInternal(
            String channel,
            String text,
            java.util.List<AttachmentStore.Attachment> attachments,
            Listener listener,
            boolean forceBrowser) {
        String clean = text == null ? "" : text.trim();
        String attachmentText = AttachmentStore.describe(attachments);
        if (clean.isEmpty() && attachmentText.isEmpty()) return;

        StringBuilder durable = new StringBuilder();
        if (!clean.isEmpty()) durable.append(clean);
        if (!attachmentText.isEmpty()) {
            if (durable.length() > 0) durable.append("\n\n");
            durable.append("[添付ファイル]\n").append(attachmentText);
        }

        ChatLogStore.Entry entry = chatLog.appendFront(
                "user",
                attachments == null || attachments.isEmpty()
                        ? channel
                        : channel + ":file",
                durable.toString());
        if (entry == null) return;

        if (attachments != null && !attachments.isEmpty()) {
            chatLog.appendBack(
                    "system",
                    "file-ingest",
                    "添付をAgent入力へ取り込み"
                            + " · count=" + attachments.size()
                            + " · user=#" + entry.id
                            + "\n" + attachmentText);
        }

        prefs.edit()
                .putLong(KEY_LAST_USER_ID, Math.max(
                        prefs.getLong(KEY_LAST_USER_ID, 0L),
                        entry.id))
                .putLong(KEY_INFLIGHT_USER_ID, entry.id)
                .putLong(KEY_INFLIGHT_STARTED_AT, System.currentTimeMillis())
                .apply();
        long generation = turnGeneration.incrementAndGet();
        processing = true;
        processUserEntryAsync(entry, listener, true, forceBrowser, generation);
    }

    public void regenerateLastUser(Listener listener) {
        ChatLogStore.Entry lastUser = null;
        List<ChatLogStore.Entry> rows = chatLog.snapshot("front", 300);
        for (int i = rows.size() - 1; i >= 0; i--) {
            ChatLogStore.Entry row = rows.get(i);
            if ("user".equals(row.role)) {
                lastUser = row;
                break;
            }
        }
        if (lastUser == null) {
            status(listener, "再生成できるユーザー発言がありません");
            return;
        }

        final ChatLogStore.Entry source = lastUser;
        final long generation = turnGeneration.incrementAndGet();
        processing = true;
        executor.execute(() -> {
            status(listener, "直前の依頼を再生成中…");
            String prompt = "次のユーザー依頼へ、前回回答の単なる言い換えではなく、"
                    + "必要なら別の推論経路も使って改めて直接答えてください。\n\n"
                    + source.text;
            PythonFapEngine.Result result = engine.processAgent(
                    prompt,
                    chatLog.recentConversationJson(MAX_CONTEXT_LOGS),
                    "regenerate");
            if (!isGenerationActive(generation)) return;
            chatLog.appendBack(
                    "system",
                    "agent",
                    "直前のユーザー依頼を再生成 · source=#" + source.id);
            deliverResult(result, "regenerate", listener, generation);
        });
    }

    public void submitDeepReasoning(String text, Listener listener) {
        String clean = text == null ? "" : text.trim();
        if (clean.isEmpty()) return;

        ChatLogStore.Entry entry = chatLog.appendFront("user", "deep", clean);
        if (entry == null) return;

        prefs.edit()
                .putLong(KEY_LAST_USER_ID, Math.max(
                        prefs.getLong(KEY_LAST_USER_ID, 0L),
                        entry.id))
                .putLong(KEY_INFLIGHT_USER_ID, entry.id)
                .putLong(KEY_INFLIGHT_STARTED_AT, System.currentTimeMillis())
                .apply();

        final long generation = turnGeneration.incrementAndGet();
        processing = true;
        executor.execute(() -> {
            status(listener, "深考 1/3 · 初期解を生成中…");
            PythonFapEngine.Result first = engine.processAgent(
                    clean,
                    chatLog.recentConversationJson(MAX_CONTEXT_LOGS),
                    "deep-primary");
            if (!isGenerationActive(generation)) return;

            status(listener, "深考 2/3 · 反例と弱点を検査中…");
            String critiquePrompt = "元の依頼:\n" + clean
                    + "\n\n初期回答:\n" + first.answer
                    + "\n\nこの回答の事実誤認、論理飛躍、抜け、反例、より良い解法を検査してください。"
                    + "単なる言い換えは禁止です。";
            PythonFapEngine.Result critique = engine.processAgent(
                    critiquePrompt,
                    chatLog.recentConversationJson(MAX_CONTEXT_LOGS),
                    "deep-critic");
            if (!isGenerationActive(generation)) return;

            status(listener, "深考 3/3 · 統合回答を生成中…");
            String synthesis = "元の依頼:\n" + clean
                    + "\n\n初期回答:\n" + first.answer
                    + "\n\n批判・反例検査:\n" + critique.answer
                    + "\n\n上記を統合し、元の依頼へ直接答える最終回答を作ってください。"
                    + "批判で指摘された欠陥を残さないでください。";
            PythonFapEngine.Result result = engine.processAgent(
                    synthesis,
                    chatLog.recentConversationJson(MAX_CONTEXT_LOGS),
                    "deep-synthesis");
            if (!isGenerationActive(generation)) return;

            chatLog.appendBack(
                    "system",
                    "agent-result",
                    "deep_reasoning=3pass"
                            + " · first=" + first.skill
                            + " · critic=" + critique.skill
                            + " · final=" + result.skill);
            deliverResult(result, "deep", listener, generation);
        });
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
            long pendingGeneration = prefs.getLong(KEY_PENDING_GENERATION, 0L);
            String pendingPrompt = prefs.getString(KEY_PENDING_PROMPT, "");
            String pendingChannel = prefs.getString(KEY_PENDING_CHANNEL, "agent");
            Listener listener = pendingBrowserListener;
            pendingBrowserListener = null;

            if (pendingUserId <= 0L
                    || pendingGeneration <= 0L
                    || pendingGeneration != turnGeneration.get()) {
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

            if (!isGenerationActive(pendingGeneration)) return;
            clearPendingBrowser();
            prefs.edit()
                    .putLong(KEY_LAST_BROWSER_ID, chatLog.lastId())
                    .putLong(KEY_LAST_USER_ID, Math.max(
                            prefs.getLong(KEY_LAST_USER_ID, 0L),
                            pendingUserId))
                    .remove(KEY_INFLIGHT_USER_ID)
                    .remove(KEY_INFLIGHT_STARTED_AT)
                    .apply();
            deliverResult(result, "agent:web", listener, pendingGeneration);
        });
    }

    private void processUserEntryAsync(
            ChatLogStore.Entry entry,
            Listener listener,
            boolean allowBrowser,
            boolean forceBrowser,
            long generation) {
        executor.execute(() -> processUserEntryBlocking(
                entry, listener, allowBrowser, forceBrowser, generation));
    }

    private void processUserEntryBlocking(
            ChatLogStore.Entry entry,
            Listener listener,
            boolean allowBrowser,
            boolean forceBrowser,
            long generation) {
        status(listener, "Chatログ #" + entry.id + " をFAPが処理中…");

        PythonFapEngine.Result result = engine.processAgent(
                entry.text,
                chatLog.recentConversationJson(MAX_CONTEXT_LOGS),
                entry.channel);
        if (!isGenerationActive(generation)) return;

        boolean freshResearch = requiresFreshResearch(entry.text);
        if (allowBrowser
                && isAgentModeEnabled()
                && (forceBrowser || freshResearch || result.needsExternalHelp())
                && PixelBrowserController.isAccessibilityEnabled(app)) {
            prefs.edit()
                    .putLong(KEY_PENDING_USER_ID, entry.id)
                    .putString(KEY_PENDING_PROMPT, entry.text)
                    .putString(KEY_PENDING_CHANNEL, entry.channel)
                    .putLong(KEY_PENDING_GENERATION, generation)
                    .putLong(KEY_LAST_USER_ID, Math.max(
                            prefs.getLong(KEY_LAST_USER_ID, 0L),
                            entry.id))
                    .apply();
            pendingBrowserListener = listener;

            chatLog.appendBack(
                    "system",
                    "agent",
                    "Chrome/ChatGPTへ外部調査を1回だけ委譲"
                            + (forceBrowser ? " · forced=1" : "")
                            + (freshResearch ? " · fresh=1" : "")
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

        prefs.edit()
                .putLong(KEY_LAST_USER_ID, Math.max(
                        prefs.getLong(KEY_LAST_USER_ID, 0L),
                        entry.id))
                .remove(KEY_INFLIGHT_USER_ID)
                .remove(KEY_INFLIGHT_STARTED_AT)
                .apply();
        deliverResult(result, entry.channel, listener, generation);
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
                processUserEntryBlocking(
                        inflight,
                        null,
                        true,
                        false,
                        turnGeneration.incrementAndGet());
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
            processUserEntryBlocking(
                    entry,
                    null,
                    true,
                    false,
                    turnGeneration.incrementAndGet());

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

    private void deliverResult(
            PythonFapEngine.Result result,
            String sourceChannel,
            Listener listener,
            long generation) {
        if (!isGenerationActive(generation)) return;

        String answer = result.answer == null ? "" : result.answer.trim();
        if (answer.isEmpty()) {
            answer = "このターンでは確定回答を生成できませんでした。";
        }

        if (listener == null) {
            chatLog.appendFront(
                    "assistant",
                    "agent:" + normalizeChannel(sourceChannel),
                    answer);
            appendResultMeta(result, sourceChannel);
            processing = false;
            return;
        }

        ChatLogStore.Entry streamEntry = chatLog.appendFront(
                "assistant",
                "agent:" + normalizeChannel(sourceChannel),
                "…");
        if (streamEntry == null) {
            appendResultMeta(result, sourceChannel);
            processing = false;
            reply(listener, result, sourceChannel);
            return;
        }

        final String finalAnswer = answer;
        final long entryId = streamEntry.id;
        final int chunkSize = finalAnswer.length() > 6000 ? 320 : 180;
        streamChunk(
                result,
                sourceChannel,
                listener,
                generation,
                entryId,
                finalAnswer,
                chunkSize,
                0);
    }

    private void streamChunk(
            PythonFapEngine.Result result,
            String sourceChannel,
            Listener listener,
            long generation,
            long entryId,
            String answer,
            int chunkSize,
            int offset) {
        if (!isGenerationActive(generation)) return;

        int end = Math.min(answer.length(), offset + chunkSize);
        String partial = answer.substring(0, end);
        chatLog.updateText(entryId, partial);
        if (listener != null) {
            try {
                listener.onStream(partial);
            } catch (Throwable ignored) {
            }
        }

        if (end >= answer.length()) {
            appendResultMeta(result, sourceChannel);
            processing = false;
            prefs.edit()
                    .remove(KEY_INFLIGHT_USER_ID)
                    .remove(KEY_INFLIGHT_STARTED_AT)
                    .apply();
            reply(listener, result, sourceChannel);
            return;
        }

        main.postDelayed(
                () -> streamChunk(
                        result,
                        sourceChannel,
                        listener,
                        generation,
                        entryId,
                        answer,
                        chunkSize,
                        end),
                28L);
    }

    private void appendResultMeta(PythonFapEngine.Result result, String sourceChannel) {
        chatLog.appendBack(
                "system",
                "agent-result",
                "finalized"
                        + " · source=" + normalizeChannel(sourceChannel)
                        + " · skill=" + result.skill
                        + " · confidence=" + String.format("%.2f", result.confidence)
                        + " · state=" + result.state);
    }

    private boolean isGenerationActive(long generation) {
        return generation > 0L && generation == turnGeneration.get();
    }

    private void clearPendingBrowser() {
        prefs.edit()
                .remove(KEY_PENDING_USER_ID)
                .remove(KEY_PENDING_PROMPT)
                .remove(KEY_PENDING_CHANNEL)
                .remove(KEY_PENDING_GENERATION)
                .apply();
    }

    private static String buildBrowserResearchPrompt(String userText) {
        return "次のユーザー依頼について、必要ならウェブ検索を使って最新情報を確認し、"
                + "簡潔で直接的な回答を作ってください。"
                + "確認した外部情報には、可能な範囲で出典名とURLまたは参照先を添えてください。"
                + "不明な点は推測せず明示してください。\n\n"
                + userText;
    }

    private static boolean requiresFreshResearch(String text) {
        String value = text == null ? "" : text.toLowerCase(Locale.ROOT);
        String[] hints = {
                "最新", "今日", "現在", "今の", "ニュース", "天気", "価格",
                "相場", "発売", "アップデート", "更新情報", "version", "release",
                "latest", "today", "current", "news", "weather", "price"
        };
        for (String hint : hints) {
            if (value.contains(hint)) return true;
        }
        return false;
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
