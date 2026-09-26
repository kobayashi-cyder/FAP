# TEST PREP — V73 Provider Capability Probe

Required:
- healthy all-capability response canonicalization;
- subset capability gating;
- ready=false;
- protocol mismatch;
- duplicate and unknown capability rejection;
- timeout and provider nonzero-exit classification;
- assert probe protocol sends no user/media content;
- compileall;
- V72/V71/V70/V69 regressions;
- V66/V67/V68 core regressions;
- Python 3.11/3.12 independent CI.

Healthy control-plane probe is not sufficient for real generation/STT/TTS claims.
