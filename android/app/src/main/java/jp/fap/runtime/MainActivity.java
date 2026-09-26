package jp.fap.runtime;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.widget.*;

public class MainActivity extends Activity {
    private static final int REQ_RECORD_AUDIO = 601;

    private AgentOrchestrator agent;
    private PythonFapEngine engine;
    private AndroidVoiceController voice;
    private EditText input;
    private TextView output;
    private ScrollView chatScroll;
    private TextView status;
    private ChatLogStore chatLog;
    private Button run;
    private Button voiceButton;
    private Button gitUpdateButton;
    private Button gitRollbackButton;
    private Button agentModeButton;
    private PythonFapEngine.Result last;
    private boolean voiceLoop = false;
    private boolean resumeVoiceAfterGit = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        agent = AgentOrchestrator.get(this);
        engine = agent.engine();
        chatLog = agent.chatLog();
        agent.reconcileAsync();

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(28, 28, 28, 28);

        TextView title = new TextView(this);
        title.setText("FAP Android · Live Python Core");
        title.setTextSize(22f);
        root.addView(title);

        status = new TextView(this);
        status.setText(engine.status());
        root.addView(status);

        input = new EditText(this);
        input.setHint("質問・命令を入力");
        input.setMinLines(3);
        input.setGravity(Gravity.TOP);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        root.addView(input, new LinearLayout.LayoutParams(-1, 0, 1f));

        run = new Button(this);
        run.setText("FAPで処理");
        run.setOnClickListener(v -> runFap());
        root.addView(run);

        LinearLayout browserRow = new LinearLayout(this);
        Button browserSetup = new Button(this);
        browserSetup.setText("Pixelブラウザ設定");
        browserSetup.setOnClickListener(v ->
                PixelBrowserController.openAccessibilitySettings(this));
        browserRow.addView(browserSetup, new LinearLayout.LayoutParams(0, -2, 1f));

        Button browserAsk = new Button(this);
        browserAsk.setText("ChatGPTへ送る");
        browserAsk.setOnClickListener(v -> {
            String q = input.getText().toString().trim();
            if (q.isEmpty()) return;
            if (!PixelBrowserController.isAccessibilityEnabled(this)) {
                Toast.makeText(
                        this,
                        "先にFAP Pixel Browser Controlをユーザー補助で有効化してください",
                        Toast.LENGTH_LONG).show();
                PixelBrowserController.openAccessibilitySettings(this);
                return;
            }
            if (PixelBrowserController.askChatGpt(this, q)) {
                chatLog.append("user", "browser", q);
                renderChatLog();
                input.setText("");
                status.setText("PIXEL BROWSER · queued");
            } else {
                status.setText("PIXEL BROWSER · " + PixelBrowserController.lastError(this));
            }
        });
        browserRow.addView(browserAsk, new LinearLayout.LayoutParams(0, -2, 1f));

        Button browserResult = new Button(this);
        browserResult.setText("ブラウザ結果");
        browserResult.setOnClickListener(v -> refreshBrowserState(true));
        browserRow.addView(browserResult, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(browserRow);

        LinearLayout gitRow = new LinearLayout(this);
        Button gitPage = new Button(this);
        gitPage.setText("GitHub更新を見る");
        gitPage.setOnClickListener(v ->
                PixelBrowserController.openUrl(this, GitRuntimeUpdater.GITHUB_UPDATE_PAGE));
        gitRow.addView(gitPage, new LinearLayout.LayoutParams(0, -2, 1f));

        gitUpdateButton = new Button(this);
        gitUpdateButton.setText("Git完全更新");
        gitUpdateButton.setOnClickListener(v -> startGitRuntimeUpdate());
        gitRow.addView(gitUpdateButton, new LinearLayout.LayoutParams(0, -2, 1f));

        gitRollbackButton = new Button(this);
        gitRollbackButton.setText("前版へ戻す");
        gitRollbackButton.setOnClickListener(v -> startGitRollback());
        gitRow.addView(gitRollbackButton, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(gitRow);

        Button gitState = new Button(this);
        gitState.setText("Git更新状態");
        gitState.setOnClickListener(v -> {
            String stateText = GitRuntimeUpdater.currentState(this);
            chatLog.append(
                    "system",
                    "git-ota",
                    "Git OTA: " + stateText + " · " + engine.status());
            renderChatLog();
            status.setText("GIT OTA · " + stateText);
        });
        root.addView(gitState);

        LinearLayout agentRow = new LinearLayout(this);

        agentModeButton = new Button(this);
        refreshAgentModeButton();
        agentModeButton.setOnClickListener(v -> {
            agent.setAgentModeEnabled(!agent.isAgentModeEnabled());
            refreshAgentModeButton();
            renderChatLog();
            status.setText("AGENT · " + agent.stateSummary());
        });
        agentRow.addView(agentModeButton, new LinearLayout.LayoutParams(0, -2, 1f));

        Button agentState = new Button(this);
        agentState.setText("Agent状態");
        agentState.setOnClickListener(v -> {
            chatLog.append("system", "agent", agent.stateSummary());
            renderChatLog();
            status.setText("AGENT · " + agent.stateSummary());
        });
        agentRow.addView(agentState, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(agentRow);

        voiceButton = new Button(this);
        voiceButton.setText("音声会話開始");
        voiceButton.setOnClickListener(v -> toggleVoiceLoop());
        root.addView(voiceButton);

        output = new TextView(this);
        output.setTextIsSelectable(true);
        output.setPadding(0, 16, 0, 16);
        chatScroll = new ScrollView(this);
        chatScroll.addView(output, new ScrollView.LayoutParams(-1, -2));
        root.addView(chatScroll, new LinearLayout.LayoutParams(-1, 0, 1f));
        renderChatLog();

        LinearLayout feedback = new LinearLayout(this);
        Button ok = new Button(this); ok.setText("検証OK");
        Button ng = new Button(this); ng.setText("失敗");
        Button clear = new Button(this); clear.setText("履歴消去");
        ok.setOnClickListener(v -> verify(true));
        ng.setOnClickListener(v -> verify(false));
        clear.setOnClickListener(v -> {
            engine.clear();
            chatLog.clear();
            agent.resetDurableState();
            renderChatLog();
            status.setText(engine.status() + " · " + agent.stateSummary());
        });
        feedback.addView(ok, new LinearLayout.LayoutParams(0, -2, 1f));
        feedback.addView(ng, new LinearLayout.LayoutParams(0, -2, 1f));
        feedback.addView(clear, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(feedback);

        TextView note = new TextView(this);
        note.setText("Agent modeでは未処理Chatログを連番カーソルで追跡し、再起動後も未回答ターンを拾い直します。低確信時はChrome/ChatGPTへ1回だけ外部調査し、FAPで統合してログへ戻します。");
        root.addView(note);

        setContentView(root);

        voice = new AndroidVoiceController(this, new AndroidVoiceController.Listener() {
            @Override public void onStatus(String message) {
                status.setText(message + " · " + engine.status());
            }

            @Override public void onPartial(String text) {
                if (voiceLoop && text != null && !text.isEmpty()) {
                    status.setText("VOICE · " + text);
                }
            }

            @Override public void onFinal(String text, float confidence) {
                if (!voiceLoop) return;
                input.setText(text);
                runVoiceFap(text, confidence);
            }

            @Override public void onError(String message, boolean recoverable) {
                status.setText("VOICE ERROR · " + message + " · " + engine.status());
                if (voiceLoop && recoverable) {
                    mainHandler.postDelayed(() -> listenIfActive(), 450);
                } else if (!recoverable) {
                    stopVoiceLoop();
                }
            }
        });
        status.setText(
                engine.status()
                        + " · " + voice.capabilitySummary()
                        + " · OTA=" + GitRuntimeUpdater.currentState(this));
    }

    private void startGitRuntimeUpdate() {
        if (gitUpdateButton == null || !gitUpdateButton.isEnabled()) return;
        pauseVoiceForGitOperation();
        gitUpdateButton.setEnabled(false);
        gitRollbackButton.setEnabled(false);
        status.setText("GIT OTA · 完全更新を開始…");

        GitRuntimeUpdater.updateAsync(this, engine, new GitRuntimeUpdater.Listener() {
            @Override public void onStatus(String message) {
                status.setText("GIT OTA · " + message);
            }

            @Override public void onComplete(boolean success, String message) {
                gitUpdateButton.setEnabled(true);
                gitRollbackButton.setEnabled(true);
                status.setText(
                        (success ? "GIT OTA · OK · " : "GIT OTA · ERROR · ")
                                + message
                                + " · "
                                + engine.status());
                chatLog.append(
                        "system",
                        "git-ota",
                        message + " · " + GitRuntimeUpdater.currentState(MainActivity.this));
                renderChatLog();
                resumeVoiceAfterGitOperation();
                Toast.makeText(
                        MainActivity.this,
                        message,
                        success ? Toast.LENGTH_SHORT : Toast.LENGTH_LONG).show();
            }
        });
    }

    private void startGitRollback() {
        if (gitRollbackButton == null || !gitRollbackButton.isEnabled()) return;
        pauseVoiceForGitOperation();
        gitUpdateButton.setEnabled(false);
        gitRollbackButton.setEnabled(false);
        status.setText("GIT OTA · ロールバックを開始…");

        GitRuntimeUpdater.rollbackAsync(this, engine, new GitRuntimeUpdater.Listener() {
            @Override public void onStatus(String message) {
                status.setText("GIT OTA · " + message);
            }

            @Override public void onComplete(boolean success, String message) {
                gitUpdateButton.setEnabled(true);
                gitRollbackButton.setEnabled(true);
                status.setText(
                        (success ? "GIT OTA · OK · " : "GIT OTA · ERROR · ")
                                + message
                                + " · "
                                + engine.status());
                chatLog.append(
                        "system",
                        "git-ota",
                        message + " · " + GitRuntimeUpdater.currentState(MainActivity.this));
                renderChatLog();
                resumeVoiceAfterGitOperation();
                Toast.makeText(
                        MainActivity.this,
                        message,
                        success ? Toast.LENGTH_SHORT : Toast.LENGTH_LONG).show();
            }
        });
    }

    private void runFap() {
        String q = input.getText().toString().trim();
        if (q.isEmpty() || !run.isEnabled()) return;
        input.setText("");
        run.setEnabled(false);

        agent.submitUserTurn("text", q, new AgentOrchestrator.Listener() {
            @Override public void onStatus(String message) {
                renderChatLog();
                status.setText("AGENT · " + message + " · " + engine.status());
            }

            @Override public void onReply(PythonFapEngine.Result result, String channel) {
                last = result;
                renderChatLog();
                status.setText("AGENT · DONE · " + engine.status());
                run.setEnabled(true);
            }
        });
        renderChatLog();
    }

    private void runVoiceFap(String q, float sttConfidence) {
        if (q == null || q.trim().isEmpty()) {
            listenIfActive();
            return;
        }

        chatLog.append(
                "system",
                "voice-meta",
                "STT confidence=" + String.format("%.2f", sttConfidence));
        run.setEnabled(false);

        agent.submitUserTurn("voice", q.trim(), new AgentOrchestrator.Listener() {
            @Override public void onStatus(String message) {
                renderChatLog();
                status.setText("VOICE · AGENT · " + message);
            }

            @Override public void onReply(PythonFapEngine.Result result, String channel) {
                last = result;
                renderChatLog();
                run.setEnabled(true);
                if (!voiceLoop) {
                    status.setText(engine.status());
                    return;
                }
                status.setText("VOICE · SPEAKING · " + engine.status());
                voice.speak(result.answer, () -> listenIfActive());
            }
        });
        renderChatLog();
    }

    private void toggleVoiceLoop() {
        if (voiceLoop) {
            stopVoiceLoop();
        } else {
            startVoiceLoop();
        }
    }

    private void startVoiceLoop() {
        if (!voice.isRecognitionAvailable()) {
            Toast.makeText(this, "この端末では音声認識サービスを利用できません", Toast.LENGTH_LONG).show();
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_RECORD_AUDIO);
            return;
        }
        voiceLoop = true;
        voiceButton.setText("音声会話停止");
        listenIfActive();
    }

    private void stopVoiceLoop() {
        voiceLoop = false;
        if (voice != null) voice.stopAll();
        if (voiceButton != null) voiceButton.setText("音声会話開始");
        if (status != null) status.setText(engine.status());
    }

    private void listenIfActive() {
        if (!voiceLoop || voice == null) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            stopVoiceLoop();
            return;
        }
        voice.startListening();
    }

    @Override public void onRequestPermissionsResult(
            int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_RECORD_AUDIO) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            voiceLoop = true;
            voiceButton.setText("音声会話停止");
            listenIfActive();
        } else {
            stopVoiceLoop();
            Toast.makeText(this, "音声会話にはマイク権限が必要です", Toast.LENGTH_LONG).show();
        }
    }

    private void verify(boolean success) {
        if (last == null) return;
        engine.verify(last, success);
        status.setText(engine.status());
        Toast.makeText(this, success ? "検証成功として記録" : "失敗として記録", Toast.LENGTH_SHORT).show();
    }

    @Override protected void onPause() {
        super.onPause();
        if (voiceLoop && voice != null) {
            voice.stopListening();
        }
    }

    private void refreshBrowserState(boolean showResult) {
        String browserState = PixelBrowserController.state(this);
        if (PixelBrowserController.STATE_RESPONSE_READY.equals(browserState)) {
            if (showResult) renderChatLog();
            status.setText("PIXEL BROWSER · response_ready · " + agent.stateSummary());
        } else if (PixelBrowserController.STATE_ERROR.equals(browserState)) {
            status.setText(
                    "PIXEL BROWSER ERROR · "
                            + PixelBrowserController.lastError(this)
                            + " · "
                            + engine.status());
        } else if (!PixelBrowserController.STATE_IDLE.equals(browserState)) {
            status.setText("PIXEL BROWSER · " + browserState + " · " + engine.status());
        }
    }

    private void refreshAgentModeButton() {
        if (agentModeButton == null || agent == null) return;
        agentModeButton.setText(agent.isAgentModeEnabled() ? "Agent ON" : "Agent OFF");
    }

    private void renderChatLog() {
        if (output == null || chatLog == null) return;
        output.setText(chatLog.render(240));
        if (chatScroll != null) {
            chatScroll.post(() -> chatScroll.fullScroll(ScrollView.FOCUS_DOWN));
        }
    }

    private void pauseVoiceForGitOperation() {
        resumeVoiceAfterGit = voiceLoop;
        if (voiceLoop && voice != null) {
            voice.stopAll();
            voiceLoop = false;
            voiceButton.setText("音声会話開始");
        }
    }

    private void resumeVoiceAfterGitOperation() {
        if (!resumeVoiceAfterGit) return;
        resumeVoiceAfterGit = false;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED) {
            voiceLoop = true;
            voiceButton.setText("音声会話停止");
            mainHandler.postDelayed(() -> listenIfActive(), 350);
        }
    }

    @Override protected void onResume() {
        super.onResume();
        agent.reconcileAsync();
        renderChatLog();
        refreshAgentModeButton();
        refreshBrowserState(true);
        if (voiceLoop && voice != null) {
            mainHandler.postDelayed(() -> listenIfActive(), 250);
        }
    }

    @Override protected void onDestroy() {
        voiceLoop = false;
        mainHandler.removeCallbacksAndMessages(null);
        if (voice != null) voice.close();
        super.onDestroy();
    }
}
