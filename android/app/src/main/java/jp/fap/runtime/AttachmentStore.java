package jp.fap.runtime;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

public final class AttachmentStore {
    private static final long MAX_FILE_BYTES = 512L * 1024L * 1024L;
    private static final int MAX_TEXT_PREVIEW_BYTES = 256 * 1024;

    public static final class Attachment {
        public final String id;
        public final String name;
        public final String mime;
        public final long bytes;
        public final String sha256;
        public final String localPath;
        public final String preview;

        Attachment(
                String id,
                String name,
                String mime,
                long bytes,
                String sha256,
                String localPath,
                String preview) {
            this.id = id;
            this.name = name;
            this.mime = mime;
            this.bytes = bytes;
            this.sha256 = sha256;
            this.localPath = localPath;
            this.preview = preview;
        }

        public JSONObject toJson() throws Exception {
            JSONObject o = new JSONObject();
            o.put("id", id);
            o.put("name", name);
            o.put("mime", mime);
            o.put("bytes", bytes);
            o.put("sha256", sha256);
            o.put("local_path", localPath);
            o.put("preview", preview);
            return o;
        }

        public String compactDescription() {
            return "📎 " + name
                    + " · " + mime
                    + " · " + humanBytes(bytes)
                    + " · sha256=" + shortSha(sha256)
                    + (preview.isEmpty() ? "" : "\n" + preview);
        }
    }

    private final Context app;
    private final File root;

    public AttachmentStore(Context context) {
        app = context.getApplicationContext();
        root = new File(app.getFilesDir(), "attachments");
        if (!root.exists()) root.mkdirs();
    }

    public Attachment importUri(Uri uri) throws Exception {
        if (uri == null) throw new IllegalArgumentException("uri is null");

        ContentResolver resolver = app.getContentResolver();
        String name = queryName(resolver, uri);
        String mime = resolver.getType(uri);
        if (mime == null || mime.trim().isEmpty()) mime = "application/octet-stream";

        String id = UUID.randomUUID().toString();
        String safe = sanitizeName(name.isEmpty() ? "attachment.bin" : name);
        File dir = new File(root, id);
        if (!dir.mkdirs()) throw new IllegalStateException("attachment directory create failed");
        File output = new File(dir, safe);

        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long total = 0L;
        try (InputStream input = resolver.openInputStream(uri);
             FileOutputStream stream = new FileOutputStream(output)) {
            if (input == null) throw new IllegalStateException("content stream unavailable");
            byte[] buffer = new byte[32 * 1024];
            while (true) {
                int read = input.read(buffer);
                if (read < 0) break;
                total += read;
                if (total > MAX_FILE_BYTES) {
                    throw new IllegalArgumentException("attachment exceeds 512 MiB limit");
                }
                digest.update(buffer, 0, read);
                stream.write(buffer, 0, read);
            }
            stream.flush();
            stream.getFD().sync();
        } catch (Throwable t) {
            deleteRecursively(dir);
            throw t;
        }

        String sha = hex(digest.digest());
        String preview = isTextLike(mime, safe)
                ? readTextPreview(output)
                : "";

        Attachment attachment = new Attachment(
                id,
                safe,
                mime,
                total,
                sha,
                output.getAbsolutePath(),
                preview);

        File meta = new File(dir, "meta.json");
        try (FileOutputStream stream = new FileOutputStream(meta)) {
            stream.write((attachment.toJson().toString(2) + "\n")
                    .getBytes(StandardCharsets.UTF_8));
            stream.flush();
            stream.getFD().sync();
        }
        return attachment;
    }

    public static String toJson(List<Attachment> attachments) {
        JSONArray array = new JSONArray();
        if (attachments != null) {
            for (Attachment attachment : attachments) {
                try {
                    array.put(attachment.toJson());
                } catch (Throwable ignored) {
                }
            }
        }
        return array.toString();
    }

    public static String describe(List<Attachment> attachments) {
        if (attachments == null || attachments.isEmpty()) return "";
        StringBuilder out = new StringBuilder();
        for (Attachment attachment : attachments) {
            if (out.length() > 0) out.append("\n\n");
            out.append(attachment.compactDescription());
        }
        return out.toString();
    }

    private static String queryName(ContentResolver resolver, Uri uri) {
        try (Cursor cursor = resolver.query(
                uri,
                new String[]{OpenableColumns.DISPLAY_NAME},
                null,
                null,
                null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) {
                    String value = cursor.getString(index);
                    if (value != null) return value.trim();
                }
            }
        } catch (Throwable ignored) {
        }
        String last = uri.getLastPathSegment();
        return last == null ? "" : last;
    }

    private static boolean isTextLike(String mime, String name) {
        String m = mime == null ? "" : mime.toLowerCase(Locale.ROOT);
        String n = name == null ? "" : name.toLowerCase(Locale.ROOT);
        if (m.startsWith("text/")) return true;
        if (m.contains("json") || m.contains("xml") || m.contains("javascript")
                || m.contains("yaml") || m.contains("csv")) return true;
        String[] suffixes = {
                ".txt", ".md", ".markdown", ".json", ".jsonl", ".csv", ".tsv",
                ".xml", ".html", ".htm", ".css", ".js", ".mjs", ".cjs",
                ".py", ".java", ".kt", ".kts", ".c", ".h", ".cc", ".cpp",
                ".hpp", ".rs", ".go", ".sh", ".ps1", ".bat", ".cmd", ".ini",
                ".cfg", ".conf", ".toml", ".yaml", ".yml", ".sql", ".log"
        };
        for (String suffix : suffixes) if (n.endsWith(suffix)) return true;
        return false;
    }

    private static String readTextPreview(File file) {
        int max = (int) Math.min(file.length(), MAX_TEXT_PREVIEW_BYTES);
        if (max <= 0) return "";
        byte[] data = new byte[max];
        try (FileInputStream input = new FileInputStream(file)) {
            int offset = 0;
            while (offset < data.length) {
                int read = input.read(data, offset, data.length - offset);
                if (read < 0) break;
                offset += read;
            }
            String value = new String(data, 0, offset, StandardCharsets.UTF_8)
                    .replace("\u0000", "")
                    .trim();
            if (file.length() > MAX_TEXT_PREVIEW_BYTES) {
                value += "\n…[preview truncated]";
            }
            return value;
        } catch (Throwable ignored) {
            return "";
        }
    }

    private static String sanitizeName(String name) {
        String value = name.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", "_").trim();
        if (value.isEmpty()) value = "attachment.bin";
        if (value.length() > 180) value = value.substring(value.length() - 180);
        return value;
    }

    private static String humanBytes(long bytes) {
        if (bytes < 1024L) return bytes + " B";
        double kb = bytes / 1024.0;
        if (kb < 1024.0) return String.format(Locale.ROOT, "%.1f KiB", kb);
        double mb = kb / 1024.0;
        if (mb < 1024.0) return String.format(Locale.ROOT, "%.1f MiB", mb);
        return String.format(Locale.ROOT, "%.2f GiB", mb / 1024.0);
    }

    private static String shortSha(String value) {
        if (value == null || value.isEmpty()) return "unknown";
        return value.substring(0, Math.min(12, value.length()));
    }

    private static String hex(byte[] data) {
        StringBuilder out = new StringBuilder(data.length * 2);
        for (byte b : data) out.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return out.toString();
    }

    private static void deleteRecursively(File file) {
        if (file == null || !file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteRecursively(child);
        }
        //noinspection ResultOfMethodCallIgnored
        file.delete();
    }
}
