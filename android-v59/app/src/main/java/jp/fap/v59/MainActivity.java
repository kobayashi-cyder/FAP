package jp.fap.v59;

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

    private PythonFapEngine engine;
    private AndroidVoiceController voice;
    private EditText input;
    private TextView output;
    private TextView status;
    private Button run;
    private Button voiceButton;
    private PythonFapEngine.Result last;
    private boolean voiceLoop = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        engine = new PythonFapEngine(this);

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

        voiceButton = new Button(this);
        voiceButton.setText("音声会話開始");
        voiceButton.setOnClickListener(v -> toggleVoiceLoop());
        root.addView(voiceButton);

        output = new TextView(this);
        output.setTextIsSelectable(true);
        output.setPadding(0, 16, 0, 16);
        root.addView(output, new LinearLayout.LayoutParams(-1, 0, 1f));

        LinearLayout feedback = new LinearLayout(this);
        Button ok = new Button(this); ok.setText("検証OK");
        Button ng = new Button(this); ng.setText("失敗");
        Button clear = new Button(this); clear.setText("履歴消去");
        ok.setOnClickListener(v -> verify(true));
        ng.setOnClickListener(v -> verify(false));
        clear.setOnClickListener(v -> {
            engine.clear();
            output.setText("");
            status.setText(engine.status());
        });
        feedback.addView(ok, new LinearLayout.LayoutParams(0, -2, 1f));
        feedback.addView(ng, new LinearLayout.LayoutParams(0, -2, 1f));
        feedback.addView(clear, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(feedback);

        TextView note = new TextView(this);
        note.setText("main更新時に最新Pythonコアとrelease sidecarをAPKへ封入。音声会話は端末能力を検出し、オンデバイスSTTを優先します。");
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
        status.setText(engine.status() + " · " + voice.capabilitySummary());
    }

    private void runFap() {
        String q = input.getText().toString().trim();
        if (q.isEmpty() || !run.isEnabled()) return;
        run.setEnabled(false);
        status.setText("THINKING · " + engine.status());

        new Thread(() -> {
            PythonFapEngine.Result result = engine.process(q);
            runOnUiThread(() -> {
                last = result;
                output.setText(result.answer + "\n\n[core] " + result.skill +
                        "\n[confidence] " + String.format("%.2f", result.confidence));
                status.setText(engine.status());
                run.setEnabled(true);
            });
        }, "fap-python").start();
    }

    private void runVoiceFap(String q, float sttConfidence) {
        if (q == null || q.trim().isEmpty()) {
            listenIfActive();
            return;
        }
        run.setEnabled(false);
        status.setText("VOICE · THINKING · " + engine.status());

        new Thread(() -> {
            PythonFapEngine.Result result = engine.process(q.trim());
            runOnUiThread(() -> {
                last = result;
                output.setText(result.answer + "\n\n[core] " + result.skill +
                        "\n[confidence] " + String.format("%.2f", result.confidence) +
                        "\n[stt-confidence] " + String.format("%.2f", sttConfidence));
                run.setEnabled(true);
                if (!voiceLoop) {
                    status.setText(engine.status());
                    return;
                }
                status.setText("VOICE · SPEAKING · " + engine.status());
                voice.speak(result.answer, () -> listenIfActive());
            });
        }, "fap-voice-python").start();
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

    @Override protected void onResume() {
        super.onResume();
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
