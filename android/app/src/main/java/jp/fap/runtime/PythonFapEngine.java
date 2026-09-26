package jp.fap.runtime;

import android.content.Context;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import org.json.JSONObject;

public final class PythonFapEngine {
    public static final class Result {
        public final String query;
        public final String answer;
        public final String skill;
        public final double confidence;
        public final String state;
        public final boolean needsTeacher;
        public final String payloadJson;

        Result(
                String query,
                String answer,
                String skill,
                double confidence,
                String state,
                boolean needsTeacher,
                String payloadJson) {
            this.query = query;
            this.answer = answer;
            this.skill = skill;
            this.confidence = confidence;
            this.state = state;
            this.needsTeacher = needsTeacher;
            this.payloadJson = payloadJson == null ? "{}" : payloadJson;
        }

        public boolean needsExternalHelp() {
            return needsTeacher
                    || !"handled".equals(state)
                    || answer == null
                    || answer.trim().isEmpty()
                    || confidence < 0.40;
        }
    }

    private final FapEngine fallback;
    private PyObject bridge;
    private String statusText = "STARTING";

    public PythonFapEngine(Context context) {
        fallback = new FapEngine(context);
        try {
            Python py = Python.getInstance();
            bridge = py.getModule("android_bridge");
            String raw = bridge.callAttr(
                    "initialize",
                    context.getFilesDir().getAbsolutePath()).toString();
            JSONObject init = new JSONObject(raw);
            statusText = init.optString("status", "READY · Python core");
        } catch (Throwable t) {
            bridge = null;
            statusText = "PYTHON CORE ERROR · Java fallback active · " + shortError(t);
        }
    }

    public synchronized Result process(String query) {
        return processAgent(query, "[]", "legacy");
    }

    public synchronized Result processAgent(
            String query,
            String recentLogJson,
            String sourceChannel) {
        if (bridge == null) {
            FapEngine.Result r = fallback.process(query);
            return new Result(
                    r.query,
                    r.answer,
                    "java_fallback:" + r.skill,
                    r.confidence,
                    "handled",
                    false,
                    "{}");
        }
        try {
            JSONObject o = new JSONObject(
                    bridge.callAttr(
                            "run_agent",
                            query,
                            recentLogJson == null ? "[]" : recentLogJson,
                            sourceChannel == null ? "agent" : sourceChannel)
                            .toString());
            statusText = o.optString("status", statusText);
            JSONObject payload = o.optJSONObject("payload");
            return new Result(
                    query,
                    o.optString("answer", ""),
                    o.optString("skill", "python_core"),
                    o.optDouble("confidence", 0.5),
                    o.optString("state", "unknown"),
                    o.optBoolean("needs_teacher", false),
                    payload == null ? "{}" : payload.toString()
            );
        } catch (Throwable t) {
            FapEngine.Result r = fallback.process(query);
            statusText = "PYTHON RUN ERROR · Java fallback active · " + shortError(t);
            return new Result(
                    r.query,
                    r.answer,
                    "java_fallback:" + r.skill,
                    r.confidence,
                    "handled",
                    false,
                    "{}");
        }
    }

    public synchronized void verify(Result result, boolean success) {
        if (bridge != null) {
            try {
                statusText = new JSONObject(
                        bridge.callAttr(
                                "verify",
                                result.query,
                                result.answer,
                                success).toString()
                ).optString("status", statusText);
                return;
            } catch (Throwable t) {
                statusText = "VERIFY ERROR · " + shortError(t);
            }
        }
        fallback.verify(
                new FapEngine.Result(
                        result.query,
                        result.answer,
                        result.skill,
                        result.confidence),
                success);
    }

    public synchronized void clear() {
        if (bridge != null) {
            try {
                statusText = new JSONObject(
                        bridge.callAttr("clear").toString())
                        .optString("status", "READY");
                return;
            } catch (Throwable ignored) { }
        }
        fallback.clear();
        statusText = fallback.status();
    }

    public synchronized JSONObject validateRuntime(String rootPath) throws Exception {
        if (bridge == null) {
            throw new IllegalStateException("Python bridge is unavailable");
        }
        String raw = bridge.callAttr("validate_runtime", rootPath).toString();
        return new JSONObject(raw);
    }

    public synchronized JSONObject reloadRuntime() throws Exception {
        if (bridge == null) {
            throw new IllegalStateException("Python bridge is unavailable");
        }
        JSONObject result = new JSONObject(
                bridge.callAttr("reload_runtime").toString());
        statusText = result.optString("status", statusText);
        return result;
    }

    public synchronized JSONObject configureMediaEndpoint(String endpoint) throws Exception {
        if (bridge == null) {
            throw new IllegalStateException("Python bridge is unavailable");
        }
        JSONObject result = new JSONObject(
                bridge.callAttr(
                        "configure_media",
                        endpoint == null ? "" : endpoint.trim())
                        .toString());
        statusText = result.optString("status", statusText);
        return result;
    }

    public synchronized String status() {
        if (bridge != null) {
            try {
                statusText = new JSONObject(
                        bridge.callAttr("status").toString())
                        .optString("status", statusText);
            } catch (Throwable ignored) { }
        }
        return statusText;
    }

    private static String shortError(Throwable t) {
        String s = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage());
        return s.length() > 180 ? s.substring(0, 180) : s;
    }
}
