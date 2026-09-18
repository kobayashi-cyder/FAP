# Decision — V69 Chat + Media

Decision: KEEP for main integration review.

Independent GitHub Actions on the same candidate lineage passed on Python 3.11 and 3.12:
- focused V69 Chat/Image/Audio interaction tests: PASS;
- compileall for V69 interaction: PASS;
- V66 operational regression: 28/28 PASS;
- V67 code-factory regression: 28/28 PASS;
- V68 code-factory regression: 34/34 PASS.

The earlier broad historical-suite run exposed one pre-existing/environment-sensitive V68
baseline issue in `test_real_subprocess_fixture_one_trial`: CI reported
`ram_source=artifact_supplied` instead of `measured_peak_rss`. This candidate does not
modify `releases/v68/**`; the issue remains separately visible rather than being hidden by
weakened tests.

Included main-ready surface:
- bounded chat session with brief/normal/rich/verbose modes;
- provider-neutral image generation contract with artifact/MIME/digest verification;
- PCM16 audio input + STT boundary;
- TTS audio output boundary;
- half-duplex STT -> responder -> TTS voice turn;
- fail-closed missing-provider/timeout/error/empty/wrong-MIME paths.

Limitations:
Real image generation, transcription and synthesis remain provider-dependent and are not
claimed until concrete adapters are independently exercised. Full duplex, barge-in, echo
cancellation, wake word and streaming remain DEFER.

Rollback: return to main V68 `929c419b3fcff55720e159b8f7f7f1d602dec305`
and remove/disable the additive V69 interaction package.
