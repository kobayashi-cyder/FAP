# FCA cross-pollination

FAP remains FAP. This candidate imports one specific FCA idea: **sparse capability activation**.

Before the planner sees capabilities, an optional selector may reduce the visible set using
relevance, expected value, information gain and execution cost. This is intended to reduce
unnecessary provider/tool activation while leaving FAP's Goal Completion Loop, critic and
hard-stop semantics intact.

The selector is fail-closed:
- empty selection is rejected;
- unregistered capabilities are rejected;
- a planner action using a filtered-out capability is rejected.

The shared `fca-fap.exchange.v1` capsule records provenance and constraints.
