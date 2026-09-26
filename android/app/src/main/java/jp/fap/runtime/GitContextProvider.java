package jp.fap.runtime;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class GitContextProvider {
    private static final String PREFS = "fap_git_context";
    private static final String KEY_LAST_CHECK = "last_check";
    private static final String KEY_LAST_DIGEST = "last_digest";
    private static final long DEFAULT_INTERVAL_MS = 15L * 60L * 1000L;
    private static final int MAX_BYTES = 768 * 1024;

    private static final String MAIN_COMMIT_URL =
            "https://api.github.com/repos/kobayashi-cyder/FAP/commits/main";

    private static final ExecutorService EXECUTOR =
            Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "fap-git-context");
                t.setDaemon(true);
                return t;
            });

    private GitContextProvider() {}

    public static void refreshIfDueAsync(Context context, ChatLogStore log) {
        refreshAsync(context, log, false);
    }

    public static void forceRefreshAsync(Context context, ChatLogStore log) {
        refreshAsync(context, log, true);
    }

    private static void refreshAsync(
            Context context,
            ChatLogStore log,
            boolean force) {
        Context app = context.getApplicationContext();
        SharedPreferences prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long now = System.currentTimeMillis();
        long last = prefs.getLong(KEY_LAST_CHECK, 0L);
        if (!force && now - last < DEFAULT_INTERVAL_MS) return;

        // Claim this interval before networking so the 3-second agent heartbeat
        // cannot fan out duplicate GitHub requests.
        prefs.edit().putLong(KEY_LAST_CHECK, now).apply();

        EXECUTOR.execute(() -> {
            try {
                JSONObject commit = fetchJson(MAIN_COMMIT_URL);
                JSONObject manifest = fetchJson(GitRuntimeUpdater.MANIFEST_URL);

                String mainSha = commit.optString("sha", "");
                String commitMessage = firstLine(
                        commit.optJSONObject("commit") == null
                                ? ""
                                : commit.optJSONObject("commit").optString("message", ""));
                String manifestSha = manifest.optString("source_commit", "");
                String runtimeVersion = manifest.optString("runtime_version", "?");
                int fileCount = manifest.optInt("file_count", 0);
                long totalBytes = manifest.optLong("total_bytes", 0L);
                String local = GitRuntimeUpdater.currentState(app);

                ArrayList<String> changed = new ArrayList<>();
                JSONArray files = commit.optJSONArray("files");
                if (files != null) {
                    for (int i = 0; i < files.length() && changed.size() < 8; i++) {
                        JSONObject row = files.optJSONObject(i);
                        if (row == null) continue;
                        String name = row.optString("filename", "").trim();
                        if (!name.isEmpty()) changed.add(name);
                    }
                }

                String relation;
                if (!mainSha.isEmpty() && mainSha.equals(manifestSha)) {
                    relation = "manifest=main同期";
                } else if (!mainSha.isEmpty() && !manifestSha.isEmpty()) {
                    relation = "manifestはmain先頭より前";
                } else {
                    relation = "Git状態不明";
                }

                String summary =
                        "Git補足\n"
                                + "main=" + shortSha(mainSha)
                                + (commitMessage.isEmpty() ? "" : " · " + commitMessage)
                                + "\nmanifest=" + shortSha(manifestSha)
                                + " · runtime=" + runtimeVersion
                                + " · files=" + fileCount
                                + " · bytes=" + totalBytes
                                + "\nlocal=" + local
                                + "\n状態=" + relation
                                + (changed.isEmpty()
                                    ? ""
                                    : "\nmain最新commit変更: " + String.join(", ", changed));

                String digest = sha256(summary);
                String previous = prefs.getString(KEY_LAST_DIGEST, "");
                if (force || !digest.equals(previous)) {
                    log.appendBack("system", "git-context", summary);
                    prefs.edit().putString(KEY_LAST_DIGEST, digest).apply();
                }
            } catch (Throwable t) {
                String summary = "Git補足取得失敗 · "
                        + t.getClass().getSimpleName()
                        + ": "
                        + safeMessage(t);
                String digest = sha256(summary);
                String previous = prefs.getString(KEY_LAST_DIGEST, "");
                if (force || !digest.equals(previous)) {
                    log.appendBack("system", "git-context", summary);
                    prefs.edit().putString(KEY_LAST_DIGEST, digest).apply();
                }
            }
        });
    }

    private static JSONObject fetchJson(String urlText) throws Exception {
        HttpURLConnection connection =
                (HttpURLConnection) new URL(urlText).openConnection();
        connection.setConnectTimeout(12_000);
        connection.setReadTimeout(18_000);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("User-Agent", "FAP-Pixel/1.0.01");
        connection.setRequestProperty(
                "Accept",
                "application/vnd.github+json, application/json;q=0.9");
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");

        try {
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new IllegalStateException("HTTP " + code);
            }
            int declared = connection.getContentLength();
            if (declared > MAX_BYTES) {
                throw new IllegalStateException("Git response too large");
            }
            try (InputStream input = connection.getInputStream();
                 ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[16 * 1024];
                int total = 0;
                while (true) {
                    int read = input.read(buffer);
                    if (read < 0) break;
                    total += read;
                    if (total > MAX_BYTES) {
                        throw new IllegalStateException("Git response exceeded limit");
                    }
                    output.write(buffer, 0, read);
                }
                return new JSONObject(
                        output.toString(StandardCharsets.UTF_8.name()));
            }
        } finally {
            connection.disconnect();
        }
    }

    private static String firstLine(String value) {
        String text = value == null ? "" : value.trim();
        int newline = text.indexOf('\n');
        return newline >= 0 ? text.substring(0, newline).trim() : text;
    }

    private static String shortSha(String sha) {
        String value = sha == null ? "" : sha.trim();
        if (value.isEmpty()) return "unknown";
        return value.substring(0, Math.min(10, value.length()));
    }

    private static String safeMessage(Throwable t) {
        String value = String.valueOf(t.getMessage());
        if (value.length() > 160) return value.substring(0, 160);
        return value;
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] data = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder();
            for (byte b : data) {
                out.append(String.format(Locale.ROOT, "%02x", b & 0xff));
            }
            return out.toString();
        } catch (Throwable ignored) {
            return value;
        }
    }
}
