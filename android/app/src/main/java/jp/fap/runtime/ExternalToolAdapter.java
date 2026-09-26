package jp.fap.runtime;

import android.content.Context;

import org.json.JSONObject;

/**
 * Pluggable boundary for authenticated external services.
 * Concrete adapters keep credentials outside FAP's core runtime and expose
 * only explicit actions after the user has connected the provider.
 */
public interface ExternalToolAdapter {
    String id();
    String displayName();
    boolean isConnected(Context context);
    JSONObject invoke(Context context, String action, JSONObject args) throws Exception;
}
