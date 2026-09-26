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
    public static final String SURFACE_FRONT = "front";
    public static final String SURFACE_BACK = "back";

    private static final String FILE_NAME = "chat_log.jsonl";
    private static final int MAX_ENTRIES = 1200;
    private static final int MAX_TEXT_CHARS = 20_000;

    private final File file;
    private final ArrayList<Entry> entries = new ArrayList<>();
    private long nextId = 1L;

    public static final class Entry {
        public final long id;
        public final long timestampMs;
        public final String role;
        public final String channel;
        public final String surface;
        public final String text;

        Entry(
                long id,
                long timestampMs,
                String role,
                String channel,
                String surface,
                String text) {
            this.id = id;
            this.timestampMs = timestampMs;
            this.role = role;
            this.channel = channel;
            this.surface = surface;
            this.text = text;
        }

        JSONObject toJson() throws Exception {
            JSONObject o = new JSONObject();
            o.put("id", id);
            o.put("timestamp_ms", timestampMs);
            o.put("role", role);
            o.put("channel", channel);
            o.put("surface", surface);
            o.put("text", text);
            return o;
        }

        static Entry fromJson(JSONObject o, long fallbackId) {
            long id = o.optLong("id", fallbackId);
            if (id <= 0L) id = fallbackId;
            String role = o.optString("role", "system");
            String channel = o.optString("channel", "unknown");
            String surface = o.optString(
                    "surface",
                    inferSurface(role, channel));
            return new Entry(
                    id,
                    o.optLong("timestamp_ms", 0L),
                    role,
                    channel,
                    normalizeSurface(surface),
                    o.optString("text", ""));
        }
    }

    public ChatLogStore(Context context) {
        file = new File(context.getFilesDir(), FILE_NAME);
        load();
    }

    public synchronized Entry append(String role, String channel, String text) {
        return append(role, channel, inferSurface(role, channel), text);
    }

    public synchronized Entry appendFront(String role, String channel, String text) {
        return append(role, channel, SURFACE_FRONT, text);
    }

    public synchronized Entry appendBack(String role, String channel, String text) {
        return append(role, channel, SURFACE_BACK, text);
    }

    public synchronized Entry append(
            String role,
            String channel,
            String surface,
            String text) {
        String cleanRole = normalizeRole(role);
        String cleanChannel = normalizeChannel(channel);
        String cleanSurface = normalizeSurface(surface);
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
                cleanSurface,
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

    public synchronized boolean updateText(long id, String text) {
        String clean = text == null ? "" : text;
        if (clean.length() > MAX_TEXT_CHARS) {
            clean = clean.substring(0, MAX_TEXT_CHARS);
        }
        for (int i = 0; i < entries.size(); i++) {
            Entry old = entries.get(i);
            if (old.id != id) continue;
            entries.set(i, new Entry(
                    old.id,
                    old.timestampMs,
                    old.role,
                    old.channel,
                    old.surface,
                    clean));
            persist();
            return true;
        }
        return false;
    }

    public synchronized String exportJsonLines() {
        StringBuilder out = new StringBuilder();
        for (Entry entry : entries) {
            try {
                out.append(entry.toJson().toString()).append("\n");
            } catch (Throwable ignored) {
            }
        }
        return out.toString();
    }

    public synchronized boolean importJsonLines(String jsonl) {
        if (jsonl == null) return false;
        ArrayList<Entry> imported = new ArrayList<>();
        long fallbackId = 1L;
        long maxId = 0L;
        for (String line : jsonl.split("\\r?\\n")) {
            String clean = line == null ? "" : line.trim();
            if (clean.isEmpty()) continue;
            try {
                Entry entry = Entry.fromJson(new JSONObject(clean), fallbackId++);
                if (entry.text == null || entry.text.isEmpty()) continue;
                imported.add(entry);
                maxId = Math.max(maxId, entry.id);
                if (imported.size() >= MAX_ENTRIES) break;
            } catch (Throwable ignored) {
            }
        }
        entries.clear();
        entries.addAll(imported);
        nextId = Math.max(1L, maxId + 1L);
        persist();
        return !entries.isEmpty();
    }

    public synchronized String suggestedTitle() {
        for (Entry entry : entries) {
            if (!SURFACE_FRONT.equals(entry.surface) || !"user".equals(entry.role)) continue;
            String title = entry.text == null ? "" : entry.text
                    .replaceAll("\\s+", " ")
                    .trim();
            if (title.isEmpty()) continue;
            return title.substring(0, Math.min(48, title.length()));
        }
        return "新しいチャット";
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

    public synchronized boolean hasFrontAssistantAfter(long id) {
        for (Entry entry : entries) {
            if (entry.id <= id) continue;
            if (!SURFACE_FRONT.equals(entry.surface)) continue;
            if ("assistant".equals(entry.role)) return true;
            if ("user".equals(entry.role)) return false;
        }
        return false;
    }

    public synchronized boolean containsRecent(
            String role,
            String channel,
            String surface,
            String text,
            int lookback) {
        String r = normalizeRole(role);
        String c = normalizeChannel(channel);
        String s = normalizeSurface(surface);
        String t = text == null ? "" : text.trim();
        int start = Math.max(0, entries.size() - Math.max(1, lookback));
        for (int i = entries.size() - 1; i >= start; i--) {
            Entry entry = entries.get(i);
            if (entry.role.equals(r)
                    && entry.channel.equals(c)
                    && entry.surface.equals(s)
                    && entry.text.equals(t)) {
                return true;
            }
        }
        return false;
    }

    public synchronized String recentConversationJson(int limit) {
        JSONArray array = new JSONArray();
        int remaining = Math.max(1, Math.min(MAX_ENTRIES, limit));
        ArrayList<Entry> selected = new ArrayList<>();
        for (int i = entries.size() - 1; i >= 0 && selected.size() < remaining; i--) {
            Entry entry = entries.get(i);
            if (!SURFACE_FRONT.equals(entry.surface)) continue;
            if (!"user".equals(entry.role) && !"assistant".equals(entry.role)) continue;
            selected.add(0, entry);
        }
        for (Entry entry : selected) {
            try {
                array.put(entry.toJson());
            } catch (Throwable ignored) {
            }
        }
        return array.toString();
    }

    public synchronized String renderFront(int limit) {
        return renderSurface(SURFACE_FRONT, limit);
    }

    public synchronized String renderBack(int limit) {
        return renderSurface(SURFACE_BACK, limit);
    }

    public synchronized String renderAll(int limit) {
        return renderSurface(null, limit);
    }

    public synchronized List<Entry> snapshot(String mode, int limit) {
        String selectedMode = mode == null ? "timeline" : mode;
        int take = Math.max(1, Math.min(MAX_ENTRIES, limit));
        ArrayList<Entry> selected = new ArrayList<>();
        for (int i = entries.size() - 1; i >= 0 && selected.size() < take; i--) {
            Entry entry = entries.get(i);
            if ("front".equals(selectedMode) && !SURFACE_FRONT.equals(entry.surface)) continue;
            if ("back".equals(selectedMode) && !SURFACE_BACK.equals(entry.surface)) continue;
            selected.add(0, entry);
        }
        return new ArrayList<>(selected);
    }

    public synchronized String renderTimeline(int limit) {
        int take = Math.max(1, Math.min(MAX_ENTRIES, limit));
        int start = Math.max(0, entries.size() - take);
        StringBuilder out = new StringBuilder();
        for (int i = start; i < entries.size(); i++) {
            Entry e = entries.get(i);
            if (out.length() > 0) out.append("\n\n");
            out.append(actorLabel(e))
                    .append("  ·  ")
                    .append(formatTime(e.timestampMs))
                    .append("  ·  #")
                    .append(e.id);
            if (SURFACE_BACK.equals(e.surface)) {
                out.append("  ·  裏");
            }
            out.append("\n")
                    .append(e.text);
        }
        return out.toString();
    }

    private String renderSurface(String surface, int limit) {
        int take = Math.max(1, Math.min(MAX_ENTRIES, limit));
        ArrayList<Entry> selected = new ArrayList<>();
        for (int i = entries.size() - 1; i >= 0 && selected.size() < take; i--) {
            Entry entry = entries.get(i);
            if (surface != null && !surface.equals(entry.surface)) continue;
            selected.add(0, entry);
        }

        StringBuilder out = new StringBuilder();
        for (Entry e : selected) {
            if (out.length() > 0) out.append("\n\n");
            out.append(formatTime(e.timestampMs))
                    .append(" · ")
                    .append(actorLabel(e))
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
            // Logging must never break the conversation or agent runtime.
        }
    }

    private static String inferSurface(String role, String channel) {
        String r = normalizeRole(role);
        String c = normalizeChannel(channel);
        if ("system".equals(r)) return SURFACE_BACK;
        if (c.startsWith("agent:")
                || c.startsWith("git")
                || c.startsWith("browser-raw")
                || c.startsWith("voice-meta")
                || c.startsWith("trace")) {
            return SURFACE_BACK;
        }
        return SURFACE_FRONT;
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
        return value.isEmpty() ? "unknown" : value.substring(0, Math.min(48, value.length()));
    }

    private static String normalizeSurface(String surface) {
        return SURFACE_BACK.equals(surface) ? SURFACE_BACK : SURFACE_FRONT;
    }

    private static String actorLabel(Entry entry) {
        String channel = entry.channel == null ? "" : entry.channel;
        if ("user".equals(entry.role)) return "あなた";
        if ("assistant".equals(entry.role)) return "FAP";
        if (channel.startsWith("git")) return "Git";
        if (channel.startsWith("browser")) return "Browser";
        if (channel.startsWith("voice")) return "Voice";
        if (channel.startsWith("agent")) return "FAP Agent";
        return "FAP System";
    }

    private static String formatTime(long timestampMs) {
        SimpleDateFormat format = new SimpleDateFormat("MM/dd HH:mm:ss", Locale.JAPAN);
        format.setTimeZone(TimeZone.getDefault());
        return format.format(new Date(Math.max(0L, timestampMs)));
    }
}
