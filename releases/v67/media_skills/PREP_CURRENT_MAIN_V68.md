# Media Foundation — current-main preparation addendum

Base reviewed: main `929c419b3fcff55720e159b8f7f7f1d602dec305` (V68). Existing PREP is stale because it names V66.

Next safe step: keep a provider-neutral `MediaRequest -> ProviderAdapter -> MediaArtifact` contract isolated from V68's TaskPlan/code-factory pipeline. Expected interfaces must reject absent provider, malformed request, timeout/error, empty bytes, wrong MIME and digest mismatch. Artifacts require SHA-256 and bounded metadata; no provider secret or user media body belongs in repository evidence.

Android: no new permission in foundation; concrete mic/storage/network permissions belong to leaf adapters. Measure request/record size, validation latency and peak memory. Promotion requires deterministic negative tests plus independently exercised concrete adapters before any generation claim.

DEFER provider-specific SDKs, Android lifecycle logic and streaming. REPLACE this contract if a current-main interface already provides equivalent typed request/artifact semantics with independent tests. Sibling media branches remain isolated and are not merge prerequisites.