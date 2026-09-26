package jp.fap.runtime;

import android.content.Context;
import android.util.AtomicFile;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

public final class ChatLogStore {
    private static final String FILE_NAME = "chat_log.jsonl";
    private static final int MAX_ENTRIES = 1000;
    private static final int MAX_TEXT_CHARS = 20_000;

    private final File file;
    private final ArrayList<Entry> entries = new ArrayList<>();
    private long nextId = 1L;

    public static final class Entry {
        public final long id;
        public final long timestampMs;
        public final String role;
        public final String channel;
        public final String text;

        Entry(long id, long timestampMs, String role, String channel, String text) {
            this.id = id;
            this.timestampMs = timestampMs;
            this.role = role;
            this.channel = channel;
            this.text = text;
        }

        JSONObject toJson() throws Exception {
            JSONObject o = new JSONObject();
            o.put("id", id);
            o.put("timestamp_ms", timestampMs);
            o.put("role", role);
            o.put("channel", channel);
            o.put("text", text);
            return o;
        }

        static Entry fromJson(JSONObject o, long fallbackId) {
            long id = o.optLong("id", fallbackId);
            if (id <= 0L) id = fallbackId;
            return new Entry(
                    id,
                    o.optLong("timestamp_ms", 0L),
                    o.optString("role", "system"),
                    o.optString("channel", "unknown"),
                    o.optString("text", ""));
        }
    }

    public ChatLogStore(Context context) {
        file = new File(context.getFilesDir(), FILE_NAME);
        load();
    }

    public synchronized Entry append(String role, String channel, String text) {
        String cleanRole = normalizeRole(role);
        String cleanChannel = normalizeChannel(channel);
        String cleanText = text == null ? "" : text.trim();
        if (cleanText.isEmpty()) return null;
        if (cleanText.length() > MAX_TEXT_CHARS) {
            cleanText = cleanText.substring(0, MAX_TEXT_CHARS);
        }

        Entry entry = new Entry(
                nextId++,
                System.currentTimeMillis(),
                cleanRole,
                cleanChannel,
                cleanText);
        entries.add(entry);
        while (entries.size() > MAX_ENTRIES) {
            entries.remove(0);
        }
        persist();
        return entry;
    }

    public synchronized void clear() {
        entries.clear();
        nextId = 1L;
        persist();
    }

    public synchronized int size() {
        return entries.size();
    }

    public synchronized long lastId() {
        return entries.isEmpty() ? 0L : entries.get(entries.size() - 1).id;
    }

    public synchronized List<Entry> entriesAfter(long id, int limit) {
        int max = Math.max(1, Math.min(MAX_ENTRIES, limit));
        ArrayList<Entry> out = new ArrayList<>();
        for (Entry entry : entries) {
            if (entry.id <= id) continue;
            out.add(entry);
            if (out.size() >= max) break;
        }
        return out;
    }

    public synchronized boolean hasAssistantAfter(long id) {
        for (Entry entry : entries) {
            if (entry.id <= id) continue;
            if ("assistant".equals(entry.role)) return true;
            if ("user".equals(entry.role)) return false;
        }
        return false;
    }

    public synchronized boolean containsRecent(
            String role,
            String channel,
            String text,
            int lookback) {
        String r = normalizeRole(role);
        String c = normalizeChannel(channel);
        String t = text == null ? "" : text.trim();
        int start = Math.max(0, entries.size() - Math.max(1, lookback));
        for (int i = entries.size() - 1; i >= start; i--) {
            Entry entry = entries.get(i);
            if (entry.role.equals(r)
                    && entry.channel.equals(c)
                    && entry.text.equals(t)) {
                return true;
            }
        }
        return false;
    }

    public synchronized String recentJson(int limit) {
        int take = Math.max(1, Math.min(MAX_ENTRIES, limit));
        int start = Math.max(0, entries.size() - take);
        JSONArray array = new JSONArray();
        for (int i = start; i < entries.size(); i++) {
            try {
                array.put(entries.get(i).toJson());
            } catch (Throwable ignored) {
            }
        }
        return array.toString();
    }

    public synchronized String render(int limit) {
        int take = Math.max(1, Math.min(MAX_ENTRIES, limit));
        int start = Math.max(0, entries.size() - take);
        StringBuilder out = new StringBuilder();
        for (int i = start; i < entries.size(); i++) {
            Entry e = entries.get(i);
            if (out.length() > 0) out.append("\n\n");
            out.append(formatTime(e.timestampMs))
                    .append(" · ")
                    .append(roleLabel(e.role))
                    .append(" [")
                    .append(e.channel)
                    .append("] #")
                    .append(e.id)
                    .append("\n")
                    .append(e.text);
        }
        return out.toString();
    }

    private void load() {
        entries.clear();
        nextId = 1L;
        if (!file.isFile()) return;
        try {
            List<String> lines = java.nio.file.Files.readAllLines(
                    file.toPath(), StandardCharsets.UTF_8);
            int start = Math.max(0, lines.size() - MAX_ENTRIES);
            long fallbackId = 1L;
            long maxId = 0L;
            for (int i = start; i < lines.size(); i++) {
                String line = lines.get(i).trim();
                if (line.isEmpty()) continue;
                try {
                    Entry e = Entry.fromJson(new JSONObject(line), fallbackId++);
                    if (!e.text.isEmpty()) {
                        entries.add(e);
                        maxId = Math.max(maxId, e.id);
                    }
                } catch (Throwable ignored) {
                }
            }
            nextId = Math.max(1L, maxId + 1L);
            // Persist once to migrate legacy rows which did not yet carry IDs.
            persist();
        } catch (Throwable ignored) {
        }
    }

    private void persist() {
        try {
            AtomicFile atomic = new AtomicFile(file);
            FileOutputStream output = null;
            try {
                output = atomic.startWrite();
                for (Entry e : entries) {
                    byte[] row = (e.toJson().toString() + "\n")
                            .getBytes(StandardCharsets.UTF_8);
                    output.write(row);
                }
                output.flush();
                output.getFD().sync();
                atomic.finishWrite(output);
            } catch (Throwable t) {
                if (output != null) atomic.failWrite(output);
                throw t;
            }
        } catch (Throwable ignored) {
            // Chat logging must never break the conversation runtime.
        }
    }

    private static String normalizeRole(String role) {
        String value = role == null ? "" : role.trim().toLowerCase(Locale.ROOT);
        if ("user".equals(value) || "assistant".equals(value) || "system".equals(value)) {
            return value;
        }
        return "system";
    }

    private static String normalizeChannel(String channel) {
        String value = channel == null ? "" : channel.trim().toLowerCase(Locale.ROOT);
        value = value.replaceAll("[^a-z0-9_.:-]", "_");
        return value.isEmpty() ? "unknown" : value.substring(0, Math.min(40, value.length()));
    }

    private static String roleLabel(String role) {
        if ("user".equals(role)) return "あなた";
        if ("assistant".equals(role)) return "FAP";
        return "System";
    }

    private static String formatTime(long timestampMs) {
        SimpleDateFormat format = new SimpleDateFormat("MM/dd HH:mm:ss", Locale.JAPAN);
        format.setTimeZone(TimeZone.getDefault());
        return format.format(new Date(Math.max(0L, timestampMs)));
    }
}
