# TEST PREP — V75 Managed Chat

Required:
- status/clear/undo controls do not invoke responder;
- mode command plus legacy mode commands;
- max exchange count preserves user/assistant pairs;
- context character budget prunes oldest full pairs;
- large response returned full but stored copy clipped;
- single latest exchange forced inside storage budget;
- oversized/empty input rejection;
- status does not contain message content;
- compileall;
- V74/V73/V72/V71/V70/V69 regressions;
- V66/V67/V68 core regressions;
- Python 3.11/3.12 independent CI.
