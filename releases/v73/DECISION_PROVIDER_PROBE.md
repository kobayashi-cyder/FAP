# Decision — V73 Provider Capability Probe

Decision: KEEP for main integration review.

Independent GitHub Actions passed on Python 3.11 and 3.12:
- V73 provider-probe focused tests: PASS;
- V72 lifecycle regression: PASS;
- V71 runtime regression: PASS;
- V70 provider-adapter regression: PASS;
- V69 interaction regression: PASS;
- V66 operational 28/28 PASS;
- V67 code-factory 28/28 PASS;
- V68 code-factory 34/34 PASS;
- compileall PASS.

The probe sends only operation name and protocol version. It classifies healthy,
unavailable, incompatible and error states, rejects duplicate/unknown capability claims, and
derives image/STT/TTS/half-duplex gates only from a healthy response.

Limitation: a healthy control-plane probe is not proof of real image/STT/TTS data-plane
quality. Concrete provider output still requires independent evidence.

Rollback anchor: main V72 `69f04a36efb33287542d58cff88ff27440db334d`.
