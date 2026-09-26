# TEST PREP — V76 Android Python Packaging

Required:
- deterministic repeated sync/report;
- stale destination replacement;
- missing source rejected before destination mutation;
- duplicate destination rejection;
- path escape rejection;
- missing __init__.py rejection;
- symlink source/tree rejection;
- invalid destination rejection;
- actual repository manifest sync into a temporary Python asset directory;
- compileall of the synchronized real package set;
- assert all seven V69-V75 package destinations exist;
- V75/V74/V73/V72/V71/V70/V69 regressions;
- V66/V67/V68 core regressions;
- Python 3.11/3.12 independent CI.

Post-promotion evidence:
- main-triggered Android APK build succeeds;
- APK_INFO records the interaction package manifest SHA-256.

Do not claim Android runtime/UI usage from packaging evidence alone.
