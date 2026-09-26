package jp.fap.runtime;

import android.content.Context;
import android.speech.SpeechRecognizer;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public final class FapToolRegistry {
    private static final Map<String, ExternalToolAdapter> EXTERNAL =
            new ConcurrentHashMap<>();

    public static final class ToolState {
        public final String id;
        public final String title;
        public final boolean available;
        public final String detail;

        ToolState(String id, String title, boolean available, String detail) {
            this.id = id;
            this.title = title;
            this.available = available;
            this.detail = detail;
        }
    }

    private FapToolRegistry() {}

    public static void registerExternal(ExternalToolAdapter adapter) {
        if (adapter == null || adapter.id() == null || adapter.id().trim().isEmpty()) return;
        EXTERNAL.put(adapter.id().trim(), adapter);
    }

    public static void unregisterExternal(String id) {
        if (id == null) return;
        EXTERNAL.remove(id.trim());
    }

    public static ExternalToolAdapter external(String id) {
        if (id == null) return null;
        return EXTERNAL.get(id.trim());
    }

    public static int connectedExternalCount(Context context) {
        int count = 0;
        for (ExternalToolAdapter adapter : EXTERNAL.values()) {
            try {
                if (adapter != null && adapter.isConnected(context)) count++;
            } catch (Throwable ignored) {
            }
        }
        return count;
    }

    public static List<ToolState> snapshot(Context context) {
        ArrayList<ToolState> out = new ArrayList<>();
        boolean accessibility = context != null
                && PixelBrowserController.isAccessibilityEnabled(context);
        boolean connected = PixelBrowserAccessibilityService.isConnected();
        boolean screen = context != null && ScreenTeachController.isSharing(context);
        boolean control = context != null && ScreenTeachController.isControlEnabled(context);
        boolean voice = context != null && SpeechRecognizer.isRecognitionAvailable(context);

        out.add(new ToolState(
                "local_reasoning",
                "FAP Core",
                true,
                "connectome runtime / semantic memory / FAP思考"));
        out.add(new ToolState(
                "web_research",
                "外部調査",
                accessibility,
                accessibility
                        ? "Chrome/ChatGPT委譲 + FAP統合"
                        : "ユーザー補助サービスを有効化してください"));
        out.add(new ToolState(
                "device_control",
                "端末操作",
                accessibility && connected && control,
                "tap / drag / text / enter · control="
                        + (control ? "ON" : "OFF")));
        out.add(new ToolState(
                "screen_context",
                "画面共有",
                screen,
                screen ? "MediaProjection rolling frames" : "画面共有OFF"));
        out.add(new ToolState(
                "voice",
                "音声",
                voice,
                voice ? "STT/TTS + barge-in" : "音声認識を利用できません"));
        out.add(new ToolState(
                "files",
                "ファイル",
                true,
                "複数添付 / PDF本文+OCR / Office / archive / APK"));
        out.add(new ToolState(
                "vision",
                "画像理解",
                true,
                "日本語OCR + on-device image labels"));
        out.add(new ToolState(
                "tables",
                "表データ",
                true,
                "CSV/TSV統計プロファイル + XLSX抽出"));
        out.add(new ToolState(
                "git_ota",
                "Git runtime OTA",
                true,
                "A/B slot update + rollback"));
        out.add(new ToolState(
                "apk_update",
                "APK更新",
                true,
                "GitHub Release manifest + signer/SHA検証"));
        out.add(new ToolState(
                "chat_archive",
                "記録庫",
                true,
                "複数会話保存 / 全文検索 / 横枝スナップショット"));
        int externalConnected = connectedExternalCount(context);
        out.add(new ToolState(
                "external_connectors",
                "外部接続",
                externalConnected > 0,
                externalConnected > 0
                        ? "接続済みadapter=" + externalConnected
                        : "OAuth/API認証用adapter slot。接続先の資格情報が必要"));
        return out;
    }

    public static String describe(Context context) {
        StringBuilder out = new StringBuilder();
        for (ToolState tool : snapshot(context)) {
            if (out.length() > 0) out.append("\n");
            out.append(tool.available ? "✓ " : "○ ")
                    .append(tool.title)
                    .append(" · ")
                    .append(tool.detail);
        }
        return out.toString();
    }
}
