package jp.fap.runtime;

import android.Manifest;
import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.widget.*;

public class MainActivity extends Activity {
    private static final int REQ_RECORD_AUDIO = 601;
    private static final int REQ_MEDIA_PROJECTION = 710;
    private static final int REQ_OPEN_DOCUMENT = 711;

    private PythonFapEngine engine;
    private AndroidVoiceController voice;
    private EditText input;
    private TextView output;
    private TextView status;
    private TextView permissionStatus;
    private Button run;
    private Button voiceButton;
    private PythonFapEngine.Result last;
    private boolean voiceLoop = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        engine = new PythonFapEngine(this);

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(28, 28, 28, 28);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("FAP Android · Live Python Core");
        title.setTextSize(22f);
        root.addView(title);

        status = new TextView(this);
        status.setText(engine.status());
        root.addView(status);

        permissionStatus = new TextView(this);
        permissionStatus.setPadding(0, 10, 0, 10);
        root.addView(permissionStatus);

        LinearLayout permissionRow = new LinearLayout(this);
        permissionRow.setOrientation(LinearLayout.HORIZONTAL);

        Button accessibility = new Button(this);
        accessibility.setText("操作権限");
        accessibility.setOnClickListener(v -> openAccessibilitySettings());

        Button overlay = new Button(this);
        overlay.setText("重ねて表示");
        overlay.setOnClickListener(v -> requestOverlayPermission());

        Button share = new Button(this);
        share.setText("画面共有");
        share.setOnClickListener(v -> requestScreenCapture());

        permissionRow.addView(accessibility, new LinearLayout.LayoutParams(0, -2, 1f));
        permissionRow.addView(overlay, new LinearLayout.LayoutParams(0, -2, 1f));
        permissionRow.addView(share, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(permissionRow);

        Button file = new Button(this);
        file.setText("ファイルを開く（全形式）");
        file.setOnClickListener(v -> openDocument());
        root.addView(file);

        input = new EditText(this);
        input.setHint("質問・命令を入力");
        input.setMinLines(3);
        input.setGravity(Gravity.TOP);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        root.addView(input, new LinearLayout.LayoutParams(-1, 420));

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
        root.addView(output, new LinearLayout.LayoutParams(-1, 560));

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
        note.setText("操作権限=アクセシビリティ、画面共有=AndroidのMediaProjection確認、重ねて表示=特別なアクセスです。これらは通常の「アプリの権限」一覧にはマイクと同じ形では表示されません。");
        root.addView(note);

        setContentView(scroll);

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
        refreshPermissionStatus();
    }

    private void refreshPermissionStatus() {
        boolean mic = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
        boolean overlay = Settings.canDrawOverlays(this);
        boolean a11y = isAccessibilityServiceEnabled();
        permissionStatus.setText(
                "権限状態 · mic=" + yesNo(mic) +
                " · accessibility=" + yesNo(a11y) +
                " · overlay=" + yesNo(overlay) +
                " · screen=" + yesNo(ScreenCaptureService.isRunning())
        );
    }

    private String yesNo(boolean value) {
        return value ? "ON" : "OFF";
    }

    private boolean isAccessibilityServiceEnabled() {
        String enabled = Settings.Secure.getString(
                getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        if (enabled == null) return false;
        ComponentName mine = new ComponentName(this, FapAccessibilityService.class);
        String flat = mine.flattenToString();
        for (String value : enabled.split(":")) {
            if (flat.equalsIgnoreCase(value)) return true;
        }
        return false;
    }

    private void openAccessibilitySettings() {
        startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
    }

    private void requestOverlayPermission() {
        if (Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "重ねて表示は許可済みです", Toast.LENGTH_SHORT).show();
            return;
        }
        Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName()));
        startActivity(intent);
    }

    private void requestScreenCapture() {
        MediaProjectionManager manager =
                (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        startActivityForResult(manager.createScreenCaptureIntent(), REQ_MEDIA_PROJECTION);
    }

    private void openDocument() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION |
                Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, REQ_OPEN_DOCUMENT);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == REQ_MEDIA_PROJECTION) {
            if (resultCode != RESULT_OK || data == null) {
                Toast.makeText(this, "画面共有は許可されませんでした", Toast.LENGTH_SHORT).show();
                refreshPermissionStatus();
                return;
            }
            Intent service = ScreenCaptureService.startIntent(this, resultCode, data);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(service);
            } else {
                startService(service);
            }
            mainHandler.postDelayed(this::refreshPermissionStatus, 500);
            return;
        }

        if (requestCode == REQ_OPEN_DOCUMENT && resultCode == RESULT_OK && data != null) {
            Uri uri = data.getData();
            if (uri != null) {
                try {
                    getContentResolver().takePersistableUriPermission(
                            uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
                } catch (SecurityException ignored) {
                    // Some providers grant a temporary URI only.
                }
                input.setText(uri.toString());
                Toast.makeText(this, "ファイルURIを取得しました", Toast.LENGTH_SHORT).show();
            }
        }
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
                voice.speak(result.answer, this::listenIfActive);
            });
        }, "fap-voice-python").start();
    }

    private void toggleVoiceLoop() {
        if (voiceLoop) stopVoiceLoop();
        else startVoiceLoop();
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
        refreshPermissionStatus();
    }

    private void verify(boolean success) {
        if (last == null) return;
        engine.verify(last, success);
        status.setText(engine.status());
        Toast.makeText(this, success ? "検証成功として記録" : "失敗として記録", Toast.LENGTH_SHORT).show();
    }

    @Override protected void onPause() {
        super.onPause();
        if (voiceLoop && voice != null) voice.stopListening();
    }

    @Override protected void onResume() {
        super.onResume();
        refreshPermissionStatus();
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
}
