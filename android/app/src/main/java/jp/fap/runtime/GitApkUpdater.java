package jp.fap.runtime;

import android.content.Context;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

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

public final class GitApkUpdater {
    public interface Listener {
        void onStatus(String message);
        void onReadyToInstall(File apk, JSONObject manifest);
        void onError(String message);
    }

    public static final String MANIFEST_URL =
            "https://github.com/kobayashi-cyder/FAP/releases/latest/download/latest-apk.json";
    public static final String FALLBACK_MANIFEST_URL =
            "https://raw.githubusercontent.com/kobayashi-cyder/FAP/main/pixel_update/apk/latest.json";

    private static final long MAX_APK_BYTES = 256L * 1024L * 1024L;
    private static final int MAX_MANIFEST_BYTES = 256 * 1024;
    private static final Pattern SHA256 = Pattern.compile("^[0-9a-f]{64}$");

    private static final ExecutorService EXECUTOR =
            Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "fap-git-apk-updater");
                t.setDaemon(true);
                return t;
            });

    private GitApkUpdater() {}

    public static void checkAndDownloadAsync(
            Context context,
            Listener listener) {
        Context app = context.getApplicationContext();
        EXECUTOR.execute(() -> {
            try {
                if (!app.getPackageManager().canRequestPackageInstalls()) {
                    listener.onStatus("APK更新には『この提供元を許可』が必要です");
                }

                listener.onStatus("Git APK manifestを取得中…");
                JSONObject manifest;
                try {
                    manifest = new JSONObject(
                            new String(
                                    fetchBytes(MANIFEST_URL, MAX_MANIFEST_BYTES),
                                    StandardCharsets.UTF_8));
                } catch (Throwable releaseManifestFailure) {
                    listener.onStatus("Release manifest未公開 · repo manifestへフォールバック");
                    manifest = new JSONObject(
                            new String(
                                    fetchBytes(FALLBACK_MANIFEST_URL, MAX_MANIFEST_BYTES),
                                    StandardCharsets.UTF_8));
                }

                validateManifest(manifest, app);
                int remoteVersion = manifest.getInt("version_code");
                PackageInfo current = app.getPackageManager().getPackageInfo(
                        app.getPackageName(),
                        PackageManager.GET_SIGNING_CERTIFICATES);
                long currentVersion = Build.VERSION.SDK_INT >= 28
                        ? current.getLongVersionCode()
                        : current.versionCode;

                if (remoteVersion <= currentVersion) {
                    listener.onStatus(
                            "APKは最新です · current=" + currentVersion
                                    + " remote=" + remoteVersion);
                    return;
                }

                String url = manifest.getString("apk_url");
                listener.onStatus("APKをGitHubから取得中…");

                byte[] apkBytes = fetchBytes(url, (int) Math.min(
                        Integer.MAX_VALUE,
                        manifest.optLong("bytes", MAX_APK_BYTES) + 1));
                long expectedBytes = manifest.optLong("bytes", -1L);
                if (expectedBytes > 0 && apkBytes.length != expectedBytes) {
                    throw new SecurityException("APKサイズ不一致");
                }

                String actualSha = sha256(apkBytes);
                String expectedSha = manifest.getString("sha256").toLowerCase(Locale.ROOT);
                if (!actualSha.equals(expectedSha)) {
                    throw new SecurityException("APK SHA-256不一致");
                }

                File dir = new File(app.getCacheDir(), "apk-update");
                if (!dir.exists() && !dir.mkdirs()) {
                    throw new IllegalStateException("APK更新ディレクトリを作成できません");
                }
                File apk = new File(dir, "FAP-Pixel-update.apk");
                try (FileOutputStream out = new FileOutputStream(apk)) {
                    out.write(apkBytes);
                    out.flush();
                    out.getFD().sync();
                }

                verifyArchive(app, apk, manifest);
                listener.onReadyToInstall(apk, manifest);
            } catch (Throwable t) {
                listener.onError(shortError(t));
            }
        });
    }

    public static void requestUnknownSourcesPermission(Context context) {
        Intent intent = new Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:" + context.getPackageName()));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    public static void launchInstaller(Context context, File apk) throws Exception {
        PackageInstaller installer = context.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams params =
                new PackageInstaller.SessionParams(
                        PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(context.getPackageName());
        params.setSize(apk.length());

        int sessionId = installer.createSession(params);
        PackageInstaller.Session session = installer.openSession(sessionId);
        try (InputStream input = new java.io.FileInputStream(apk);
             java.io.OutputStream output = session.openWrite(
                     "FAP-Pixel.apk",
                     0,
                     apk.length())) {
            byte[] buffer = new byte[32 * 1024];
            long written = 0L;
            while (true) {
                int read = input.read(buffer);
                if (read < 0) break;
                output.write(buffer, 0, read);
                written += read;
                session.setStagingProgress(
                        apk.length() <= 0 ? 0f : (float) written / (float) apk.length());
            }
            session.fsync(output);
        }

        Intent callback = new Intent(context, ApkInstallResultReceiver.class);
        callback.setAction(ApkInstallResultReceiver.ACTION_INSTALL_STATUS);
        callback.putExtra("session_id", sessionId);
        PendingIntent pending = PendingIntent.getBroadcast(
                context,
                sessionId,
                callback,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE);
        session.commit(pending.getIntentSender());
        session.close();
    }

    private static void validateManifest(JSONObject manifest, Context context) throws Exception {
        if (!"fap.pixel.apk.manifest.v1".equals(manifest.optString("schema", ""))) {
            throw new SecurityException("未知のAPK manifest schema");
        }
        if (!context.getPackageName().equals(manifest.optString("package_name", ""))) {
            throw new SecurityException("APK package_name不一致");
        }
        if (!manifest.optBoolean("available", false)) {
            throw new IllegalStateException("Git APK更新はまだ公開されていません");
        }

        String sha = manifest.optString("sha256", "").toLowerCase(Locale.ROOT);
        if (!SHA256.matcher(sha).matches()) {
            throw new SecurityException("APK SHA-256形式不正");
        }

        String url = manifest.optString("apk_url", "");
        URL parsed = new URL(url);
        String host = parsed.getHost().toLowerCase(Locale.ROOT);
        if (!isAllowedGitHubHost(host) || !"https".equalsIgnoreCase(parsed.getProtocol())) {
            throw new SecurityException("APK URLはGitHub HTTPSに限定されています");
        }

        long bytes = manifest.optLong("bytes", -1L);
        if (bytes < 1L || bytes > MAX_APK_BYTES) {
            throw new SecurityException("APKサイズが範囲外です");
        }
        if (manifest.optInt("version_code", -1) < 1) {
            throw new SecurityException("version_code不正");
        }
    }

    private static void verifyArchive(
            Context context,
            File apk,
            JSONObject manifest) throws Exception {
        PackageManager pm = context.getPackageManager();
        PackageInfo archive = pm.getPackageArchiveInfo(
                apk.getAbsolutePath(),
                PackageManager.GET_SIGNING_CERTIFICATES);
        if (archive == null) throw new SecurityException("APK解析失敗");
        if (!context.getPackageName().equals(archive.packageName)) {
            throw new SecurityException("APK package署名対象がFAPではありません");
        }

        long remoteVersion = Build.VERSION.SDK_INT >= 28
                ? archive.getLongVersionCode()
                : archive.versionCode;
        if (remoteVersion != manifest.getInt("version_code")) {
            throw new SecurityException("APK versionCodeがmanifestと不一致");
        }

        PackageInfo installed = pm.getPackageInfo(
                context.getPackageName(),
                PackageManager.GET_SIGNING_CERTIFICATES);

        String installedSigner = signerDigest(installed);
        String archiveSigner = signerDigest(archive);
        if (installedSigner.isEmpty() || !installedSigner.equals(archiveSigner)) {
            throw new SecurityException("APK署名が現在のFAPと一致しません");
        }

        String expectedSigner = manifest.optString("signer_sha256", "").trim().toLowerCase(Locale.ROOT);
        if (!expectedSigner.isEmpty() && !expectedSigner.equals(archiveSigner)) {
            throw new SecurityException("APK signer SHA-256がmanifestと不一致");
        }
    }

    private static String signerDigest(PackageInfo info) throws Exception {
        if (info == null || info.signingInfo == null) return "";
        Signature[] signatures = info.signingInfo.hasMultipleSigners()
                ? info.signingInfo.getApkContentsSigners()
                : info.signingInfo.getSigningCertificateHistory();
        if (signatures == null || signatures.length == 0) return "";
        return sha256(signatures[0].toByteArray());
    }

    private static boolean isAllowedGitHubHost(String host) {
        return host.equals("github.com")
                || host.equals("raw.githubusercontent.com")
                || host.endsWith(".githubusercontent.com")
                || host.endsWith(".github.com");
    }

    private static byte[] fetchBytes(String urlText, int maxBytes) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(urlText).openConnection();
        connection.setConnectTimeout(15_000);
        connection.setReadTimeout(40_000);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("User-Agent", "FAP-Pixel/1.0.01");
        try {
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new IllegalStateException("HTTP " + code);
            }
            try (InputStream input = connection.getInputStream();
                 ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[32 * 1024];
                int total = 0;
                while (true) {
                    int read = input.read(buffer);
                    if (read < 0) break;
                    total += read;
                    if (total > maxBytes) throw new SecurityException("download too large");
                    out.write(buffer, 0, read);
                }
                return out.toByteArray();
            }
        } finally {
            connection.disconnect();
        }
    }

    private static String sha256(byte[] data) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] value = digest.digest(data);
        StringBuilder out = new StringBuilder(value.length * 2);
        for (byte b : value) out.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return out.toString();
    }

    private static String shortError(Throwable t) {
        String value = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage());
        return value.length() <= 220 ? value : value.substring(0, 220);
    }
}
