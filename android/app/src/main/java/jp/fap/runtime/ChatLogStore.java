package jp.fap.runtime;

import android.content.Context;
import android.util.AtomicFile;

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

    public static final class Entry {
        public final long timestampMs;
        public final String role;
        public final String channel;
        public final String text;

        Entry(long timestampMs, String role, String channel, String text) {
            this.timestampMs = timestampMs;
            this.role = role;
            this.channel = channel;
            this.text = text;
        }

        JSONObject toJson() throws Exception {
            JSONObject o = new JSONObject();
            o.put("timestamp_ms", timestampMs);
            o.put("role", role);
            o.put("channel", channel);
            o.put("text", text);
            return o;
        }

        static Entry fromJson(JSONObject o) {
            return new Entry(
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

    public synchronized void append(String role, String channel, String text) {
        String cleanRole = normalizeRole(role);
        String cleanChannel = normalizeChannel(channel);
        String cleanText = text == null ? "" : text.trim();
        if (cleanText.isEmpty()) return;
        if (cleanText.length() > MAX_TEXT_CHARS) {
            cleanText = cleanText.substring(0, MAX_TEXT_CHARS);
        }

        entries.add(new Entry(
                System.currentTimeMillis(),
                cleanRole,
                cleanChannel,
                cleanText));
        while (entries.size() > MAX_ENTRIES) {
            entries.remove(0);
        }
        persist();
    }

    public synchronized void clear() {
        entries.clear();
        persist();
    }

    public synchronized int size() {
        return entries.size();
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
                    .append("]\n")
                    .append(e.text);
        }
        return out.toString();
    }

    private void load() {
        entries.clear();
        if (!file.isFile()) return;
        try {
            List<String> lines = java.nio.file.Files.readAllLines(
                    file.toPath(), StandardCharsets.UTF_8);
            int start = Math.max(0, lines.size() - MAX_ENTRIES);
            for (int i = start; i < lines.size(); i++) {
                String line = lines.get(i).trim();
                if (line.isEmpty()) continue;
                try {
                    Entry e = Entry.fromJson(new JSONObject(line));
                    if (!e.text.isEmpty()) entries.add(e);
                } catch (Throwable ignored) {
                }
            }
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
