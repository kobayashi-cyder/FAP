package jp.fap.runtime;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

public final class AndroidVoiceController {
    public interface Listener {
        void onStatus(String status);
        void onPartial(String text);
        void onFinal(String text, float confidence);
        void onError(String message, boolean recoverable);
    }

    private enum VoiceState {
        IDLE,
        LISTENING,
        SPEAKING,
        CLOSED
    }

    private static final long RESTART_DELAY_MS = 240L;
    private static final long BUSY_REBUILD_DELAY_MS = 480L;
    private static final long BARGE_IN_ARM_DELAY_MS = 520L;
    private static final int MAX_RECOVERY_STREAK = 8;
    private static final int TTS_CHUNK_CHARS = 72;

    private final Activity activity;
    private final Listener listener;
    private final Handler main = new Handler(Looper.getMainLooper());

    private SpeechRecognizer recognizer;
    private TextToSpeech tts;

    private VoiceState state = VoiceState.IDLE;
    private boolean closed = false;
    private boolean continuousMode = false;
    private boolean onDeviceRecognizer = false;
    private boolean ttsReady = false;
    private boolean recognizerListening = false;
    private boolean bargeInArmed = false;
    private boolean bargeInTriggered = false;
    private int recoveryStreak = 0;

    private long recognizerGeneration = 0L;
    private String currentSpeechText = "";
    private String finalUtteranceId = "";
    private Runnable speechDone;

    public AndroidVoiceController(Activity activity, Listener listener) {
        this.activity = activity;
        this.listener = listener;
        initializeTts();
        rebuildRecognizer(false);
    }

    public boolean isRecognitionAvailable() {
        return !closed && SpeechRecognizer.isRecognitionAvailable(activity);
    }

    public boolean isTtsReady() {
        return ttsReady && !closed;
    }

    public boolean isContinuousMode() {
        return continuousMode && !closed;
    }

    public String capabilitySummary() {
        String stt;
        if (!SpeechRecognizer.isRecognitionAvailable(activity)) {
            stt = "STT=unavailable";
        } else {
            stt = onDeviceRecognizer ? "STT=on-device" : "STT=system";
        }
        String ttsState = ttsReady ? "TTS=ready" : "TTS=initializing";
        return stt + " · " + ttsState + " · continuous="
                + (continuousMode ? "ON" : "OFF") + " · locale=ja-JP";
    }

    public void startContinuous() {
        if (closed) return;
        continuousMode = true;
        recoveryStreak = 0;
        startListeningInternal(false);
    }

    public void stopContinuous() {
        continuousMode = false;
        stopAll();
    }

    public void startListening() {
        if (closed) return;
        startListeningInternal(false);
    }

    public void stopListening() {
        cancelRecognizer();
        if (state == VoiceState.LISTENING) state = VoiceState.IDLE;
    }

    public void speak(String text, Runnable onDone) {
        if (closed) {
            if (onDone != null) onDone.run();
            return;
        }

        String value = text == null ? "" : text.trim();
        if (value.isEmpty() || !ttsReady || tts == null) {
            if (onDone != null) onDone.run();
            if (continuousMode) scheduleListen(RESTART_DELAY_MS);
            return;
        }

        cancelRecognizer();
        state = VoiceState.SPEAKING;
        bargeInArmed = false;
        bargeInTriggered = false;
        currentSpeechText = normalize(value);
        speechDone = onDone;

        List<String> chunks = splitForSpeech(value, TTS_CHUNK_CHARS);
        if (chunks.isEmpty()) {
            finishSpeech(false);
            return;
        }

        finalUtteranceId = "fap-" + UUID.randomUUID();
        for (int i = 0; i < chunks.size(); i++) {
            String id = i == chunks.size() - 1
                    ? finalUtteranceId
                    : finalUtteranceId + "-p" + i;
            int queueMode = i == 0 ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD;
            int rc = tts.speak(chunks.get(i), queueMode, null, id);
            if (rc != TextToSpeech.SUCCESS) {
                listener.onError("TTS rejected utterance", true);
                finishSpeech(false);
                return;
            }
        }
    }

    public void stopSpeaking() {
        if (tts != null) {
            try {
                tts.stop();
            } catch (Throwable ignored) {
            }
        }
        currentSpeechText = "";
        finalUtteranceId = "";
        bargeInArmed = false;
        bargeInTriggered = false;
        speechDone = null;
        if (state == VoiceState.SPEAKING) state = VoiceState.IDLE;
    }

    public void stopAll() {
        cancelRecognizer();
        stopSpeaking();
        main.removeCallbacksAndMessages(null);
        if (!closed) state = VoiceState.IDLE;
    }

    public void close() {
        if (closed) return;
        continuousMode = false;
        closed = true;
        state = VoiceState.CLOSED;
        main.removeCallbacksAndMessages(null);
        cancelRecognizer();
        destroyRecognizer();
        if (tts != null) {
            try {
                tts.stop();
                tts.shutdown();
            } catch (Throwable ignored) {
            }
            tts = null;
        }
        ttsReady = false;
    }

    private void startListeningInternal(boolean duringSpeech) {
        if (closed) return;
        if (!SpeechRecognizer.isRecognitionAvailable(activity)) {
            listener.onError("Speech recognition unavailable", false);
            return;
        }
        if (recognizer == null) {
            rebuildRecognizer(false);
        }
        if (recognizer == null) {
            listener.onError("No speech recognizer", false);
            return;
        }

        try {
            if (recognizerListening) {
                recognizer.cancel();
                recognizerListening = false;
            }
            recognizer.startListening(recognitionIntent());
            recognizerListening = true;
            if (!duringSpeech) state = VoiceState.LISTENING;
            listener.onStatus(
                    duringSpeech
                            ? "VOICE · barge-in ready"
                            : "VOICE · listening · " + capabilitySummary());
        } catch (Throwable t) {
            recognizerListening = false;
            recoverRecognizer("startListening: " + shortError(t), true);
        }
    }

    private Intent recognitionIntent() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ja-JP");
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "ja-JP");
        intent.putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, "ja-JP");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5);
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
        intent.putExtra(
                RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS,
                520L);
        intent.putExtra(
                RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS,
                320L);
        intent.putExtra(
                RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS,
                120L);
        return intent;
    }

    private void rebuildRecognizer(boolean afterFailure) {
        if (closed) return;
        destroyRecognizer();
        final long generation = ++recognizerGeneration;

        try {
            if (Build.VERSION.SDK_INT >= 31
                    && SpeechRecognizer.isOnDeviceRecognitionAvailable(activity)) {
                recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(activity);
                onDeviceRecognizer = true;
            } else {
                recognizer = SpeechRecognizer.createSpeechRecognizer(activity);
                onDeviceRecognizer = false;
            }
            recognizer.setRecognitionListener(new RecognitionListener() {
                @Override public void onReadyForSpeech(Bundle params) {
                    if (generation != recognizerGeneration || closed) return;
                    recognizerListening = true;
                    if (state != VoiceState.SPEAKING) {
                        state = VoiceState.LISTENING;
                        listener.onStatus("VOICE · listening · " + capabilitySummary());
                    }
                }

                @Override public void onBeginningOfSpeech() {
                    if (generation != recognizerGeneration || closed) return;
                    if (state == VoiceState.SPEAKING) {
                        listener.onStatus("VOICE · interruption candidate");
                    } else {
                        listener.onStatus("VOICE · hearing");
                    }
                }

                @Override public void onRmsChanged(float rmsdB) { }

                @Override public void onBufferReceived(byte[] buffer) { }

                @Override public void onEndOfSpeech() {
                    if (generation != recognizerGeneration || closed) return;
                    if (state != VoiceState.SPEAKING || bargeInTriggered) {
                        listener.onStatus("VOICE · recognizing");
                    }
                }

                @Override public void onError(int error) {
                    if (generation != recognizerGeneration || closed) return;
                    recognizerListening = false;
                    handleRecognizerError(error);
                }

                @Override public void onResults(Bundle results) {
                    if (generation != recognizerGeneration || closed) return;
                    recognizerListening = false;
                    handleResults(results);
                }

                @Override public void onPartialResults(Bundle partialResults) {
                    if (generation != recognizerGeneration || closed) return;
                    String partial = bestText(partialResults);
                    if (partial.isEmpty()) return;

                    if (state == VoiceState.SPEAKING) {
                        if (!bargeInArmed) return;
                        if (looksLikeTtsEcho(partial)) return;
                        if (!bargeInTriggered) {
                            bargeInTriggered = true;
                            try {
                                if (tts != null) tts.stop();
                            } catch (Throwable ignored) {
                            }
                            currentSpeechText = "";
                            finalUtteranceId = "";
                            speechDone = null;
                            state = VoiceState.LISTENING;
                            listener.onStatus("VOICE · interrupted");
                        }
                    }
                    listener.onPartial(partial);
                }

                @Override public void onEvent(int eventType, Bundle params) { }
            });

            if (afterFailure) {
                listener.onStatus(
                        "VOICE · recognizer rebuilt · "
                                + (onDeviceRecognizer ? "on-device" : "system"));
            }
        } catch (Throwable t) {
            recognizer = null;
            onDeviceRecognizer = false;
            listener.onError("Recognizer init: " + shortError(t), false);
        }
    }

    private void handleResults(Bundle results) {
        String text = bestText(results);
        float confidence = bestConfidence(results);

        if (text.isEmpty()) {
            if (state == VoiceState.SPEAKING) scheduleBargeIn();
            else scheduleListen(RESTART_DELAY_MS);
            return;
        }

        if (state == VoiceState.SPEAKING && !bargeInTriggered) {
            if (looksLikeTtsEcho(text)) {
                scheduleBargeIn();
                return;
            }
            bargeInTriggered = true;
            try {
                if (tts != null) tts.stop();
            } catch (Throwable ignored) {
            }
            currentSpeechText = "";
            finalUtteranceId = "";
            speechDone = null;
            state = VoiceState.IDLE;
        }

        recoveryStreak = 0;
        state = VoiceState.IDLE;
        listener.onFinal(text, confidence);
    }

    private void handleRecognizerError(int error) {
        if (closed) return;

        boolean quietRetry = error == SpeechRecognizer.ERROR_NO_MATCH
                || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT;

        if (quietRetry) {
            if (state == VoiceState.SPEAKING) scheduleBargeIn();
            else if (continuousMode) scheduleListen(RESTART_DELAY_MS);
            return;
        }

        boolean rebuild = error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY
                || error == SpeechRecognizer.ERROR_CLIENT
                || (Build.VERSION.SDK_INT >= 31
                    && error == SpeechRecognizer.ERROR_SERVER_DISCONNECTED);
        boolean recoverable = rebuild
                || error == SpeechRecognizer.ERROR_NETWORK
                || error == SpeechRecognizer.ERROR_NETWORK_TIMEOUT
                || error == SpeechRecognizer.ERROR_SERVER
                || error == SpeechRecognizer.ERROR_TOO_MANY_REQUESTS;

        if (!recoverable) {
            listener.onError("STT error=" + error, false);
            return;
        }

        recoverRecognizer("STT error=" + error, rebuild);
    }

    private void recoverRecognizer(String reason, boolean rebuild) {
        recoveryStreak += 1;
        if (recoveryStreak > MAX_RECOVERY_STREAK) {
            listener.onError(reason + " · recovery limit reached", false);
            continuousMode = false;
            return;
        }

        listener.onStatus("VOICE · recovering · " + reason);
        long delay = rebuild ? BUSY_REBUILD_DELAY_MS : RESTART_DELAY_MS;
        main.postDelayed(() -> {
            if (closed) return;
            if (rebuild) rebuildRecognizer(true);
            if (state == VoiceState.SPEAKING) {
                scheduleBargeIn();
            } else if (continuousMode) {
                startListeningInternal(false);
            }
        }, delay);
    }

    private void initializeTts() {
        tts = new TextToSpeech(activity, status -> {
            if (closed) return;
            if (status != TextToSpeech.SUCCESS) {
                ttsReady = false;
                listener.onError("TTS initialization failed", false);
                return;
            }

            int language = tts.setLanguage(Locale.JAPAN);
            ttsReady = language != TextToSpeech.LANG_MISSING_DATA
                    && language != TextToSpeech.LANG_NOT_SUPPORTED;
            if (!ttsReady) {
                listener.onError("Japanese TTS voice unavailable", false);
                return;
            }

            tts.setSpeechRate(1.06f);
            tts.setPitch(1.0f);
            listener.onStatus("VOICE · " + capabilitySummary());
        });

        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String utteranceId) {
                activity.runOnUiThread(() -> {
                    if (closed) return;
                    state = VoiceState.SPEAKING;
                    listener.onStatus("VOICE · speaking");
                    if (continuousMode && !bargeInArmed) {
                        main.postDelayed(() -> {
                            if (closed || state != VoiceState.SPEAKING) return;
                            bargeInArmed = true;
                            startListeningInternal(true);
                        }, BARGE_IN_ARM_DELAY_MS);
                    }
                });
            }

            @Override public void onDone(String utteranceId) {
                if (!utteranceId.equals(finalUtteranceId)) return;
                activity.runOnUiThread(() -> finishSpeech(true));
            }

            @Override public void onError(String utteranceId) {
                if (!utteranceId.equals(finalUtteranceId)) return;
                activity.runOnUiThread(() -> {
                    listener.onError("TTS playback error", true);
                    finishSpeech(false);
                });
            }
        });
    }

    private void finishSpeech(boolean completed) {
        if (closed) return;
        cancelRecognizer();
        currentSpeechText = "";
        finalUtteranceId = "";
        bargeInArmed = false;
        bargeInTriggered = false;
        state = VoiceState.IDLE;

        Runnable done = speechDone;
        speechDone = null;
        listener.onStatus(completed ? "VOICE · reply finished" : "VOICE · reply stopped");
        if (done != null) done.run();

        if (continuousMode) scheduleListen(RESTART_DELAY_MS);
    }

    private void scheduleListen(long delayMs) {
        if (!continuousMode || closed) return;
        main.postDelayed(() -> {
            if (!continuousMode || closed || state == VoiceState.SPEAKING) return;
            startListeningInternal(false);
        }, delayMs);
    }

    private void scheduleBargeIn() {
        if (!continuousMode || closed || state != VoiceState.SPEAKING) return;
        main.postDelayed(() -> {
            if (!continuousMode || closed || state != VoiceState.SPEAKING) return;
            bargeInArmed = true;
            startListeningInternal(true);
        }, BARGE_IN_ARM_DELAY_MS);
    }

    private void cancelRecognizer() {
        if (recognizer == null) {
            recognizerListening = false;
            return;
        }
        try {
            if (recognizerListening) recognizer.cancel();
        } catch (Throwable ignored) {
        }
        recognizerListening = false;
    }

    private void destroyRecognizer() {
        if (recognizer != null) {
            try {
                recognizer.cancel();
            } catch (Throwable ignored) {
            }
            try {
                recognizer.destroy();
            } catch (Throwable ignored) {
            }
        }
        recognizer = null;
        recognizerListening = false;
    }

    private String bestText(Bundle results) {
        if (results == null) return "";
        ArrayList<String> matches = results.getStringArrayList(
                SpeechRecognizer.RESULTS_RECOGNITION);
        if (matches == null) return "";
        for (String match : matches) {
            if (match != null && !match.trim().isEmpty()) return match.trim();
        }
        return "";
    }

    private float bestConfidence(Bundle results) {
        if (results == null) return 0.0f;
        float[] scores = results.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES);
        if (scores == null || scores.length == 0 || scores[0] < 0.0f) return 0.0f;
        return Math.max(0.0f, Math.min(1.0f, scores[0]));
    }

    private boolean looksLikeTtsEcho(String heard) {
        String h = normalize(heard);
        String t = currentSpeechText;
        if (h.length() < 2 || t.isEmpty()) return false;
        if (t.contains(h)) return true;

        int shared = 0;
        int samples = Math.min(12, h.length());
        for (int i = 0; i < samples; i++) {
            char c = h.charAt(i);
            if (t.indexOf(c) >= 0) shared += 1;
        }
        return samples >= 6 && ((double) shared / (double) samples) >= 0.83;
    }

    private static List<String> splitForSpeech(String text, int maxChars) {
        ArrayList<String> out = new ArrayList<>();
        String value = text == null ? "" : text.trim();
        if (value.isEmpty()) return out;

        StringBuilder buffer = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            buffer.append(ch);

            boolean punctuation = "。！？!?、,；;：:".indexOf(ch) >= 0;
            if ((punctuation && buffer.length() >= 8) || buffer.length() >= maxChars) {
                String piece = buffer.toString().trim();
                if (!piece.isEmpty()) out.add(piece);
                buffer.setLength(0);
            }
        }

        String rest = buffer.toString().trim();
        if (!rest.isEmpty()) out.add(rest);
        return out;
    }

    private static String normalize(String value) {
        if (value == null) return "";
        return value
                .toLowerCase(Locale.JAPAN)
                .replaceAll("[\\s、。！？!?.,，．・「」『』（）()【】\"]", "")
                .trim();
    }

    private static String shortError(Throwable t) {
        String s = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage());
        return s.length() > 180 ? s.substring(0, 180) : s;
    }
}
