# TEST PREP — V74 Health-gated Runtime

Required:
- chat works without a provider probe;
- unprobed media is blocked before provider invocation;
- unhealthy probe blocks invocation;
- undeclared capability blocks invocation;
- healthy declared capability invokes exactly once;
- voice requires both STT and TTS;
- unconfigured provider remains needs_provider;
- status combines configured and probed state;
- compileall;
- V73/V72/V71/V70/V69 regressions;
- V66/V67/V68 core regressions;
- Python 3.11/3.12 independent CI.
