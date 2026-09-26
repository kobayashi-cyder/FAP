package jp.fap.runtime;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.media.Image;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.media.MediaMuxer;

import java.io.File;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class AndroidVideoComposer {
    private static final String MIME = MediaFormat.MIMETYPE_VIDEO_AVC;

    public static final class Result {
        public final boolean ok;
        public final String path;
        public final String error;
        public final int durationSeconds;
        public final int fps;
        public final int width;
        public final int height;

        Result(
                boolean ok,
                String path,
                String error,
                int durationSeconds,
                int fps,
                int width,
                int height) {
            this.ok = ok;
            this.path = path == null ? "" : path;
            this.error = error == null ? "" : error;
            this.durationSeconds = durationSeconds;
            this.fps = fps;
            this.width = width;
            this.height = height;
        }
    }

    private AndroidVideoComposer() {}

    public static Result compose(
            Context context,
            List<String> framePaths,
            int requestedDurationSeconds,
            int requestedFps,
            int requestedWidth,
            int requestedHeight) {
        int durationSeconds = Math.max(2, Math.min(15, requestedDurationSeconds));
        int fps = Math.max(8, Math.min(24, requestedFps));
        int width = even(Math.max(256, Math.min(720, requestedWidth)));
        int height = even(Math.max(256, Math.min(720, requestedHeight)));

        ArrayList<Bitmap> keyframes = new ArrayList<>();
        if (framePaths != null) {
            for (String raw : framePaths) {
                if (raw == null || raw.trim().isEmpty()) continue;
                try {
                    Bitmap bitmap = BitmapFactory.decodeFile(raw.trim());
                    if (bitmap != null && bitmap.getWidth() > 0 && bitmap.getHeight() > 0) {
                        keyframes.add(bitmap);
                    }
                } catch (Throwable ignored) {
                }
            }
        }

        if (keyframes.isEmpty()) {
            return new Result(
                    false,
                    "",
                    "no decodable video keyframes",
                    durationSeconds,
                    fps,
                    width,
                    height);
        }

        File outputDir = new File(context.getFilesDir(), "generated_media");
        if (!outputDir.exists() && !outputDir.mkdirs()) {
            recycle(keyframes);
            return new Result(
                    false,
                    "",
                    "could not create generated_media directory",
                    durationSeconds,
                    fps,
                    width,
                    height);
        }
        File output = new File(
                outputDir,
                String.format(
                        Locale.ROOT,
                        "fap_video_%d.mp4",
                        System.currentTimeMillis()));

        MediaCodec encoder = null;
        MediaMuxer muxer = null;
        boolean muxerStarted = false;
        int trackIndex = -1;
        try {
            encoder = MediaCodec.createEncoderByType(MIME);
            int colorFormat = selectColorFormat(encoder.getCodecInfo(), MIME);

            MediaFormat format = MediaFormat.createVideoFormat(MIME, width, height);
            format.setInteger(MediaFormat.KEY_COLOR_FORMAT, colorFormat);
            format.setInteger(MediaFormat.KEY_BIT_RATE, Math.max(900_000, width * height * 6));
            format.setInteger(MediaFormat.KEY_FRAME_RATE, fps);
            format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);
            encoder.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
            encoder.start();

            muxer = new MediaMuxer(
                    output.getAbsolutePath(),
                    MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);

            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            Bitmap frame = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            int totalFrames = Math.max(1, durationSeconds * fps);

            for (int frameIndex = 0; frameIndex < totalFrames; frameIndex++) {
                renderFrame(frame, keyframes, frameIndex, totalFrames);
                long ptsUs = frameIndex * 1_000_000L / fps;

                int inputIndex;
                do {
                    inputIndex = encoder.dequeueInputBuffer(10_000);
                    DrainState state = drainAvailable(
                            encoder,
                            muxer,
                            info,
                            false,
                            muxerStarted,
                            trackIndex);
                    muxerStarted = state.muxerStarted;
                    trackIndex = state.trackIndex;
                } while (inputIndex < 0);

                Image inputImage = null;
                try {
                    inputImage = encoder.getInputImage(inputIndex);
                } catch (Throwable ignored) {
                }

                int size;
                if (inputImage != null) {
                    fillYuv420Image(inputImage, frame);
                    size = width * height * 3 / 2;
                    inputImage.close();
                } else {
                    ByteBuffer buffer = encoder.getInputBuffer(inputIndex);
                    if (buffer == null) {
                        throw new IllegalStateException("encoder input buffer unavailable");
                    }
                    buffer.clear();
                    byte[] yuv = toYuv420(frame, colorFormat);
                    buffer.put(yuv);
                    size = yuv.length;
                }
                encoder.queueInputBuffer(inputIndex, 0, size, ptsUs, 0);

                DrainState state = drainAvailable(
                        encoder,
                        muxer,
                        info,
                        false,
                        muxerStarted,
                        trackIndex);
                muxerStarted = state.muxerStarted;
                trackIndex = state.trackIndex;
            }

            int eosIndex;
            do {
                eosIndex = encoder.dequeueInputBuffer(10_000);
                DrainState state = drainAvailable(
                        encoder,
                        muxer,
                        info,
                        false,
                        muxerStarted,
                        trackIndex);
                muxerStarted = state.muxerStarted;
                trackIndex = state.trackIndex;
            } while (eosIndex < 0);

            long eosPts = totalFrames * 1_000_000L / fps;
            encoder.queueInputBuffer(
                    eosIndex,
                    0,
                    0,
                    eosPts,
                    MediaCodec.BUFFER_FLAG_END_OF_STREAM);

            boolean eos = false;
            while (!eos) {
                int outIndex = encoder.dequeueOutputBuffer(info, 20_000);
                if (outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    if (muxerStarted) {
                        throw new IllegalStateException("encoder output format changed twice");
                    }
                    trackIndex = muxer.addTrack(encoder.getOutputFormat());
                    muxer.start();
                    muxerStarted = true;
                } else if (outIndex >= 0) {
                    ByteBuffer encoded = encoder.getOutputBuffer(outIndex);
                    if (encoded == null) {
                        throw new IllegalStateException("encoder output buffer unavailable");
                    }
                    if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
                        info.size = 0;
                    }
                    if (info.size > 0) {
                        if (!muxerStarted || trackIndex < 0) {
                            throw new IllegalStateException("muxer not started before video sample");
                        }
                        encoded.position(info.offset);
                        encoded.limit(info.offset + info.size);
                        muxer.writeSampleData(trackIndex, encoded, info);
                    }
                    eos = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
                    encoder.releaseOutputBuffer(outIndex, false);
                }
            }

            frame.recycle();
            if (!output.isFile() || output.length() < 1024) {
                throw new IllegalStateException("encoded MP4 failed artifact verification");
            }

            return new Result(
                    true,
                    output.getAbsolutePath(),
                    "",
                    durationSeconds,
                    fps,
                    width,
                    height);
        } catch (Throwable t) {
            try {
                output.delete();
            } catch (Throwable ignored) {
            }
            return new Result(
                    false,
                    "",
                    t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()),
                    durationSeconds,
                    fps,
                    width,
                    height);
        } finally {
            if (encoder != null) {
                try {
                    encoder.stop();
                } catch (Throwable ignored) {
                }
                try {
                    encoder.release();
                } catch (Throwable ignored) {
                }
            }
            if (muxer != null) {
                if (muxerStarted) {
                    try {
                        muxer.stop();
                    } catch (Throwable ignored) {
                    }
                }
                try {
                    muxer.release();
                } catch (Throwable ignored) {
                }
            }
            recycle(keyframes);
        }
    }

    private static DrainState drainAvailable(
            MediaCodec encoder,
            MediaMuxer muxer,
            MediaCodec.BufferInfo info,
            boolean wait,
            boolean muxerStarted,
            int trackIndex) {
        while (true) {
            int outIndex = encoder.dequeueOutputBuffer(info, wait ? 10_000 : 0);
            if (outIndex == MediaCodec.INFO_TRY_AGAIN_LATER) {
                return new DrainState(muxerStarted, trackIndex);
            }
            if (outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                if (muxerStarted) {
                    throw new IllegalStateException("encoder output format changed twice");
                }
                trackIndex = muxer.addTrack(encoder.getOutputFormat());
                muxer.start();
                muxerStarted = true;
                continue;
            }
            if (outIndex >= 0) {
                ByteBuffer encoded = encoder.getOutputBuffer(outIndex);
                if (encoded == null) {
                    throw new IllegalStateException("encoder output buffer unavailable");
                }
                if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
                    info.size = 0;
                }
                if (info.size > 0) {
                    if (!muxerStarted || trackIndex < 0) {
                        throw new IllegalStateException("muxer not started before sample");
                    }
                    encoded.position(info.offset);
                    encoded.limit(info.offset + info.size);
                    muxer.writeSampleData(trackIndex, encoded, info);
                }
                encoder.releaseOutputBuffer(outIndex, false);
                continue;
            }
        }
    }

    private static int selectColorFormat(MediaCodecInfo info, String mime) {
        MediaCodecInfo.CodecCapabilities caps = info.getCapabilitiesForType(mime);
        int[] preferred = {
                MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible,
                MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420SemiPlanar,
                MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Planar
        };
        for (int want : preferred) {
            for (int have : caps.colorFormats) {
                if (have == want) return want;
            }
        }
        throw new IllegalStateException("no supported YUV420 encoder color format");
    }

    private static void renderFrame(
            Bitmap target,
            List<Bitmap> keyframes,
            int frameIndex,
            int totalFrames) {
        Canvas canvas = new Canvas(target);
        canvas.drawColor(Color.BLACK);

        if (keyframes.size() == 1) {
            float phase = totalFrames <= 1 ? 0f : frameIndex / (float) (totalFrames - 1);
            drawCover(canvas, keyframes.get(0), target.getWidth(), target.getHeight(), 255, phase);
            return;
        }

        float global = totalFrames <= 1
                ? 0f
                : frameIndex / (float) (totalFrames - 1);
        float position = global * (keyframes.size() - 1);
        int left = Math.min(keyframes.size() - 1, (int) Math.floor(position));
        int right = Math.min(keyframes.size() - 1, left + 1);
        float mix = Math.max(0f, Math.min(1f, position - left));

        int alphaLeft = Math.round(255f * (1f - mix));
        int alphaRight = Math.round(255f * mix);
        drawCover(
                canvas,
                keyframes.get(left),
                target.getWidth(),
                target.getHeight(),
                alphaLeft,
                global);
        if (right != left && alphaRight > 0) {
            drawCover(
                    canvas,
                    keyframes.get(right),
                    target.getWidth(),
                    target.getHeight(),
                    alphaRight,
                    global);
        }
    }

    private static void drawCover(
            Canvas canvas,
            Bitmap source,
            int targetWidth,
            int targetHeight,
            int alpha,
            float phase) {
        float sourceAspect = source.getWidth() / (float) source.getHeight();
        float targetAspect = targetWidth / (float) targetHeight;

        int baseW = source.getWidth();
        int baseH = source.getHeight();
        if (sourceAspect > targetAspect) {
            baseW = Math.round(source.getHeight() * targetAspect);
        } else {
            baseH = Math.round(source.getWidth() / targetAspect);
        }

        float zoom = 1.0f + 0.08f * Math.max(0f, Math.min(1f, phase));
        int cropW = Math.max(2, Math.round(baseW / zoom));
        int cropH = Math.max(2, Math.round(baseH / zoom));
        float pan = (phase - 0.5f) * 0.06f;
        int cx = source.getWidth() / 2 + Math.round(pan * source.getWidth());
        int cy = source.getHeight() / 2 - Math.round(pan * source.getHeight());
        int left = clamp(cx - cropW / 2, 0, source.getWidth() - cropW);
        int top = clamp(cy - cropH / 2, 0, source.getHeight() - cropH);

        Rect src = new Rect(left, top, left + cropW, top + cropH);
        Rect dst = new Rect(0, 0, targetWidth, targetHeight);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        paint.setAlpha(Math.max(0, Math.min(255, alpha)));
        canvas.drawBitmap(source, src, dst, paint);
    }

    private static void fillYuv420Image(Image image, Bitmap bitmap) {
        int width = bitmap.getWidth();
        int height = bitmap.getHeight();
        int[] pixels = new int[width * height];
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height);

        Image.Plane[] planes = image.getPlanes();
        if (planes == null || planes.length < 3) {
            throw new IllegalStateException("encoder input image has no YUV planes");
        }

        ByteBuffer yBuf = planes[0].getBuffer();
        ByteBuffer uBuf = planes[1].getBuffer();
        ByteBuffer vBuf = planes[2].getBuffer();
        int yBase = yBuf.position();
        int uBase = uBuf.position();
        int vBase = vBuf.position();

        int yRowStride = planes[0].getRowStride();
        int yPixelStride = planes[0].getPixelStride();
        int uRowStride = planes[1].getRowStride();
        int uPixelStride = planes[1].getPixelStride();
        int vRowStride = planes[2].getRowStride();
        int vPixelStride = planes[2].getPixelStride();

        for (int y = 0; y < height; y++) {
            int row = y * width;
            for (int x = 0; x < width; x++) {
                int color = pixels[row + x];
                int r = Color.red(color);
                int g = Color.green(color);
                int b = Color.blue(color);
                int yy = clamp8(((66 * r + 129 * g + 25 * b + 128) >> 8) + 16);
                yBuf.put(yBase + y * yRowStride + x * yPixelStride, (byte) yy);
            }
        }

        for (int y = 0; y < height; y += 2) {
            int row = y * width;
            int cy = y / 2;
            for (int x = 0; x < width; x += 2) {
                int color = pixels[row + x];
                int r = Color.red(color);
                int g = Color.green(color);
                int b = Color.blue(color);
                int u = clamp8(((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128);
                int v = clamp8(((112 * r - 94 * g - 18 * b + 128) >> 8) + 128);
                int cx = x / 2;
                uBuf.put(uBase + cy * uRowStride + cx * uPixelStride, (byte) u);
                vBuf.put(vBase + cy * vRowStride + cx * vPixelStride, (byte) v);
            }
        }
    }

    private static byte[] toYuv420(Bitmap bitmap, int colorFormat) {
        int width = bitmap.getWidth();
        int height = bitmap.getHeight();
        int[] pixels = new int[width * height];
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height);

        int frameSize = width * height;
        byte[] out = new byte[frameSize * 3 / 2];
        int uStart = frameSize;
        int vStart = frameSize + frameSize / 4;
        int uv = frameSize;

        for (int y = 0; y < height; y++) {
            int row = y * width;
            for (int x = 0; x < width; x++) {
                int color = pixels[row + x];
                int r = Color.red(color);
                int g = Color.green(color);
                int b = Color.blue(color);
                int yy = clamp8(((66 * r + 129 * g + 25 * b + 128) >> 8) + 16);
                out[row + x] = (byte) yy;

                if ((x & 1) == 0 && (y & 1) == 0) {
                    int u = clamp8(((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128);
                    int v = clamp8(((112 * r - 94 * g - 18 * b + 128) >> 8) + 128);
                    if (colorFormat == MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Planar) {
                        int chromaIndex = (y / 2) * (width / 2) + (x / 2);
                        out[uStart + chromaIndex] = (byte) u;
                        out[vStart + chromaIndex] = (byte) v;
                    } else {
                        out[uv++] = (byte) u;
                        out[uv++] = (byte) v;
                    }
                }
            }
        }
        return out;
    }

    private static void recycle(List<Bitmap> bitmaps) {
        for (Bitmap bitmap : bitmaps) {
            if (bitmap == null) continue;
            try {
                if (!bitmap.isRecycled()) bitmap.recycle();
            } catch (Throwable ignored) {
            }
        }
    }

    private static int even(int value) {
        return (value & 1) == 0 ? value : value - 1;
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private static int clamp8(int value) {
        return Math.max(0, Math.min(255, value));
    }

    private static final class DrainState {
        final boolean muxerStarted;
        final int trackIndex;

        DrainState(boolean muxerStarted, int trackIndex) {
            this.muxerStarted = muxerStarted;
            this.trackIndex = trackIndex;
        }
    }
}
