# Image Generation Skill — PREP

Status: non-main experimental lane.

## Guaranteed scope
- Validate prompt, dimensions, output format, optional seed.
- Produce a deterministic request plan.
- Refuse to claim success when no renderer/provider is configured.
- Verify returned artifact is non-empty image media and expose SHA-256 evidence.

## Next implementation steps
1. Add provider timeout/error taxonomy and retry budget.
2. Add content-addressed artifact manifest with source prompt digest and provider metadata.
3. Add Android/local adapter contract without embedding provider secrets.
4. Add optional edit/inpaint request schema separately from text-to-image.
5. Measure latency/RAM/storage and artifact validation failure rate.

## Promotion evidence
- unit/negative tests including malformed prompt/dimensions/format;
- provider failure and wrong-MIME tests;
- deterministic request serialization;
- no API keys in repository/logs;
- one independently verified real provider adapter before claiming actual generation support.

Local prototype verification before upload: combined media prototype suite 12/12 PASS. Branch still requires CI/provider integration evidence.
