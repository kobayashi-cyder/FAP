package jp.fap.runtime;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.graphics.BitmapFactory;
import android.media.MediaMetadataRetriever;
import android.os.Build;
import android.os.ParcelFileDescriptor;
import android.graphics.pdf.PdfRenderer;
import android.graphics.pdf.content.PdfPageTextContent;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Locale;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public final class AttachmentAnalyzer {
    private static final int MAX_EXTRACTED_CHARS = 120_000;
    private static final int MAX_ZIP_ENTRIES = 80;
    private static final Pattern XML_TAG = Pattern.compile("<[^>]+>");

    private AttachmentAnalyzer() {}

    public static String analyze(
            Context context,
            File file,
            String name,
            String mime) {
        String lower = name == null ? "" : name.toLowerCase(Locale.ROOT);
        String m = mime == null ? "" : mime.toLowerCase(Locale.ROOT);

        try {
            if (lower.endsWith(".pdf") || "application/pdf".equals(m)) {
                return analyzePdf(file);
            }
            if (m.startsWith("image/")) {
                return analyzeImage(file);
            }
            if (m.startsWith("audio/") || m.startsWith("video/")) {
                return analyzeMedia(file);
            }
            if (lower.endsWith(".apk")
                    || "application/vnd.android.package-archive".equals(m)) {
                return analyzeApk(context, file);
            }
            if (lower.endsWith(".docx")
                    || lower.endsWith(".pptx")
                    || lower.endsWith(".xlsx")
                    || lower.endsWith(".odt")
                    || lower.endsWith(".ods")
                    || lower.endsWith(".odp")) {
                return analyzeOfficeZip(file, lower);
            }
            if (lower.endsWith(".zip")
                    || lower.endsWith(".jar")
                    || lower.endsWith(".aar")
                    || lower.endsWith(".epub")
                    || lower.endsWith(".whl")) {
                return analyzeZip(file);
            }
        } catch (Throwable t) {
            return "解析補足: " + t.getClass().getSimpleName()
                    + ": " + String.valueOf(t.getMessage());
        }

        return analyzeMagic(file);
    }

    private static String analyzePdf(File file) throws Exception {
        try (ParcelFileDescriptor fd = ParcelFileDescriptor.open(
                file,
                ParcelFileDescriptor.MODE_READ_ONLY);
             PdfRenderer renderer = new PdfRenderer(fd)) {
            int pages = renderer.getPageCount();
            StringBuilder out = new StringBuilder("PDF · pages=").append(pages);
            if (pages > 0) {
                try (PdfRenderer.Page page = renderer.openPage(0)) {
                    out.append(" · firstPage=")
                            .append(page.getWidth())
                            .append("x")
                            .append(page.getHeight());
                }
            }

            if (Build.VERSION.SDK_INT < 35) {
                out.append("\nPDF本文抽出にはAndroid 15以降が必要です。ファイル本体は保持済み。");
                return out.toString();
            }

            int extractedPages = 0;
            int extractedSegments = 0;
            for (int i = 0; i < pages && out.length() < MAX_EXTRACTED_CHARS; i++) {
                try (PdfRenderer.Page page = renderer.openPage(i)) {
                    java.util.List<PdfPageTextContent> contents = page.getTextContents();
                    if (contents == null || contents.isEmpty()) continue;

                    StringBuilder pageText = new StringBuilder();
                    for (PdfPageTextContent content : contents) {
                        if (content == null) continue;
                        String text = content.getText();
                        if (text == null) continue;
                        text = text.trim();
                        if (text.isEmpty()) continue;
                        if (pageText.length() > 0) pageText.append("\n");
                        pageText.append(text);
                        extractedSegments++;
                        if (out.length() + pageText.length() >= MAX_EXTRACTED_CHARS) break;
                    }
                    if (pageText.length() == 0) continue;

                    out.append("\n\n[PDF page ")
                            .append(i + 1)
                            .append("]\n")
                            .append(pageText);
                    extractedPages++;
                }
            }

            if (out.length() > MAX_EXTRACTED_CHARS) {
                out.setLength(MAX_EXTRACTED_CHARS);
                out.append("\n[PDF text truncated]");
            }
            out.append("\n\nPDF本文抽出 · pages=")
                    .append(extractedPages)
                    .append("/")
                    .append(pages)
                    .append(" · segments=")
                    .append(extractedSegments);
            if (extractedPages == 0 && pages > 0) {
                out.append(" · 埋め込みテキストなし（スキャンPDFの可能性）");
            }
            return out.toString();
        }
    }

    private static String analyzeImage(File file) {
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), options);
        return "画像 · "
                + options.outWidth + "x" + options.outHeight
                + " · mime=" + String.valueOf(options.outMimeType);
    }

    private static String analyzeMedia(File file) {
        MediaMetadataRetriever retriever = new MediaMetadataRetriever();
        try {
            retriever.setDataSource(file.getAbsolutePath());
            String duration = retriever.extractMetadata(
                    MediaMetadataRetriever.METADATA_KEY_DURATION);
            String width = retriever.extractMetadata(
                    MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH);
            String height = retriever.extractMetadata(
                    MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT);
            String title = retriever.extractMetadata(
                    MediaMetadataRetriever.METADATA_KEY_TITLE);
            String artist = retriever.extractMetadata(
                    MediaMetadataRetriever.METADATA_KEY_ARTIST);

            StringBuilder out = new StringBuilder("メディア");
            if (duration != null) out.append(" · durationMs=").append(duration);
            if (width != null && height != null) {
                out.append(" · video=").append(width).append("x").append(height);
            }
            if (title != null && !title.isEmpty()) out.append("\nTitle: ").append(title);
            if (artist != null && !artist.isEmpty()) out.append("\nArtist: ").append(artist);
            return out.toString();
        } finally {
            try {
                retriever.release();
            } catch (Throwable ignored) {
            }
        }
    }

    private static String analyzeApk(Context context, File file) {
        PackageInfo info = context.getPackageManager().getPackageArchiveInfo(
                file.getAbsolutePath(),
                0);
        if (info == null) return "APK · package metadata unavailable";
        long version = android.os.Build.VERSION.SDK_INT >= 28
                ? info.getLongVersionCode()
                : info.versionCode;
        return "APK · package=" + info.packageName
                + " · versionName=" + String.valueOf(info.versionName)
                + " · versionCode=" + version;
    }

    private static String analyzeOfficeZip(File file, String lowerName) throws Exception {
        try (ZipFile zip = new ZipFile(file)) {
            ArrayList<String> candidates = new ArrayList<>();
            zip.stream()
                    .map(ZipEntry::getName)
                    .filter(name -> {
                        if (lowerName.endsWith(".docx")) {
                            return name.equals("word/document.xml")
                                    || name.startsWith("word/header")
                                    || name.startsWith("word/footer");
                        }
                        if (lowerName.endsWith(".pptx")) {
                            return name.startsWith("ppt/slides/slide")
                                    && name.endsWith(".xml");
                        }
                        if (lowerName.endsWith(".xlsx")) {
                            return name.equals("xl/sharedStrings.xml")
                                    || (name.startsWith("xl/worksheets/sheet")
                                        && name.endsWith(".xml"));
                        }
                        return name.equals("content.xml");
                    })
                    .sorted(Comparator.naturalOrder())
                    .forEach(candidates::add);

            StringBuilder out = new StringBuilder("Office/ODF抽出");
            int budget = MAX_EXTRACTED_CHARS;
            for (String entryName : candidates) {
                if (budget <= 0) break;
                ZipEntry entry = zip.getEntry(entryName);
                if (entry == null || entry.isDirectory()) continue;
                String xml;
                try (InputStream in = zip.getInputStream(entry)) {
                    xml = readUtf8(in, Math.min(512 * 1024, Math.max(4096, budget * 2)));
                }
                String text = xmlToText(xml);
                if (text.isEmpty()) continue;
                if (text.length() > budget) text = text.substring(0, budget);
                out.append("\n[").append(entryName).append("]\n").append(text);
                budget -= text.length();
            }

            if (out.length() == "Office/ODF抽出".length()) {
                out.append("\n本文候補なし");
            } else if (budget <= 0) {
                out.append("\n…[extraction truncated]");
            }
            return out.toString();
        }
    }

    private static String analyzeZip(File file) throws Exception {
        try (ZipFile zip = new ZipFile(file)) {
            StringBuilder out = new StringBuilder("Archive entries:");
            int[] count = {0};
            zip.stream()
                    .sorted(Comparator.comparing(ZipEntry::getName))
                    .limit(MAX_ZIP_ENTRIES)
                    .forEach(entry -> {
                        count[0]++;
                        out.append("\n")
                                .append(entry.isDirectory() ? "DIR " : "FILE ")
                                .append(entry.getName());
                        if (!entry.isDirectory()) {
                            out.append(" · ").append(entry.getSize()).append(" B");
                        }
                    });
            if (zip.size() > count[0]) {
                out.append("\n… +").append(zip.size() - count[0]).append(" entries");
            }
            return out.toString();
        }
    }

    private static String analyzeMagic(File file) {
        byte[] header = new byte[32];
        int read = 0;
        try (FileInputStream input = new FileInputStream(file)) {
            read = input.read(header);
        } catch (Throwable ignored) {
        }
        if (read <= 0) return "Binary/unknown · empty or unreadable header";
        StringBuilder hex = new StringBuilder();
        for (int i = 0; i < read; i++) {
            if (i > 0) hex.append(' ');
            hex.append(String.format(Locale.ROOT, "%02X", header[i] & 0xff));
        }
        return "Binary/unknown · magic[0.." + (read - 1) + "]=" + hex;
    }

    private static String readUtf8(InputStream input, int maxBytes) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int total = 0;
        while (true) {
            int read = input.read(buffer);
            if (read < 0) break;
            total += read;
            if (total > maxBytes) {
                int allowed = read - (total - maxBytes);
                if (allowed > 0) out.write(buffer, 0, allowed);
                break;
            }
            out.write(buffer, 0, read);
        }
        return out.toString(StandardCharsets.UTF_8.name());
    }

    private static String xmlToText(String xml) {
        if (xml == null || xml.isEmpty()) return "";
        String value = xml
                .replace("</w:p>", "\n")
                .replace("</a:p>", "\n")
                .replace("</text:p>", "\n")
                .replace("</table:table-row>", "\n")
                .replace("</c>", "\t");
        value = XML_TAG.matcher(value).replaceAll(" ");
        value = value
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&amp;", "&")
                .replace("&quot;", "\"")
                .replace("&apos;", "'");
        return value
                .replaceAll("[ \\t]+", " ")
                .replaceAll(" *\\n *", "\n")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
    }
}
