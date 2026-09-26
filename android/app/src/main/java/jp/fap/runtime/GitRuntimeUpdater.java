package jp.fap.runtime;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.AtomicFile;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Pattern;

public final class GitRuntimeUpdater {
    public interface Listener {
        void onStatus(String message);
        void onComplete(boolean success, String message);
    }

    public static final String MANIFEST_URL =
            "https://raw.githubusercontent.com/kobayashi-cyder/FAP/main/pixel_update/latest.json";
    public static final String GITHUB_UPDATE_PAGE =
            "https://github.com/kobayashi-cyder/FAP/tree/main/pixel_update";

    private static final String RAW_PREFIX =
            "https://raw.githubusercontent.com/kobayashi-cyder/FAP/";
    private static final String ACTIVE_FILE = "runtime_active.json";
    private static final String SLOT_MANIFEST = "slot_manifest.json";
    private static final String SCHEMA = "fap.pixel.runtime.manifest.v1";
    private static final int MAX_MANIFEST_BYTES = 512 * 1024;
    private static final int MAX_FILE_COUNT = 128;
    private static final long MAX_TOTAL_BYTES = 16L * 1024L * 1024L;
    private static final int MAX_SINGLE_FILE_BYTES = 2 * 1024 * 1024;
    private static final Pattern SHA40 = Pattern.compile("^[0-9a-f]{40}$");
    private static final Pattern SHA256 = Pattern.compile("^[0-9a-f]{64}$");
    private static final Pattern ROOT_PY =
            Pattern.compile("^fap_[A-Za-z0-9_]+\\.py$");
    private static final Pattern KNOWLEDGE =
            Pattern.compile("^knowledge/[A-Za-z0-9_./-]+\\.jsonl$");

    private static final ExecutorService EXECUTOR =
            Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "fap-git-runtime-updater");
                t.setDaemon(true);
                return t;
            });
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private GitRuntimeUpdater() {}

    public static void updateAsync(
            Context context,
            PythonFapEngine engine,
            Listener listener) {
        Context app = context.getApplicationContext();
        EXECUTOR.execute(() -> {
            try {
                updateBlocking(app, engine, listener);
            } catch (Throwable t) {
                complete(listener, false,
                        "Git完全更新に失敗: " + shortError(t));
            }
        });
    }

    public static void rollbackAsync(
            Context context,
            PythonFapEngine engine,
            Listener listener) {
        Context app = context.getApplicationContext();
        EXECUTOR.execute(() -> {
            try {
                rollbackBlocking(app, engine, listener);
            } catch (Throwable t) {
                complete(listener, false,
                        "ロールバックに失敗: " + shortError(t));
            }
        });
    }

    public static String currentState(Context context) {
        try {
            JSONObject active = readJson(new File(context.getFilesDir(), ACTIVE_FILE));
            if (active == null) return "packaged";
            String slot = active.optString("slot", "");
            String commit = active.optString("source_commit", "");
            String version = active.optString("runtime_version", "");
            if (!slot.equals("A") && !slot.equals("B")) return "packaged";
            return "slot=" + slot
                    + " version=" + version
                    + " commit=" + shortCommit(commit);
        } catch (Throwable ignored) {
            return "packaged";
        }
    }

    private static void updateBlocking(
            Context context,
            PythonFapEngine engine,
            Listener listener) throws Exception {
        emit(listener, "Git manifestを取得中…");
        byte[] manifestBytes = fetchBytes(MANIFEST_URL, MAX_MANIFEST_BYTES);
        JSONObject manifest = new JSONObject(
                new String(manifestBytes, StandardCharsets.UTF_8));
        validateManifest(manifest);

        String commit = manifest.getString("source_commit");
        String runtimeVersion = manifest.getString("runtime_version");
        JSONArray files = manifest.getJSONArray("files");
        long totalBytes = manifest.getLong("total_bytes");

        File filesDir = context.getFilesDir();
        File slotsRoot = new File(filesDir, "runtime_slots");
        if (!slotsRoot.exists() && !slotsRoot.mkdirs()) {
            throw new IllegalStateException("runtime_slotsを作成できません");
        }

        JSONObject previous = readJson(new File(filesDir, ACTIVE_FILE));
        String previousSlot = previous == null ? "" : previous.optString("slot", "");
        String targetSlot = "A".equals(previousSlot) ? "B" : "A";
        File target = new File(slotsRoot, targetSlot);
        deleteRecursively(target);
        if (!target.mkdirs()) {
            throw new IllegalStateException("更新スロットを作成できません: " + targetSlot);
        }

        long written = 0L;
        try {
            for (int i = 0; i < files.length(); i++) {
                JSONObject row = files.getJSONObject(i);
                String path = row.getString("path");
                String expectedSha = row.getString("sha256");
                int expectedBytes = row.getInt("bytes");

                emit(listener,
                        "完全更新 " + (i + 1) + "/" + files.length() + " · " + path);

                byte[] data = fetchBytes(
                        rawUrl(commit, path),
                        Math.min(MAX_SINGLE_FILE_BYTES, expectedBytes + 1));
                if (data.length != expectedBytes) {
                    throw new SecurityException(
                            "サイズ不一致: " + path
                                    + " expected=" + expectedBytes
                                    + " actual=" + data.length);
                }
                String actualSha = sha256(data);
                if (!expectedSha.equals(actualSha)) {
                    throw new SecurityException("SHA-256不一致: " + path);
                }

                File output = safeOutput(target, path);
                File parent = output.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IllegalStateException("ディレクトリ作成失敗: " + path);
                }
                try (FileOutputStream stream = new FileOutputStream(output)) {
                    stream.write(data);
                    stream.flush();
                    stream.getFD().sync();
                }
                written += data.length;
            }

            if (written != totalBytes) {
                throw new SecurityException(
                        "総バイト数不一致: expected=" + totalBytes + " actual=" + written);
            }

            File slotManifest = new File(target, SLOT_MANIFEST);
            writeAtomic(slotManifest, manifest.toString(2).getBytes(StandardCharsets.UTF_8));

            emit(listener, "Python構文・知識・起動スモークテスト中…");
            JSONObject validation = engine.validateRuntime(target.getAbsolutePath());
            if (!validation.optBoolean("ok", false)) {
                throw new IllegalStateException("候補ランタイム検証に失敗");
            }

            JSONObject next = new JSONObject();
            next.put("schema", "fap.pixel.runtime.active.v1");
            next.put("slot", targetSlot);
            next.put("runtime_version", runtimeVersion);
            next.put("source_commit", commit);
            next.put("file_count", files.length());
            next.put("total_bytes", written);
            next.put("activated_at", System.currentTimeMillis());

            File activeFile = new File(filesDir, ACTIVE_FILE);
            writeAtomic(activeFile, next.toString(2).getBytes(StandardCharsets.UTF_8));

            try {
                JSONObject reloaded = engine.reloadRuntime();
                String activeCommit = reloaded.optString("runtime_commit", "");
                if (!commit.equals(activeCommit)) {
                    throw new IllegalStateException("再ロード後のcommitが一致しません");
                }
            } catch (Throwable reloadFailure) {
                restoreActive(activeFile, previous);
                try {
                    engine.reloadRuntime();
                } catch (Throwable ignored) {
                }
                throw reloadFailure;
            }

            complete(listener, true,
                    "Git完全更新完了 · slot=" + targetSlot
                            + " · " + files.length() + " files"
                            + " · " + written + " bytes"
                            + " · " + shortCommit(commit));
        } catch (Throwable t) {
            deleteRecursively(target);
            throw t;
        }
    }

    private static void rollbackBlocking(
            Context context,
            PythonFapEngine engine,
            Listener listener) throws Exception {
        File filesDir = context.getFilesDir();
        File activeFile = new File(filesDir, ACTIVE_FILE);
        JSONObject current = readJson(activeFile);

        if (current == null) {
            throw new IllegalStateException("現在はAPK内蔵ランタイムです");
        }

        String currentSlot = current.optString("slot", "");
        String otherSlot = "A".equals(currentSlot) ? "B" : "A";
        File otherRoot = new File(new File(filesDir, "runtime_slots"), otherSlot);
        File otherManifestFile = new File(otherRoot, SLOT_MANIFEST);

        JSONObject previousState = current;
        if (!otherManifestFile.isFile()) {
            emit(listener, "旧スロットがないためAPK内蔵ランタイムへ戻します…");
            if (!activeFile.delete() && activeFile.exists()) {
                throw new IllegalStateException("active stateを削除できません");
            }
            try {
                engine.reloadRuntime();
            } catch (Throwable t) {
                writeAtomic(
                        activeFile,
                        previousState.toString(2).getBytes(StandardCharsets.UTF_8));
                try {
                    engine.reloadRuntime();
                } catch (Throwable ignored) {
                }
                throw t;
            }
            complete(listener, true, "APK内蔵ランタイムへロールバックしました");
            return;
        }

        JSONObject manifest = readJson(otherManifestFile);
        if (manifest == null) {
            throw new IllegalStateException("旧スロットmanifestが壊れています");
        }
        validateManifest(manifest);

        JSONObject next = new JSONObject();
        next.put("schema", "fap.pixel.runtime.active.v1");
        next.put("slot", otherSlot);
        next.put("runtime_version", manifest.getString("runtime_version"));
        next.put("source_commit", manifest.getString("source_commit"));
        next.put("file_count", manifest.getInt("file_count"));
        next.put("total_bytes", manifest.getLong("total_bytes"));
        next.put("activated_at", System.currentTimeMillis());

        emit(listener, "slot " + otherSlot + " へロールバック中…");
        writeAtomic(activeFile, next.toString(2).getBytes(StandardCharsets.UTF_8));
        try {
            engine.reloadRuntime();
        } catch (Throwable t) {
            writeAtomic(
                    activeFile,
                    previousState.toString(2).getBytes(StandardCharsets.UTF_8));
            try {
                engine.reloadRuntime();
            } catch (Throwable ignored) {
            }
            throw t;
        }

        complete(listener, true,
                "ロールバック完了 · slot=" + otherSlot
                        + " · " + shortCommit(next.optString("source_commit", "")));
    }

    private static void validateManifest(JSONObject manifest) throws Exception {
        if (!SCHEMA.equals(manifest.optString("schema", ""))) {
            throw new SecurityException("未知の更新manifest schema");
        }

        String commit = manifest.optString("source_commit", "").toLowerCase(Locale.ROOT);
        if (!SHA40.matcher(commit).matches()) {
            throw new SecurityException("source_commitが不正です");
        }

        if (!"fap_1x_standard_runtime.py".equals(
                manifest.optString("entrypoint", ""))) {
            throw new SecurityException("entrypointが不正です");
        }

        JSONArray files = manifest.optJSONArray("files");
        if (files == null || files.length() < 1 || files.length() > MAX_FILE_COUNT) {
            throw new SecurityException("file_countが範囲外です");
        }
        if (manifest.optInt("file_count", -1) != files.length()) {
            throw new SecurityException("file_countが一致しません");
        }

        long declaredTotal = manifest.optLong("total_bytes", -1L);
        if (declaredTotal < 1L || declaredTotal > MAX_TOTAL_BYTES) {
            throw new SecurityException("total_bytesが範囲外です");
        }

        long calculated = 0L;
        boolean hasEntrypoint = false;
        for (int i = 0; i < files.length(); i++) {
            JSONObject row = files.getJSONObject(i);
            String path = row.optString("path", "");
            if (!isAllowedPath(path)) {
                throw new SecurityException("更新対象外path: " + path);
            }
            String sha = row.optString("sha256", "").toLowerCase(Locale.ROOT);
            if (!SHA256.matcher(sha).matches()) {
                throw new SecurityException("SHA-256形式不正: " + path);
            }
            int bytes = row.optInt("bytes", -1);
            if (bytes < 1 || bytes > MAX_SINGLE_FILE_BYTES) {
                throw new SecurityException("ファイルサイズ範囲外: " + path);
            }
            calculated += bytes;
            if ("fap_1x_standard_runtime.py".equals(path)) {
                hasEntrypoint = true;
            }
        }
        if (!hasEntrypoint) {
            throw new SecurityException("entrypointがfilesに含まれていません");
        }
        if (calculated != declaredTotal) {
            throw new SecurityException("manifest total_bytes不一致");
        }
    }

    private static boolean isAllowedPath(String path) {
        if (path == null || path.isEmpty()) return false;
        if (path.startsWith("/") || path.contains("\\") || path.contains("..")) return false;
        return ROOT_PY.matcher(path).matches() || KNOWLEDGE.matcher(path).matches();
    }

    private static File safeOutput(File root, String relative) throws Exception {
        File output = new File(root, relative);
        String rootPath = root.getCanonicalPath() + File.separator;
        String outputPath = output.getCanonicalPath();
        if (!outputPath.startsWith(rootPath)) {
            throw new SecurityException("path traversal: " + relative);
        }
        return output;
    }

    private static String rawUrl(String commit, String path) {
        StringBuilder encoded = new StringBuilder();
        String[] parts = path.split("/");
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) encoded.append('/');
            encoded.append(parts[i]
                    .replace("%", "%25")
                    .replace(" ", "%20")
                    .replace("#", "%23")
                    .replace("?", "%3F"));
        }
        return RAW_PREFIX + commit + "/" + encoded;
    }

    private static byte[] fetchBytes(String urlText, int maxBytes) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(urlText).openConnection();
        connection.setInstanceFollowRedirects(true);
        connection.setConnectTimeout(15_000);
        connection.setReadTimeout(25_000);
        connection.setRequestProperty("User-Agent", "FAP-Pixel/1.0.01");
        connection.setRequestProperty("Accept", "application/octet-stream, application/json;q=0.9");

        try {
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new IllegalStateException("HTTP " + code + " for " + urlText);
            }
            int length = connection.getContentLength();
            if (length > maxBytes) {
                throw new SecurityException("download too large: " + length);
            }

            try (InputStream input = connection.getInputStream();
                 ByteArrayOutputStream output = new ByteArrayOutputStream(
                         Math.max(1024, Math.min(maxBytes, Math.max(0, length))))) {
                byte[] buffer = new byte[16 * 1024];
                int total = 0;
                while (true) {
                    int read = input.read(buffer);
                    if (read < 0) break;
                    total += read;
                    if (total > maxBytes) {
                        throw new SecurityException("download exceeded limit");
                    }
                    output.write(buffer, 0, read);
                }
                return output.toByteArray();
            }
        } finally {
            connection.disconnect();
        }
    }

    private static String sha256(byte[] data) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] value = digest.digest(data);
        StringBuilder out = new StringBuilder(value.length * 2);
        for (byte b : value) {
            out.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        }
        return out.toString();
    }

    private static JSONObject readJson(File file) {
        try {
            if (!file.isFile()) return null;
            byte[] data = java.nio.file.Files.readAllBytes(file.toPath());
            return new JSONObject(new String(data, StandardCharsets.UTF_8));
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static void writeAtomic(File file, byte[] data) throws Exception {
        File parent = file.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IllegalStateException("parent directory create failed");
        }

        AtomicFile atomic = new AtomicFile(file);
        FileOutputStream output = null;
        try {
            output = atomic.startWrite();
            output.write(data);
            output.flush();
            output.getFD().sync();
            atomic.finishWrite(output);
        } catch (Throwable t) {
            if (output != null) {
                atomic.failWrite(output);
            }
            throw t;
        }
    }

    private static void restoreActive(File activeFile, JSONObject previous) throws Exception {
        if (previous == null) {
            if (activeFile.exists() && !activeFile.delete()) {
                throw new IllegalStateException("failed to restore packaged runtime");
            }
            return;
        }
        writeAtomic(
                activeFile,
                previous.toString(2).getBytes(StandardCharsets.UTF_8));
    }

    private static void deleteRecursively(File file) {
        if (file == null || !file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteRecursively(child);
                }
            }
        }
        //noinspection ResultOfMethodCallIgnored
        file.delete();
    }

    private static String shortCommit(String commit) {
        if (commit == null) return "unknown";
        return commit.length() <= 10 ? commit : commit.substring(0, 10);
    }

    private static String shortError(Throwable t) {
        String message = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage());
        return message.length() <= 220 ? message : message.substring(0, 220);
    }

    private static void emit(Listener listener, String message) {
        if (listener == null) return;
        MAIN.post(() -> listener.onStatus(message));
    }

    private static void complete(Listener listener, boolean success, String message) {
        if (listener == null) return;
        MAIN.post(() -> listener.onComplete(success, message));
    }
}
