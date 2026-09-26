# FAP Native UI

This is the browser UI for `1.0.01-cpp-native-r002`.

The interface has two independent paths:

1. **Native trace** — C++ core compiled to WebAssembly runs in the browser and
   reports route selection, adaptive compute budget, extra-path activation and
   multi-intent detection.
2. **Conversation API** — when `/api/v1/chat` is available, the UI forwards
   the user message to the existing FAP conversation runtime and renders its
   reply/artifacts.

The UI therefore remains diagnostically useful even if the Python/API runtime
is offline.

## Build the native browser runtime

Activate Emscripten, then from the repository root:

```bash
bash native_cpp/ui/build_wasm.sh
```

The command emits `fap_native.js`, `fap_native.wasm` and, when the knowledge
directory is present, the Emscripten data preload beside this UI.

Serve the folder through HTTP; browsers generally do not permit a complete WASM
startup from `file://`.

Example:

```bash
python -m http.server 8080 --directory native_cpp/ui
```

Then open `http://127.0.0.1:8080/`.

The conversation API field defaults to `http://127.0.0.1:11439`, matching the
existing FAP chat UI. Turn on **Native only** to avoid API calls.
