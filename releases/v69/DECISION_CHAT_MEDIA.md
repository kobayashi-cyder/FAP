# Decision — V69 Chat + Media

Current decision: MODIFY / pending clean same-HEAD CI.

Focused Chat/Image/Audio tests pass independently on Python 3.11 and 3.12.

The first broad historical-suite run exposed one pre-existing/environment-sensitive V68
baseline failure: `test_real_subprocess_fixture_one_trial` expected
`ram_source=measured_peak_rss` but the CI environment reported `artifact_supplied`.
This candidate does not modify `releases/v68/**`.

Promotion gate therefore requires, on the same candidate HEAD:
- all focused V69 interaction tests;
- V66 operational 28/28;
- V67 code-factory 28/28;
- V68 code-factory 34/34;
- compileall on V69 interaction.

The historical RSS-source mismatch remains a separately recorded baseline issue and must
not be misrepresented as a V69 regression.

Real image generation, STT, and TTS remain DEFER until concrete provider adapters are
independently exercised. Half-duplex voice is the only voice-session baseline in scope.

Rollback: return to main V68 `929c419b3fcff55720e159b8f7f7f1d602dec305`
and remove/disable the additive V69 interaction package.
