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
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
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
        String preview;
        if (isTextLike(mime, safe)) {
            String rawText = readTextPreview(output);
            if (looksDelimitedTable(mime, safe)) {
                char delimiter = safe.toLowerCase(Locale.ROOT).endsWith(".tsv")
                        ? '\t'
                        : ',';
                preview = profileDelimitedTable(
                        rawText,
                        delimiter,
                        output.length() > MAX_TEXT_PREVIEW_BYTES);
            } else {
                preview = rawText;
            }
        } else {
            preview = AttachmentAnalyzer.analyze(app, output, safe, mime);
        }

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

    private static boolean looksDelimitedTable(String mime, String name) {
        String m = mime == null ? "" : mime.toLowerCase(Locale.ROOT);
        String n = name == null ? "" : name.toLowerCase(Locale.ROOT);
        return m.contains("csv")
                || m.contains("tab-separated")
                || n.endsWith(".csv")
                || n.endsWith(".tsv");
    }

    private static String profileDelimitedTable(
            String raw,
            char delimiter,
            boolean sampled) {
        String value = raw == null ? "" : raw.trim();
        if (value.isEmpty()) return "表データ · empty";

        String[] lines = value.split("\\r?\\n");
        ArrayList<List<String>> rows = new ArrayList<>();
        for (String line : lines) {
            if (line == null || line.isEmpty()) continue;
            if (line.startsWith("…[preview truncated]")) break;
            rows.add(parseDelimitedLine(line, delimiter));
            if (rows.size() >= 4000) break;
        }
        if (rows.isEmpty()) return "表データ · no rows";

        int columns = 0;
        for (List<String> row : rows) columns = Math.max(columns, row.size());
        columns = Math.min(columns, 80);
        if (columns <= 0) return "表データ · no columns";

        List<String> header = rows.get(0);
        boolean hasHeader = looksLikeHeader(rows);
        int start = hasHeader ? 1 : 0;
        int dataRows = Math.max(0, rows.size() - start);

        StringBuilder out = new StringBuilder();
        out.append("表データ解析 · delimiter=")
                .append(delimiter == '\t' ? "TAB" : "COMMA")
                .append(" · rowsSampled=")
                .append(dataRows)
                .append(" · columns=")
                .append(columns)
                .append(" · header=")
                .append(hasHeader ? "yes" : "no");
        if (sampled) out.append(" · sourceTruncated=yes");

        for (int col = 0; col < columns && col < 24; col++) {
            String name = hasHeader && col < header.size()
                    ? cleanCell(header.get(col))
                    : "col" + (col + 1);
            if (name.isEmpty()) name = "col" + (col + 1);

            int present = 0;
            int missing = 0;
            int numeric = 0;
            double sum = 0.0;
            double min = Double.POSITIVE_INFINITY;
            double max = Double.NEGATIVE_INFINITY;
            LinkedHashMap<String, Integer> freq = new LinkedHashMap<>();

            for (int r = start; r < rows.size(); r++) {
                List<String> row = rows.get(r);
                String cell = col < row.size() ? cleanCell(row.get(col)) : "";
                if (cell.isEmpty()) {
                    missing++;
                    continue;
                }
                present++;
                Double number = parseNumber(cell);
                if (number != null && Double.isFinite(number)) {
                    numeric++;
                    sum += number;
                    min = Math.min(min, number);
                    max = Math.max(max, number);
                }
                if (freq.size() < 128 || freq.containsKey(cell)) {
                    freq.put(cell, freq.getOrDefault(cell, 0) + 1);
                }
            }

            out.append("\n- ")
                    .append(name)
                    .append(": present=")
                    .append(present)
                    .append(", missing=")
                    .append(missing);

            if (numeric > 0 && numeric >= Math.max(2, present * 3 / 5)) {
                out.append(", numeric=")
                        .append(numeric)
                        .append(", min=")
                        .append(formatNumber(min))
                        .append(", max=")
                        .append(formatNumber(max))
                        .append(", mean=")
                        .append(formatNumber(sum / numeric));
            } else {
                String top = topValue(freq);
                if (!top.isEmpty()) out.append(", top=").append(top);
            }
        }

        if (columns > 24) {
            out.append("\n… +").append(columns - 24).append(" columns");
        }

        out.append("\n\n[先頭データ]\n");
        int previewChars = Math.min(12000, value.length());
        out.append(value, 0, previewChars);
        if (value.length() > previewChars) out.append("\n…[table preview truncated]");
        return out.toString();
    }

    private static boolean looksLikeHeader(ArrayList<List<String>> rows) {
        if (rows.size() < 2) return true;
        List<String> first = rows.get(0);
        List<String> second = rows.get(1);
        int n = Math.max(first.size(), second.size());
        int firstText = 0;
        int secondNumeric = 0;
        for (int i = 0; i < n; i++) {
            String a = i < first.size() ? cleanCell(first.get(i)) : "";
            String b = i < second.size() ? cleanCell(second.get(i)) : "";
            if (!a.isEmpty() && parseNumber(a) == null) firstText++;
            if (!b.isEmpty() && parseNumber(b) != null) secondNumeric++;
        }
        return firstText >= Math.max(1, n / 2)
                && secondNumeric >= Math.max(1, n / 3);
    }

    private static List<String> parseDelimitedLine(String line, char delimiter) {
        ArrayList<String> out = new ArrayList<>();
        StringBuilder cell = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    cell.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
                continue;
            }
            if (ch == delimiter && !quoted) {
                out.add(cell.toString());
                cell.setLength(0);
            } else {
                cell.append(ch);
            }
        }
        out.add(cell.toString());
        return out;
    }

    private static String cleanCell(String value) {
        return value == null ? "" : value.trim();
    }

    private static Double parseNumber(String value) {
        if (value == null) return null;
        String v = value.trim()
                .replace(",", "")
                .replace("￥", "")
                .replace("$", "")
                .replace("%", "");
        if (v.isEmpty()) return null;
        try {
            return Double.parseDouble(v);
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static String formatNumber(double value) {
        double abs = Math.abs(value);
        if (abs >= 1_000_000.0 || (abs > 0 && abs < 0.001)) {
            return String.format(Locale.ROOT, "%.4e", value);
        }
        return String.format(Locale.ROOT, "%.4f", value)
                .replaceAll("0+$", "")
                .replaceAll("\\.$", "");
    }

    private static String topValue(Map<String, Integer> freq) {
        String best = "";
        int bestCount = 0;
        for (Map.Entry<String, Integer> entry : freq.entrySet()) {
            if (entry.getValue() > bestCount) {
                best = entry.getKey();
                bestCount = entry.getValue();
            }
        }
        if (best.isEmpty()) return "";
        if (best.length() > 60) best = best.substring(0, 60) + "…";
        return best + " (" + bestCount + ")";
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
