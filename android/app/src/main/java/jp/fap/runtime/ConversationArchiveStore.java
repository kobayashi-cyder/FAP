package jp.fap.runtime;

import android.content.Context;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.FileInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

public final class ConversationArchiveStore {
    public static final class Session {
        public final String id;
        public final String title;
        public final long archivedAt;
        public final File file;

        Session(String id, String title, long archivedAt, File file) {
            this.id = id;
            this.title = title;
            this.archivedAt = archivedAt;
            this.file = file;
        }

        public String displayLabel() {
            java.text.SimpleDateFormat format =
                    new java.text.SimpleDateFormat("MM/dd HH:mm", Locale.JAPAN);
            return title + "  ·  " + format.format(new java.util.Date(archivedAt));
        }
    }

    private final File root;

    public ConversationArchiveStore(Context context) {
        root = new File(context.getFilesDir(), "conversation_archive");
        if (!root.exists()) root.mkdirs();
    }

    public Session archive(ChatLogStore log) {
        if (log == null || log.size() <= 0) return null;
        try {
            long now = System.currentTimeMillis();
            String id = now + "-" + Integer.toHexString(log.exportJsonLines().hashCode());
            String title = log.suggestedTitle();
            JSONObject payload = new JSONObject();
            payload.put("schema", "fap.pixel.chat.session.v1");
            payload.put("id", id);
            payload.put("title", title);
            payload.put("archived_at", now);
            payload.put("jsonl", log.exportJsonLines());

            File file = new File(root, id + ".json");
            try (FileOutputStream out = new FileOutputStream(file)) {
                out.write((payload.toString() + "\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
                out.getFD().sync();
            }
            trim(80);
            return new Session(id, title, now, file);
        } catch (Throwable ignored) {
            return null;
        }
    }

    public List<Session> list() {
        ArrayList<Session> out = new ArrayList<>();
        File[] files = root.listFiles((dir, name) -> name.endsWith(".json"));
        if (files == null) return out;
        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
        for (File file : files) {
            Session session = readMeta(file);
            if (session != null) out.add(session);
            if (out.size() >= 80) break;
        }
        return out;
    }

    public boolean restore(Session session, ChatLogStore log) {
        if (session == null || log == null || session.file == null) return false;
        try {
            String raw = readUtf8(session.file);
            JSONObject payload = new JSONObject(raw);
            if (!"fap.pixel.chat.session.v1".equals(payload.optString("schema"))) {
                return false;
            }
            return log.importJsonLines(payload.optString("jsonl", ""));
        } catch (Throwable ignored) {
            return false;
        }
    }

    public boolean delete(Session session) {
        return session != null
                && session.file != null
                && (!session.file.exists() || session.file.delete());
    }

    private Session readMeta(File file) {
        try {
            String raw = readUtf8(file);
            JSONObject payload = new JSONObject(raw);
            if (!"fap.pixel.chat.session.v1".equals(payload.optString("schema"))) {
                return null;
            }
            return new Session(
                    payload.optString("id", file.getName()),
                    payload.optString("title", "チャット"),
                    payload.optLong("archived_at", file.lastModified()),
                    file);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static String readUtf8(File file) throws Exception {
        try (FileInputStream input = new FileInputStream(file);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            while (true) {
                int read = input.read(buffer);
                if (read < 0) break;
                output.write(buffer, 0, read);
                if (output.size() > 24 * 1024 * 1024) {
                    throw new IllegalArgumentException("conversation archive too large");
                }
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private void trim(int max) {
        File[] files = root.listFiles((dir, name) -> name.endsWith(".json"));
        if (files == null || files.length <= max) return;
        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
        for (int i = max; i < files.length; i++) {
            try {
                files[i].delete();
            } catch (Throwable ignored) {
            }
        }
    }
}
