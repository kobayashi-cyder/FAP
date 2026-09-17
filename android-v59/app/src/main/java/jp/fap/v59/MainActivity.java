package jp.fap.v59;

import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.widget.*;

public class MainActivity extends Activity {
    private PythonFapEngine engine;
    private EditText input;
    private TextView output;
    private TextView status;
    private Button run;
    private PythonFapEngine.Result last;

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
        note.setText("main更新時に最新Pythonコアとrelease sidecarをAPKへ封入。検証済み結果だけ永続学習へ昇格します。");
        root.addView(note);

        setContentView(root);
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

    private void verify(boolean success) {
        if (last == null) return;
        engine.verify(last, success);
        status.setText(engine.status());
        Toast.makeText(this, success ? "検証成功として記録" : "失敗として記録", Toast.LENGTH_SHORT).show();
    }
}
