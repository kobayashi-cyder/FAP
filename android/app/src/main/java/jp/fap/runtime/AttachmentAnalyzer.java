package jp.fap.runtime;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.MediaMetadataRetriever;
import android.os.Build;
import android.os.ParcelFileDescriptor;
import android.graphics.pdf.PdfRenderer;
import android.graphics.pdf.content.PdfPageTextContent;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.label.ImageLabel;
import com.google.mlkit.vision.label.ImageLabeler;
import com.google.mlkit.vision.label.ImageLabeling;
import com.google.mlkit.vision.label.defaults.ImageLabelerOptions;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
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
                return analyzeMedia(context, file);
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
            int extractedPages = 0;
            int ocrPages = 0;
            int extractedSegments = 0;

            TextRecognizer ocr = null;
            try {
                for (int i = 0; i < pages && out.length() < MAX_EXTRACTED_CHARS; i++) {
                    String pageText = "";
                    try (PdfRenderer.Page page = renderer.openPage(i)) {
                        if (i == 0) {
                            out.append(" · firstPage=")
                                    .append(page.getWidth())
                                    .append("x")
                                    .append(page.getHeight());
                        }

                        if (Build.VERSION.SDK_INT >= 35) {
                            java.util.List<PdfPageTextContent> contents = page.getTextContents();
                            if (contents != null && !contents.isEmpty()) {
                                StringBuilder embedded = new StringBuilder();
                                for (PdfPageTextContent content : contents) {
                                    if (content == null || content.getText() == null) continue;
                                    String text = content.getText().trim();
                                    if (text.isEmpty()) continue;
                                    if (embedded.length() > 0) embedded.append("\n");
                                    embedded.append(text);
                                    extractedSegments++;
                                    if (out.length() + embedded.length() >= MAX_EXTRACTED_CHARS) {
                                        break;
                                    }
                                }
                                pageText = embedded.toString().trim();
                            }
                        }

                        if (pageText.isEmpty() && i < 12) {
                            if (ocr == null) {
                                ocr = TextRecognition.getClient(
                                        new JapaneseTextRecognizerOptions.Builder().build());
                            }
                            Bitmap bitmap = renderPdfPageForOcr(page, 1800);
                            if (bitmap != null) {
                                try {
                                    pageText = recognizeText(ocr, bitmap);
                                    if (!pageText.isEmpty()) {
                                        ocrPages++;
                                    }
                                } finally {
                                    bitmap.recycle();
                                }
                            }
                        }
                    }

                    if (pageText.isEmpty()) continue;
                    if (out.length() + pageText.length() > MAX_EXTRACTED_CHARS) {
                        pageText = pageText.substring(
                                0,
                                Math.max(0, MAX_EXTRACTED_CHARS - out.length()));
                    }
                    out.append("\n\n[PDF page ")
                            .append(i + 1)
                            .append("]\n")
                            .append(pageText);
                    extractedPages++;
                }
            } finally {
                if (ocr != null) {
                    try {
                        ocr.close();
                    } catch (Throwable ignored) {
                    }
                }
            }

            if (out.length() > MAX_EXTRACTED_CHARS) {
                out.setLength(MAX_EXTRACTED_CHARS);
                out.append("\n[PDF text truncated]");
            }

            out.append("\n\nPDF解析 · textPages=")
                    .append(extractedPages)
                    .append("/")
                    .append(pages)
                    .append(" · ocrPages=")
                    .append(ocrPages)
                    .append(" · embeddedSegments=")
                    .append(extractedSegments);
            if (extractedPages == 0 && pages > 0) {
                out.append(" · 本文を抽出できませんでした");
            } else if (pages > 12 && ocrPages > 0) {
                out.append(" · OCRは先頭12ページまで");
            }
            return out.toString();
        }
    }

    private static Bitmap renderPdfPageForOcr(PdfRenderer.Page page, int maxDimension) {
        if (page == null) return null;
        int sourceWidth = Math.max(1, page.getWidth());
        int sourceHeight = Math.max(1, page.getHeight());
        float scale = Math.min(
                1.0f,
                (float) maxDimension / (float) Math.max(sourceWidth, sourceHeight));
        int width = Math.max(1, Math.round(sourceWidth * scale));
        int height = Math.max(1, Math.round(sourceHeight * scale));
        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        bitmap.eraseColor(0xffffffff);
        page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
        return bitmap;
    }

    private static String analyzeImage(File file) throws Exception {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), bounds);

        Bitmap bitmap = decodeSampledBitmap(file, 2200);
        StringBuilder out = new StringBuilder("画像 · ")
                .append(bounds.outWidth)
                .append("x")
                .append(bounds.outHeight)
                .append(" · mime=")
                .append(String.valueOf(bounds.outMimeType));

        if (bitmap == null) {
            return out.append("\n画像デコード失敗").toString();
        }

        TextRecognizer recognizer = null;
        ImageLabeler labeler = null;
        try {
            InputImage image = InputImage.fromBitmap(bitmap, 0);

            recognizer = TextRecognition.getClient(
                    new JapaneseTextRecognizerOptions.Builder().build());
            Text recognized = Tasks.await(
                    recognizer.process(image),
                    12,
                    TimeUnit.SECONDS);
            String ocrText = recognized == null ? "" : recognized.getText().trim();
            if (!ocrText.isEmpty()) {
                if (ocrText.length() > 30_000) {
                    ocrText = ocrText.substring(0, 30_000) + "\n…[OCR truncated]";
                }
                out.append("\n\n[OCR]\n").append(ocrText);
            } else {
                out.append("\n\n[OCR] 文字検出なし");
            }

            ImageLabelerOptions options =
                    new ImageLabelerOptions.Builder()
                            .setConfidenceThreshold(0.45f)
                            .build();
            labeler = ImageLabeling.getClient(options);
            java.util.List<ImageLabel> labels = Tasks.await(
                    labeler.process(image),
                    12,
                    TimeUnit.SECONDS);
            if (labels != null && !labels.isEmpty()) {
                out.append("\n\n[画像ラベル]");
                int count = 0;
                for (ImageLabel label : labels) {
                    if (label == null || label.getText() == null) continue;
                    out.append("\n- ")
                            .append(label.getText())
                            .append(" · ")
                            .append(String.format(
                                    Locale.ROOT,
                                    "%.2f",
                                    label.getConfidence()));
                    if (++count >= 12) break;
                }
            } else {
                out.append("\n\n[画像ラベル] 検出なし");
            }
        } finally {
            if (recognizer != null) {
                try {
                    recognizer.close();
                } catch (Throwable ignored) {
                }
            }
            if (labeler != null) {
                try {
                    labeler.close();
                } catch (Throwable ignored) {
                }
            }
            bitmap.recycle();
        }
        return out.toString();
    }

    private static Bitmap decodeSampledBitmap(File file, int maxDimension) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), bounds);
        int width = Math.max(1, bounds.outWidth);
        int height = Math.max(1, bounds.outHeight);
        int sample = 1;
        while (Math.max(width / sample, height / sample) > maxDimension) {
            sample *= 2;
        }
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = Math.max(1, sample);
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        return BitmapFactory.decodeFile(file.getAbsolutePath(), options);
    }

    private static String recognizeText(TextRecognizer recognizer, Bitmap bitmap)
            throws Exception {
        if (recognizer == null || bitmap == null) return "";
        Text text = Tasks.await(
                recognizer.process(InputImage.fromBitmap(bitmap, 0)),
                12,
                TimeUnit.SECONDS);
        return text == null || text.getText() == null
                ? ""
                : text.getText().trim();
    }

    private static String analyzeBitmapFrame(Bitmap bitmap) throws Exception {
        if (bitmap == null) return "";
        StringBuilder out = new StringBuilder();
        TextRecognizer recognizer = null;
        ImageLabeler labeler = null;
        try {
            InputImage image = InputImage.fromBitmap(bitmap, 0);
            recognizer = TextRecognition.getClient(
                    new JapaneseTextRecognizerOptions.Builder().build());
            Text recognized = Tasks.await(
                    recognizer.process(image),
                    10,
                    TimeUnit.SECONDS);
            String text = recognized == null ? "" : recognized.getText().trim();
            if (!text.isEmpty()) {
                if (text.length() > 4000) text = text.substring(0, 4000) + "…";
                out.append("OCR=").append(text);
            }

            labeler = ImageLabeling.getClient(
                    new ImageLabelerOptions.Builder()
                            .setConfidenceThreshold(0.50f)
                            .build());
            java.util.List<ImageLabel> labels = Tasks.await(
                    labeler.process(image),
                    10,
                    TimeUnit.SECONDS);
            if (labels != null && !labels.isEmpty()) {
                if (out.length() > 0) out.append("\n");
                out.append("labels=");
                int count = 0;
                for (ImageLabel label : labels) {
                    if (label == null || label.getText() == null) continue;
                    if (count > 0) out.append(", ");
                    out.append(label.getText())
                            .append("(")
                            .append(String.format(Locale.ROOT, "%.2f", label.getConfidence()))
                            .append(")");
                    if (++count >= 8) break;
                }
            }
        } finally {
            if (recognizer != null) {
                try { recognizer.close(); } catch (Throwable ignored) {}
            }
            if (labeler != null) {
                try { labeler.close(); } catch (Throwable ignored) {}
            }
        }
        return out.toString();
    }

    private static String analyzeMedia(Context context, File file) throws Exception {
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

            if (width != null && height != null) {
                long durationMs = 0L;
                try {
                    durationMs = Long.parseLong(duration == null ? "0" : duration);
                } catch (NumberFormatException ignored) {
                }
                long middleUs = Math.max(0L, durationMs * 500L);
                Bitmap frame = retriever.getFrameAtTime(
                        middleUs,
                        MediaMetadataRetriever.OPTION_CLOSEST_SYNC);
                if (frame != null) {
                    try {
                        String vision = analyzeBitmapFrame(frame);
                        if (!vision.isEmpty()) {
                            out.append("\n\n[動画中央フレーム解析]\n").append(vision);
                        }
                    } finally {
                        frame.recycle();
                    }
                }
            }

            String transcript = AudioFileTranscriber.transcribe(
                    context,
                    file,
                    90_000L);
            if (transcript != null && !transcript.trim().isEmpty()) {
                out.append("\n\n[").append(transcript.trim()).append("]");
            }
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
