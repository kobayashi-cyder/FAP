package jp.fap.runtime;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final int REQ_RECORD_AUDIO = 601;

    private static final int BLACK = Color.rgb(15, 20, 25);
    private static final int MUTED = Color.rgb(83, 100, 113);
    private static final int BORDER = Color.rgb(239, 243, 244);
    private static final int SOFT = Color.rgb(247, 249, 249);
    private static final int BLUE = Color.rgb(29, 155, 240);

    private AgentOrchestrator agent;
    private PythonFapEngine engine;
    private AndroidVoiceController voice;
    private ChatLogStore chatLog;

    private TextView status;
    private EditText input;
    private FapTimelineView timeline;
    private Button sendButton;
    private Button voiceButton;
    private Button agentModeButton;
    private Button gitUpdateButton;
    private Button gitRollbackButton;
    private TextView timelineTab;
    private TextView frontTab;
    private TextView backTab;

    private PythonFapEngine.Result last;
    private String logViewMode = "timeline";
    private boolean voiceLoop = false;
    private boolean resumeVoiceAfterGit = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        configureLightWindow();

        agent = AgentOrchestrator.get(this);
        engine = agent.engine();
        chatLog = agent.chatLog();
        agent.reconcileAsync();

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        root.addView(buildHeader(), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        root.addView(buildTabs(), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(48)));
        root.addView(buildToolStrip(), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(48)));

        timeline = new FapTimelineView(this);
        root.addView(timeline, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f));

        root.addView(buildComposer(), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));

        setContentView(root);
        renderTimeline();

        voice = new AndroidVoiceController(this, new AndroidVoiceController.Listener() {
            @Override public void onStatus(String message) {
                setStatus(message);
            }

            @Override public void onPartial(String text) {
                if (voiceLoop && text != null && !text.isEmpty()) {
                    setStatus("聞き取り中 · " + text);
                }
            }

            @Override public void onFinal(String text, float confidence) {
                if (!voiceLoop) return;
                runVoiceFap(text, confidence);
            }

            @Override public void onError(String message, boolean recoverable) {
                chatLog.appendBack("system", "voice", "音声エラー · " + message);
                renderTimeline();
                if (voiceLoop && recoverable) {
                    setStatus("音声を再接続中…");
                    mainHandler.postDelayed(() -> listenIfActive(), 420);
                } else if (!recoverable) {
                    stopVoiceLoop();
                }
            }
        });

        refreshAgentModeButton();
        refreshVoiceButton();
        setStatus(
                voice.capabilitySummary()
                        + " · "
                        + agent.stateSummary()
                        + " · "
                        + GitRuntimeUpdater.currentState(this));
    }

    private View buildHeader() {
        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.VERTICAL);
        header.setBackgroundColor(Color.WHITE);

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(16), dp(10), dp(12), dp(4));

        TextView title = new TextView(this);
        title.setText("FAP");
        title.setTextSize(21f);
        title.setTextColor(BLACK);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        top.addView(title, new LinearLayout.LayoutParams(0, dp(42), 1f));

        TextView gitRefresh = iconButton("↻");
        gitRefresh.setContentDescription("Git補足を更新");
        gitRefresh.setOnClickListener(v -> {
            agent.refreshGitContextAsync(true);
            chatLog.appendBack("system", "git-context", "Git補足の手動更新を要求");
            setStatus("Git補足を更新中…");
            mainHandler.postDelayed(this::renderTimeline, 900);
        });
        top.addView(gitRefresh, new LinearLayout.LayoutParams(dp(42), dp(42)));

        header.addView(top);

        status = new TextView(this);
        status.setTextSize(12f);
        status.setTextColor(MUTED);
        status.setSingleLine(true);
        status.setPadding(dp(16), 0, dp(16), dp(8));
        header.addView(status);

        View line = new View(this);
        line.setBackgroundColor(BORDER);
        header.addView(line, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(1)));
        return header;
    }

    private View buildTabs() {
        LinearLayout tabs = new LinearLayout(this);
        tabs.setOrientation(LinearLayout.HORIZONTAL);
        tabs.setBackgroundColor(Color.WHITE);

        timelineTab = tab("タイムライン", "timeline");
        frontTab = tab("会話", "front");
        backTab = tab("裏側", "back");

        tabs.addView(timelineTab, new LinearLayout.LayoutParams(0, dp(48), 1f));
        tabs.addView(frontTab, new LinearLayout.LayoutParams(0, dp(48), 1f));
        tabs.addView(backTab, new LinearLayout.LayoutParams(0, dp(48), 1f));
        refreshTabs();
        return tabs;
    }

    private TextView tab(String label, String mode) {
        TextView tab = new TextView(this);
        tab.setText(label);
        tab.setGravity(Gravity.CENTER);
        tab.setTextSize(14f);
        tab.setOnClickListener(v -> {
            logViewMode = mode;
            refreshTabs();
            renderTimeline();
        });
        return tab;
    }

    private View buildToolStrip() {
        HorizontalScrollView scroll = new HorizontalScrollView(this);
        scroll.setHorizontalScrollBarEnabled(false);
        scroll.setBackgroundColor(Color.WHITE);

        LinearLayout tools = new LinearLayout(this);
        tools.setOrientation(LinearLayout.HORIZONTAL);
        tools.setGravity(Gravity.CENTER_VERTICAL);
        tools.setPadding(dp(12), dp(5), dp(12), dp(5));

        agentModeButton = chip("Agent");
        agentModeButton.setOnClickListener(v -> {
            agent.setAgentModeEnabled(!agent.isAgentModeEnabled());
            refreshAgentModeButton();
            renderTimeline();
            setStatus(agent.stateSummary());
        });
        tools.addView(agentModeButton);

        voiceButton = chip("音声");
        voiceButton.setOnClickListener(v -> toggleVoiceLoop());
        tools.addView(voiceButton);

        Button browser = chip("Browser");
        browser.setOnClickListener(v -> {
            if (!PixelBrowserController.isAccessibilityEnabled(this)) {
                PixelBrowserController.openAccessibilitySettings(this);
                return;
            }
            String q = input.getText().toString().trim();
            if (q.isEmpty()) {
                Toast.makeText(this, "下の入力欄へ指示を入れてください", Toast.LENGTH_SHORT).show();
                return;
            }
            if (PixelBrowserController.askChatGpt(this, q)) {
                chatLog.appendFront("user", "browser", q);
                input.setText("");
                renderTimeline();
                setStatus("Browserへ送信しました");
            }
        });
        tools.addView(browser);

        Button browserSetup = chip("Browser設定");
        browserSetup.setOnClickListener(v ->
                PixelBrowserController.openAccessibilitySettings(this));
        tools.addView(browserSetup);

        gitUpdateButton = chip("Git更新");
        gitUpdateButton.setOnClickListener(v -> startGitRuntimeUpdate());
        tools.addView(gitUpdateButton);

        Button gitContext = chip("Git補足");
        gitContext.setOnClickListener(v -> {
            agent.refreshGitContextAsync(true);
            setStatus("Git main / manifestを確認中…");
            mainHandler.postDelayed(this::renderTimeline, 900);
        });
        tools.addView(gitContext);

        gitRollbackButton = chip("前版へ");
        gitRollbackButton.setOnClickListener(v -> startGitRollback());
        tools.addView(gitRollbackButton);

        Button verifyOk = chip("✓");
        verifyOk.setContentDescription("直前の回答を検証OKとして記録");
        verifyOk.setOnClickListener(v -> verify(true));
        tools.addView(verifyOk);

        Button verifyNg = chip("×");
        verifyNg.setContentDescription("直前の回答を失敗として記録");
        verifyNg.setOnClickListener(v -> verify(false));
        tools.addView(verifyNg);

        Button clear = chip("履歴消去");
        clear.setOnClickListener(v -> {
            engine.clear();
            chatLog.clear();
            agent.resetDurableState();
            renderTimeline();
            setStatus("履歴を消去しました");
        });
        tools.addView(clear);

        scroll.addView(tools, new HorizontalScrollView.LayoutParams(
                HorizontalScrollView.LayoutParams.WRAP_CONTENT,
                HorizontalScrollView.LayoutParams.MATCH_PARENT));
        return scroll;
    }

    private View buildComposer() {
        LinearLayout wrapper = new LinearLayout(this);
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setBackgroundColor(Color.WHITE);

        View line = new View(this);
        line.setBackgroundColor(BORDER);
        wrapper.addView(line, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(1)));

        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.HORIZONTAL);
        composer.setGravity(Gravity.BOTTOM);
        composer.setPadding(dp(12), dp(8), dp(12), dp(10));

        TextView avatar = new TextView(this);
        avatar.setText("あ");
        avatar.setGravity(Gravity.CENTER);
        avatar.setTextSize(14f);
        avatar.setTypeface(Typeface.DEFAULT_BOLD);
        avatar.setTextColor(BLACK);
        avatar.setBackground(circle(SOFT));
        LinearLayout.LayoutParams avatarParams = new LinearLayout.LayoutParams(dp(38), dp(38));
        avatarParams.setMargins(0, dp(2), dp(8), 0);
        composer.addView(avatar, avatarParams);

        input = new EditText(this);
        input.setHint("いまどうしてる？ / FAPへ指示");
        input.setHintTextColor(MUTED);
        input.setTextColor(BLACK);
        input.setTextSize(15f);
        input.setMinLines(1);
        input.setMaxLines(5);
        input.setGravity(Gravity.TOP);
        input.setPadding(dp(14), dp(10), dp(14), dp(10));
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        input.setBackground(roundRect(SOFT, 22, 0, 0));
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.WRAP_CONTENT,
                1f);
        inputParams.setMargins(0, 0, dp(8), 0);
        composer.addView(input, inputParams);

        sendButton = new Button(this);
        sendButton.setText("投稿");
        sendButton.setTextSize(14f);
        sendButton.setTextColor(Color.WHITE);
        sendButton.setAllCaps(false);
        sendButton.setTypeface(Typeface.DEFAULT_BOLD);
        sendButton.setPadding(dp(16), 0, dp(16), 0);
        sendButton.setBackground(roundRect(BLACK, 22, 0, 0));
        sendButton.setOnClickListener(v -> runFap());
        composer.addView(sendButton, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                dp(44)));

        wrapper.addView(composer);
        return wrapper;
    }

    private void startGitRuntimeUpdate() {
        if (gitUpdateButton == null || !gitUpdateButton.isEnabled()) return;
        pauseVoiceForGitOperation();
        gitUpdateButton.setEnabled(false);
        gitRollbackButton.setEnabled(false);
        chatLog.appendBack(
                "system",
                "git-ota",
                "完全ランタイム更新を開始 · " + GitRuntimeUpdater.currentState(this));
        renderTimeline();
        setStatus("Git完全更新を開始…");

        GitRuntimeUpdater.updateAsync(this, engine, new GitRuntimeUpdater.Listener() {
            @Override public void onStatus(String message) {
                setStatus(message);
            }

            @Override public void onComplete(boolean success, String message) {
                gitUpdateButton.setEnabled(true);
                gitRollbackButton.setEnabled(true);
                chatLog.appendBack(
                        "system",
                        "git-ota",
                        (success ? "更新完了 · " : "更新失敗 · ")
                                + message
                                + " · "
                                + GitRuntimeUpdater.currentState(MainActivity.this));
                agent.refreshGitContextAsync(true);
                renderTimeline();
                resumeVoiceAfterGitOperation();
                setStatus(message);
            }
        });
    }

    private void startGitRollback() {
        if (gitRollbackButton == null || !gitRollbackButton.isEnabled()) return;
        pauseVoiceForGitOperation();
        gitUpdateButton.setEnabled(false);
        gitRollbackButton.setEnabled(false);
        chatLog.appendBack("system", "git-ota", "前版へのロールバックを開始");
        renderTimeline();

        GitRuntimeUpdater.rollbackAsync(this, engine, new GitRuntimeUpdater.Listener() {
            @Override public void onStatus(String message) {
                setStatus(message);
            }

            @Override public void onComplete(boolean success, String message) {
                gitUpdateButton.setEnabled(true);
                gitRollbackButton.setEnabled(true);
                chatLog.appendBack(
                        "system",
                        "git-ota",
                        (success ? "ロールバック完了 · " : "ロールバック失敗 · ")
                                + message
                                + " · "
                                + GitRuntimeUpdater.currentState(MainActivity.this));
                agent.refreshGitContextAsync(true);
                renderTimeline();
                resumeVoiceAfterGitOperation();
                setStatus(message);
            }
        });
    }

    private void runFap() {
        String q = input.getText().toString().trim();
        if (q.isEmpty() || !sendButton.isEnabled()) return;

        input.setText("");
        sendButton.setEnabled(false);

        agent.submitUserTurn("text", q, new AgentOrchestrator.Listener() {
            @Override public void onStatus(String message) {
                renderTimeline();
                setStatus(message);
            }

            @Override public void onReply(PythonFapEngine.Result result, String channel) {
                last = result;
                renderTimeline();
                setStatus("FAP · " + result.skill + " · " + String.format("%.2f", result.confidence));
                sendButton.setEnabled(true);
            }
        });
        renderTimeline();
    }

    private void runVoiceFap(String q, float sttConfidence) {
        if (q == null || q.trim().isEmpty()) {
            listenIfActive();
            return;
        }

        chatLog.appendBack(
                "system",
                "voice-meta",
                "STT確定 · confidence=" + String.format("%.2f", sttConfidence));
        sendButton.setEnabled(false);

        agent.submitUserTurn("voice", q.trim(), new AgentOrchestrator.Listener() {
            @Override public void onStatus(String message) {
                renderTimeline();
                setStatus("音声 · " + message);
            }

            @Override public void onReply(PythonFapEngine.Result result, String channel) {
                last = result;
                renderTimeline();
                sendButton.setEnabled(true);
                if (!voiceLoop) {
                    setStatus(engine.status());
                    return;
                }
                setStatus("FAPが読み上げ中…");
                voice.speak(result.answer, () -> listenIfActive());
            }
        });
        renderTimeline();
    }

    private void toggleVoiceLoop() {
        if (voiceLoop) stopVoiceLoop();
        else startVoiceLoop();
    }

    private void startVoiceLoop() {
        if (voice == null || !voice.isRecognitionAvailable()) {
            Toast.makeText(this, "この端末では音声認識サービスを利用できません", Toast.LENGTH_LONG).show();
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_RECORD_AUDIO);
            return;
        }
        voiceLoop = true;
        refreshVoiceButton();
        chatLog.appendBack("system", "voice", "音声会話を開始");
        renderTimeline();
        listenIfActive();
    }

    private void stopVoiceLoop() {
        voiceLoop = false;
        if (voice != null) voice.stopAll();
        refreshVoiceButton();
        chatLog.appendBack("system", "voice", "音声会話を停止");
        renderTimeline();
        setStatus(engine.status());
    }

    private void listenIfActive() {
        if (!voiceLoop || voice == null) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            stopVoiceLoop();
            return;
        }
        voice.startListening();
    }

    @Override public void onRequestPermissionsResult(
            int requestCode,
            String[] permissions,
            int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_RECORD_AUDIO) return;
        if (grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            voiceLoop = true;
            refreshVoiceButton();
            listenIfActive();
        } else {
            stopVoiceLoop();
            Toast.makeText(this, "音声会話にはマイク権限が必要です", Toast.LENGTH_LONG).show();
        }
    }

    private void verify(boolean success) {
        if (last == null) return;
        engine.verify(last, success);
        chatLog.appendBack(
                "system",
                "agent-review",
                success ? "直前のFAP回答を検証OKとして記録" : "直前のFAP回答を失敗として記録");
        renderTimeline();
        setStatus(engine.status());
    }

    private void renderTimeline() {
        if (timeline == null || chatLog == null) return;
        timeline.render(chatLog.snapshot(logViewMode, 300));
    }

    private void refreshTabs() {
        setTabState(timelineTab, "timeline".equals(logViewMode));
        setTabState(frontTab, "front".equals(logViewMode));
        setTabState(backTab, "back".equals(logViewMode));
    }

    private void setTabState(TextView tab, boolean selected) {
        if (tab == null) return;
        tab.setTextColor(selected ? BLACK : MUTED);
        tab.setTypeface(Typeface.DEFAULT, selected ? Typeface.BOLD : Typeface.NORMAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.WHITE);
        if (selected) {
            bg.setStroke(dp(3), BLACK);
        }
        tab.setBackground(bg);
    }

    private void refreshAgentModeButton() {
        if (agentModeButton == null || agent == null) return;
        styleChip(
                agentModeButton,
                agent.isAgentModeEnabled() ? "Agent ON" : "Agent OFF",
                agent.isAgentModeEnabled());
    }

    private void refreshVoiceButton() {
        if (voiceButton == null) return;
        styleChip(voiceButton, voiceLoop ? "音声 ON" : "音声", voiceLoop);
    }

    private void pauseVoiceForGitOperation() {
        resumeVoiceAfterGit = voiceLoop;
        if (voiceLoop && voice != null) {
            voice.stopAll();
            voiceLoop = false;
            refreshVoiceButton();
        }
    }

    private void resumeVoiceAfterGitOperation() {
        if (!resumeVoiceAfterGit) return;
        resumeVoiceAfterGit = false;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED) {
            voiceLoop = true;
            refreshVoiceButton();
            mainHandler.postDelayed(this::listenIfActive, 350);
        }
    }

    private void refreshBrowserState() {
        String browserState = PixelBrowserController.state(this);
        if (PixelBrowserController.STATE_ERROR.equals(browserState)) {
            chatLog.appendBack(
                    "system",
                    "browser-raw",
                    "Browser error · " + PixelBrowserController.lastError(this));
            renderTimeline();
        }
    }

    @Override protected void onPause() {
        super.onPause();
        if (voiceLoop && voice != null) {
            voice.stopListening();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        agent.reconcileAsync();
        agent.refreshGitContextAsync(false);
        refreshBrowserState();
        refreshAgentModeButton();
        refreshVoiceButton();
        refreshTabs();
        renderTimeline();
        if (voiceLoop && voice != null) {
            mainHandler.postDelayed(this::listenIfActive, 250);
        }
    }

    @Override protected void onDestroy() {
        voiceLoop = false;
        mainHandler.removeCallbacksAndMessages(null);
        if (voice != null) voice.close();
        super.onDestroy();
    }

    private void configureLightWindow() {
        Window window = getWindow();
        window.setStatusBarColor(Color.WHITE);
        window.setNavigationBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                        | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    }

    private void setStatus(String text) {
        if (status == null) return;
        status.setText(text == null ? "" : text);
    }

    private TextView iconButton(String text) {
        TextView button = new TextView(this);
        button.setText(text);
        button.setTextSize(22f);
        button.setTextColor(BLACK);
        button.setGravity(Gravity.CENTER);
        button.setBackground(circle(Color.WHITE));
        return button;
    }

    private Button chip(String text) {
        Button button = new Button(this);
        button.setAllCaps(false);
        button.setTextSize(12f);
        button.setPadding(dp(12), 0, dp(12), 0);
        styleChip(button, text, false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                dp(36));
        params.setMargins(dp(3), 0, dp(3), 0);
        button.setLayoutParams(params);
        return button;
    }

    private void styleChip(Button button, String text, boolean active) {
        button.setText(text);
        button.setTextColor(active ? Color.WHITE : BLACK);
        button.setTypeface(Typeface.DEFAULT_BOLD);
        button.setBackground(roundRect(
                active ? BLACK : Color.WHITE,
                18,
                active ? 0 : Color.rgb(207, 217, 222),
                active ? 0 : 1));
    }

    private GradientDrawable roundRect(int fill, int radiusDp, int strokeColor, int strokeDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(radiusDp));
        if (strokeDp > 0) drawable.setStroke(dp(strokeDp), strokeColor);
        return drawable;
    }

    private GradientDrawable circle(int fill) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.OVAL);
        drawable.setColor(fill);
        return drawable;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
