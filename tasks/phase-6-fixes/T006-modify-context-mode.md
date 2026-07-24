# T006 — Context-mode handoff redesign (deferred)

## Status
**Blocked on T004 results.** Do not start until the T004 pilot shows
whether the T001 archive fix alone changes branch outcomes. Right now the
bigger problem is that the archive rarely holds a genuinely advanced state
to hand off at all (T001); refining *what we tell the child* about a state
is a secondary lever.

## Context if unblocked
Current modes (`go_explore/continuations.py` `ContextMode`):
`original_task_only`, `parent_summary`, `critical_parent_summary`,
`failure_symptom`, `none`. `failure_symptom` was added most recently
(see git log) specifically to tell a child what the parent already tried
without inheriting the parent's possibly-flawed reasoning wholesale.

## Open questions to answer only after T004
- Does `context_mode=none` (restored sandbox, no narrative) actually cause
  redundant re-attempts of already-failed approaches, or does the restored
  file state alone make that moot?
- Does `failure_symptom` measurably reduce token usage vs `none` for the
  same solve rate, per T004 data?
- Is there evidence a new mode is needed, or is picking a default between
  the four existing modes sufficient?

## Do not
Do not design or implement a new context mode speculatively. This ticket
exists to hold the question, not to be worked before T004 has results.
