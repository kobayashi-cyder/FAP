package jp.fap.runtime;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Best-effort local transcription for attached audio on Android 13+.
 * It decodes compressed audio to PCM and injects that PCM into the on-device
 * SpeechRecognizer through RecognizerIntent.EXTRA_AUDIO_SOURCE.
 */
public final class AudioFileTranscriber {
    private AudioFileTranscriber() {}

    private static final class AudioSpec {
        final int sampleRate;
        final int channels;
        final String mime;

        AudioSpec(int sampleRate, int channels, String mime) {
            this.sampleRate = sampleRate;
            this.channels = channels;
            this.mime = mime;
        }
    }

    public static String transcribe(Context context, File file, long timeoutMs) {
        if (context == null || file == null || !file.isFile()) return "";
        if (Build.VERSION.SDK_INT < 33) {
            return "音声文字起こし: Android 13以降が必要";
        }
        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            return "音声文字起こし: RECORD_AUDIO権限を許可すると利用可能";
        }
        if (!SpeechRecognizer.isOnDeviceRecognitionAvailable(context)) {
            return "音声文字起こし: オンデバイス音声認識が利用できません";
        }

        AudioSpec spec;
        try {
            spec = inspect(file);
        } catch (Throwable t) {
            return "音声文字起こし: audio track unavailable · "
                    + t.getClass().getSimpleName();
        }

        ParcelFileDescriptor[] pipe;
        try {
            pipe = ParcelFileDescriptor.createPipe();
        } catch (Throwable t) {
            return "音声文字起こし: pipe create failed";
        }

        ParcelFileDescriptor readFd = pipe[0];
        ParcelFileDescriptor writeFd = pipe[1];
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>("");
        AtomicReference<String> error = new AtomicReference<>("");
        AtomicReference<SpeechRecognizer> recognizerRef = new AtomicReference<>();
        StringBuilder segmented = new StringBuilder();
        Handler main = new Handler(Looper.getMainLooper());

        main.post(() -> {
            try {
                SpeechRecognizer recognizer =
                        SpeechRecognizer.createOnDeviceSpeechRecognizer(context);
                recognizerRef.set(recognizer);
                recognizer.setRecognitionListener(new RecognitionListener() {
                    @Override public void onReadyForSpeech(Bundle params) {}
                    @Override public void onBeginningOfSpeech() {}
                    @Override public void onRmsChanged(float rmsdB) {}
                    @Override public void onBufferReceived(byte[] buffer) {}
                    @Override public void onEndOfSpeech() {}

                    @Override public void onError(int code) {
                        error.set("recognizer error=" + code);
                        done.countDown();
                    }

                    @Override public void onResults(Bundle results) {
                        String text = bestText(results);
                        if (!text.isEmpty()) result.set(text);
                        done.countDown();
                    }

                    @Override public void onPartialResults(Bundle partialResults) {}

                    @Override public void onEvent(int eventType, Bundle params) {}

                    @Override public void onSegmentResults(Bundle segmentResults) {
                        String text = bestText(segmentResults);
                        if (text.isEmpty()) return;
                        synchronized (segmented) {
                            if (segmented.length() > 0) segmented.append("\n");
                            segmented.append(text);
                        }
                    }

                    @Override public void onEndOfSegmentedSession() {
                        synchronized (segmented) {
                            if (segmented.length() > 0) {
                                result.set(segmented.toString());
                            }
                        }
                        done.countDown();
                    }
                });

                Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                intent.putExtra(
                        RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ja-JP");
                intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false);
                intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, readFd);
                intent.putExtra(
                        RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT,
                        Math.max(1, spec.channels));
                intent.putExtra(
                        RecognizerIntent.EXTRA_AUDIO_SOURCE_ENCODING,
                        AudioFormat.ENCODING_PCM_16BIT);
                intent.putExtra(
                        RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE,
                        Math.max(8000, spec.sampleRate));
                intent.putExtra(
                        RecognizerIntent.EXTRA_SEGMENTED_SESSION,
                        RecognizerIntent.EXTRA_AUDIO_SOURCE);
                recognizer.startListening(intent);
            } catch (Throwable t) {
                error.set(t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()));
                done.countDown();
            }
        });

        Thread decoder = new Thread(() -> {
            try (FileOutputStream pcm = new FileOutputStream(writeFd.getFileDescriptor())) {
                decodeToPcm16(file, pcm);
                pcm.flush();
            } catch (Throwable t) {
                error.compareAndSet(
                        "",
                        "decode " + t.getClass().getSimpleName()
                                + ": " + String.valueOf(t.getMessage()));
            } finally {
                try { writeFd.close(); } catch (Throwable ignored) {}
            }
        }, "fap-audio-file-decode");
        decoder.setDaemon(true);
        decoder.start();

        try {
            long wait = Math.max(5_000L, Math.min(180_000L, timeoutMs));
            done.await(wait, TimeUnit.MILLISECONDS);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        } finally {
            try { readFd.close(); } catch (Throwable ignored) {}
            main.post(() -> {
                SpeechRecognizer recognizer = recognizerRef.getAndSet(null);
                if (recognizer != null) {
                    try { recognizer.cancel(); } catch (Throwable ignored) {}
                    try { recognizer.destroy(); } catch (Throwable ignored) {}
                }
            });
        }

        String text = result.get().trim();
        if (!text.isEmpty()) {
            if (text.length() > 30_000) {
                text = text.substring(0, 30_000) + "\n…[transcript truncated]";
            }
            return "音声文字起こし(on-device)\n" + text;
        }
        String failure = error.get();
        return failure.isEmpty()
                ? "音声文字起こし: timeout / no speech result"
                : "音声文字起こし: " + failure;
    }

    private static String bestText(Bundle results) {
        if (results == null) return "";
        ArrayList<String> values = results.getStringArrayList(
                SpeechRecognizer.RESULTS_RECOGNITION);
        if (values == null) return "";
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return "";
    }

    private static AudioSpec inspect(File file) throws Exception {
        MediaExtractor extractor = new MediaExtractor();
        try {
            extractor.setDataSource(file.getAbsolutePath());
            int track = findAudioTrack(extractor);
            if (track < 0) throw new IllegalArgumentException("no audio track");
            MediaFormat format = extractor.getTrackFormat(track);
            String mime = format.getString(MediaFormat.KEY_MIME);
            int rate = format.containsKey(MediaFormat.KEY_SAMPLE_RATE)
                    ? format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                    : 16000;
            int channels = format.containsKey(MediaFormat.KEY_CHANNEL_COUNT)
                    ? format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                    : 1;
            return new AudioSpec(rate, channels, mime == null ? "" : mime);
        } finally {
            extractor.release();
        }
    }

    private static int findAudioTrack(MediaExtractor extractor) {
        for (int i = 0; i < extractor.getTrackCount(); i++) {
            MediaFormat format = extractor.getTrackFormat(i);
            String mime = format.getString(MediaFormat.KEY_MIME);
            if (mime != null && mime.startsWith("audio/")) return i;
        }
        return -1;
    }

    private static void decodeToPcm16(File file, FileOutputStream output) throws Exception {
        MediaExtractor extractor = new MediaExtractor();
        MediaCodec codec = null;
        try {
            extractor.setDataSource(file.getAbsolutePath());
            int track = findAudioTrack(extractor);
            if (track < 0) throw new IllegalArgumentException("no audio track");
            extractor.selectTrack(track);
            MediaFormat format = extractor.getTrackFormat(track);
            String mime = format.getString(MediaFormat.KEY_MIME);
            if (mime == null) throw new IllegalArgumentException("audio mime missing");

            if (Build.VERSION.SDK_INT >= 24) {
                try {
                    format.setInteger(
                            MediaFormat.KEY_PCM_ENCODING,
                            AudioFormat.ENCODING_PCM_16BIT);
                } catch (Throwable ignored) {
                }
            }

            codec = MediaCodec.createDecoderByType(mime);
            codec.configure(format, null, null, 0);
            codec.start();

            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            boolean inputDone = false;
            boolean outputDone = false;
            long started = System.currentTimeMillis();

            while (!outputDone) {
                if (System.currentTimeMillis() - started > 170_000L) {
                    throw new IllegalStateException("decode timeout");
                }

                if (!inputDone) {
                    int inputIndex = codec.dequeueInputBuffer(10_000);
                    if (inputIndex >= 0) {
                        ByteBuffer input = codec.getInputBuffer(inputIndex);
                        if (input == null) continue;
                        input.clear();
                        int size = extractor.readSampleData(input, 0);
                        if (size < 0) {
                            codec.queueInputBuffer(
                                    inputIndex,
                                    0,
                                    0,
                                    0L,
                                    MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputDone = true;
                        } else {
                            long timeUs = extractor.getSampleTime();
                            codec.queueInputBuffer(
                                    inputIndex,
                                    0,
                                    size,
                                    Math.max(0L, timeUs),
                                    0);
                            extractor.advance();
                        }
                    }
                }

                int outputIndex = codec.dequeueOutputBuffer(info, 10_000);
                if (outputIndex >= 0) {
                    ByteBuffer buffer = codec.getOutputBuffer(outputIndex);
                    if (buffer != null && info.size > 0) {
                        buffer.position(info.offset);
                        buffer.limit(info.offset + info.size);
                        byte[] data = new byte[info.size];
                        buffer.get(data);
                        output.write(data);
                    }
                    outputDone = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
                    codec.releaseOutputBuffer(outputIndex, false);
                }
            }
        } finally {
            if (codec != null) {
                try { codec.stop(); } catch (Throwable ignored) {}
                try { codec.release(); } catch (Throwable ignored) {}
            }
            extractor.release();
        }
    }
}
