#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_URL="${FAP_REPO_URL:-https://github.com/kobayashi-cyder/FAP.git}"
REF="${FAP_REF:-side/1.0.01-pixel-browser-runtime-20260926}"
DEST="${1:-$HOME/fap-pixel-min}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required. In Termux: pkg install git" >&2
  exit 10
fi

if [ -e "$DEST" ]; then
  echo "Destination already exists: $DEST" >&2
  exit 11
fi

git clone --filter=blob:none --depth 1 --no-checkout --branch "$REF" "$REPO_URL" "$DEST"
cd "$DEST"
git sparse-checkout init --no-cone

cat > .git/info/sparse-checkout <<'EOF'
/android/
/android_packaging/sync_pixel_runtime.py
/knowledge/
/fap_1x_runtime.py
/fap_1x_standard_runtime.py
/fap_discourse_context.py
/fap_dynamic_sparse_routing.py
/fap_exponential_linear.py
/fap_factual_qa.py
/fap_generic_derivation.py
/fap_generic_rule_reasoner.py
/fap_interaction_fabric.py
/fap_reflective_conversation.py
/fap_response_explorers.py
/fap_response_redundancy.py
/fap_response_series_executor.py
/fap_response_specialists.py
/fap_response_specialists_extra.py
/fap_semantic_conversation.py
/fap_semantic_memory.py
/fap_speech.py
/.github/workflows/pixel-1-0-01-apk-verify.yml
EOF

git checkout "$REF"

echo "FAP Pixel minimal source fetched:"
git rev-parse --short HEAD
du -sh . 2>/dev/null || true
echo
echo "This checkout is the minimal Pixel source/runtime set."
echo "The APK is built by the Pixel 1.0.01 APK Verify workflow on GitHub."
