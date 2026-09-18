# Audio Input / STT Skill — PREP

Status: isolated non-main lane, refreshed against actual `main@de4ed52e1b5c7d5a505f5ee5ca8d88110fa6bf15`. Roadmaps are non-binding; sibling media branches remain separate.

Next safe step: separate bounded microphone lifecycle from STT. Provider-neutral PCM input is baseline. Claim a concrete STT adapter only after independent exact-backend evidence; otherwise DEFER transcription. Streaming, wake-word, full-duplex, barge-in and echo cancellation remain later capabilities.

Expected interfaces: bounded `AudioInputSpec`, `MicSession` start/stop/cancel/close, PCM frame owner, `SttAdapter`, `TranscriptResult`, typed lifecycle/provider errors, redacted evidence record and focused tests. Android microphone code owns platform APIs and permission; provider SDK/protocol stays behind `SttAdapter`.

Negative tests: permission denied/revoked, mic busy, start-stop races, lifecycle cancellation, double close, stale callback, empty/truncated/oversized PCM, unsupported sample rate/channels, timeout/provider failure, empty/oversized transcript, buffer budget+1, temp-file leak, and accidental content/credential logging. Fail closed.

Android/privacy/resources: request `RECORD_AUDIO` only for explicit capture; release platform handles on stop/cancel/lifecycle loss/error. Capture-only work does not require audio focus. Raw audio/transcripts are ephemeral by default, content logging off, persistence opt-in. Measure startup/stop and STT latency where applicable, peak RSS delta, buffer high-water mark, retained storage bytes (default zero), and repeated-cycle handle/RAM growth; unsupported metrics are `unavailable`.

Promotion: platform lifecycle needs permission/race/stale-callback tests plus repeated start-stop cleanup evidence on representative Android/host runtime. STT additionally needs exact adapter/backend independent invocation with bounded metadata and measured resources. Existing prototype tests are not real STT evidence.

DEFER STT without real backend evidence. REPLACE/split if capture and provider concerns leak across boundaries, buffers become unbounded, lifecycle cleanup fails, retention becomes implicit, or resource growth/regression is unexplained.