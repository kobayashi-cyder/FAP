package jp.fap.runtime;

import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class GeneratedMediaStore {
    private static final int MAX_FILES = 24;
    private static final long MAX_BYTES = 320L * 1024L * 1024L;

    private GeneratedMediaStore() {}

    public static File directory(Context context) {
        File dir = new File(context.getFilesDir(), "generated_media");
        if (!dir.exists()) dir.mkdirs();
        return dir;
    }

    public static File keepCover(Context context, String sourcePath) {
        if (sourcePath == null || sourcePath.trim().isEmpty()) return null;
        File source = new File(sourcePath.trim());
        if (!source.isFile()) return null;
        String suffix = source.getName().toLowerCase().endsWith(".jpg") ? ".jpg" : ".png";
        File target = new File(
                directory(context),
                "cover_" + System.currentTimeMillis() + suffix);
        try (FileInputStream in = new FileInputStream(source);
             FileOutputStream out = new FileOutputStream(target)) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = in.read(buffer)) > 0) out.write(buffer, 0, read);
            out.flush();
            return target.isFile() && target.length() > 0 ? target : null;
        } catch (Throwable ignored) {
            try { target.delete(); } catch (Throwable ignoredAgain) {}
            return null;
        }
    }

    public static void deleteTransientFrames(List<String> framePaths, String preservedPath) {
        if (framePaths == null) return;
        String keep = preservedPath == null ? "" : new File(preservedPath).getAbsolutePath();
        for (String raw : framePaths) {
            if (raw == null || raw.trim().isEmpty()) continue;
            File file = new File(raw.trim());
            if (file.getAbsolutePath().equals(keep)) continue;
            try {
                if (file.isFile()) file.delete();
            } catch (Throwable ignored) {
            }
        }
    }

    public static void prune(Context context, String... keepPaths) {
        File dir = directory(context);
        File[] files = dir.listFiles(File::isFile);
        if (files == null || files.length == 0) return;

        Set<String> keep = new HashSet<>();
        if (keepPaths != null) {
            for (String raw : keepPaths) {
                if (raw == null || raw.trim().isEmpty()) continue;
                keep.add(new File(raw.trim()).getAbsolutePath());
            }
        }

        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
        long total = 0L;
        for (File file : files) total += Math.max(0L, file.length());

        int retained = 0;
        for (File file : files) {
            String path = file.getAbsolutePath();
            boolean pinned = keep.contains(path);
            boolean overCount = retained >= MAX_FILES;
            boolean overBytes = total > MAX_BYTES;
            if (pinned || (!overCount && !overBytes)) {
                retained++;
                continue;
            }
            long size = Math.max(0L, file.length());
            try {
                if (file.delete()) total = Math.max(0L, total - size);
            } catch (Throwable ignored) {
                retained++;
            }
        }
    }
}
