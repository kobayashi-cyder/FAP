package jp.fap.v59;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;

import java.util.ArrayList;
import java.util.Locale;
import java.util.UUID;

public final class AndroidVoiceController {
    public interface Listener {
        void onStatus(String status);
        void onPartial(String text);
        void onFinal(String text, float confidence);
        void onError(String message, boolean recoverable);
    }

    private final Activity activity;
    private final Listener listener;
    private SpeechRecognizer recognizer;
    private TextToSpeech tts;
    private boolean ttsReady = false;
    private boolean listening = false;
    private boolean closed = false;
    private boolean onDeviceRecognizer = false;
    private Runnable speechDone;

    public AndroidVoiceController(Activity activity, Listener listener) {
        this.activity = activity;
        this.listener = listener;
        initializeTts();
        initializeRecognizer();
    }

    public boolean isRecognitionAvailable() {
        return !closed && SpeechRecognizer.isRecognitionAvailable(activity);
    }

    public boolean isTtsReady() {
        return ttsReady && !closed;
    }

    public String capabilitySummary() {
        String stt;
        if (!SpeechRecognizer.isRecognitionAvailable(activity)) {
            stt = "STT=unavailable";
        } else {
            stt = onDeviceRecognizer ? "STT=on-device" : "STT=system";
        }
        String voice = ttsReady ? "TTS=ready" : "TTS=initializing";
        return stt + " · " + voice + " · locale=ja-JP";
    }

    private void initializeRecognizer() {
        if (closed || !SpeechRecognizer.isRecognitionAvailable(activity)) {
            listener.onStatus("VOICE · speech recognition unavailable");
            return;
        }
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
                    listening = true;
                    listener.onStatus("VOICE · listening · " + capabilitySummary());
                }

                @Override public void onBeginningOfSpeech() {
                    listener.onStatus("VOICE · hearing");
                }

                @Override public void onRmsChanged(float rmsdB) { }

                @Override public void onBufferReceived(byte[] buffer) { }

                @Override public void onEndOfSpeech() {
                    listener.onStatus("VOICE · recognizing");
                }

                @Override public void onError(int error) {
                    listening = false;
                    boolean recoverable = error == SpeechRecognizer.ERROR_NO_MATCH
                            || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT
                            || error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY
                            || error == SpeechRecognizer.ERROR_CLIENT;
                    listener.onError("STT error=" + error, recoverable);
                }

                @Override public void onResults(Bundle results) {
                    listening = false;
                    ArrayList<String> matches = results.getStringArrayList(
                            SpeechRecognizer.RESULTS_RECOGNITION);
                    float[] scores = results.getFloatArray(
                            SpeechRecognizer.CONFIDENCE_SCORES);
                    if (matches == null || matches.isEmpty()
                            || matches.get(0) == null || matches.get(0).trim().isEmpty()) {
                        listener.onError("STT returned no text", true);
                        return;
                    }
                    float confidence = 0.0f;
                    if (scores != null && scores.length > 0 && scores[0] >= 0.0f) {
                        confidence = Math.max(0.0f, Math.min(1.0f, scores[0]));
                    }
                    listener.onFinal(matches.get(0).trim(), confidence);
                }

                @Override public void onPartialResults(Bundle partialResults) {
                    ArrayList<String> matches = partialResults.getStringArrayList(
                            SpeechRecognizer.RESULTS_RECOGNITION);
                    if (matches != null && !matches.isEmpty() && matches.get(0) != null) {
                        listener.onPartial(matches.get(0).trim());
                    }
                }

                @Override public void onEvent(int eventType, Bundle params) { }
            });
        } catch (Throwable t) {
            recognizer = null;
            onDeviceRecognizer = false;
            listener.onError("Recognizer init: " + shortError(t), false);
        }
    }

    private Intent recognitionIntent() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ja-JP");
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "ja-JP");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3);
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
        return intent;
    }

    public void startListening() {
        if (closed) return;
        stopSpeaking();
        if (recognizer == null) {
            initializeRecognizer();
        }
        if (recognizer == null) {
            listener.onError("No speech recognizer", false);
            return;
        }
        try {
            if (listening) {
                recognizer.cancel();
                listening = false;
            }
            recognizer.startListening(recognitionIntent());
        } catch (Throwable t) {
            listening = false;
            listener.onError("Start listening: " + shortError(t), true);
        }
    }

    public void stopListening() {
        if (recognizer == null) return;
        try {
            recognizer.cancel();
        } catch (Throwable ignored) { }
        listening = false;
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
            if (ttsReady) {
                // Slightly above the platform default reduces turn latency while
                // remaining intelligible on common Japanese voices.
                tts.setSpeechRate(1.05f);
                tts.setPitch(1.0f);
                listener.onStatus("VOICE · " + capabilitySummary());
            } else {
                listener.onError("Japanese TTS voice unavailable", false);
            }
        });
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String utteranceId) {
                activity.runOnUiThread(
                        () -> listener.onStatus("VOICE · speaking"));
            }

            @Override public void onDone(String utteranceId) {
                Runnable done = speechDone;
                speechDone = null;
                activity.runOnUiThread(() -> {
                    listener.onStatus("VOICE · reply finished");
                    if (done != null) done.run();
                });
            }

            @Override public void onError(String utteranceId) {
                Runnable done = speechDone;
                speechDone = null;
                activity.runOnUiThread(() -> {
                    listener.onError("TTS playback error", true);
                    if (done != null) done.run();
                });
            }
        });
    }

    public void speak(String text, Runnable onDone) {
        if (closed) {
            if (onDone != null) onDone.run();
            return;
        }
        String value = text == null ? "" : text.trim();
        if (value.isEmpty() || !ttsReady) {
            if (onDone != null) onDone.run();
            return;
        }
        stopListening();
        speechDone = onDone;
        String utteranceId = "fap-" + UUID.randomUUID();
        int rc = tts.speak(value, TextToSpeech.QUEUE_FLUSH, null, utteranceId);
        if (rc != TextToSpeech.SUCCESS) {
            Runnable done = speechDone;
            speechDone = null;
            listener.onError("TTS rejected utterance", true);
            if (done != null) done.run();
        }
    }

    public void stopSpeaking() {
        if (tts == null) return;
        try {
            tts.stop();
        } catch (Throwable ignored) { }
        speechDone = null;
    }

    public void stopAll() {
        stopListening();
        stopSpeaking();
    }

    public void close() {
        if (closed) return;
        closed = true;
        stopAll();
        if (recognizer != null) {
            try {
                recognizer.destroy();
            } catch (Throwable ignored) { }
            recognizer = null;
        }
        if (tts != null) {
            try {
                tts.shutdown();
            } catch (Throwable ignored) { }
            tts = null;
        }
    }

    private static String shortError(Throwable t) {
        String s = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage());
        return s.length() > 180 ? s.substring(0, 180) : s;
    }
}
