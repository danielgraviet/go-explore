# Returning to Development States

The original hypothesis is archived at
[docs/archive-docs/essay-original-hypothesis.md](archive-docs/essay-original-hypothesis.md).
Do not treat that draft as the current claim. Evidence for every sentence
below is in [docs/claim-ledger.md](claim-ledger.md).

## One Sentence

Coding-agent progress lives in the sandbox, not only in the transcript.
Daytona snapshots let us return to that state. Returning is not enough:
inherited files can trap the next agent, handoff has a token tax, and
under a fixed budget independent retries currently solve more
Terminal-Bench tasks.

## Abstract

Coding agents often make useful progress before they fail. They install
dependencies, reproduce failures, identify files, generate artifacts, and
write partial fixes. Most retry systems discard this work.

We adapted Go-Explore to software engineering by treating a full Daytona
sandbox snapshot as the reusable search state: save intermediate machines,
rank them in an archive, and fork a new agent into a selected snapshot.
Restore is reliable. On easy Terminal-Bench anchors, 24/24 continuations
verified against a live snapshot and solved at parity with clean attempts.
On a pre-registered harder subset, the rescue mechanism sometimes fired,
but independent retries still won: 17/25 versus 6/25.

The result is a characterization, not a method win. Full-sandbox restore
makes environment-level search possible. It does not, under a matched
token budget and the selectors we tested, beat retry-from-scratch.
Failures are structured: budget fragmentation, wrong-state attractors,
handoff tax, and unverified selector signals.

## Claims

1. Full Daytona snapshots are a reliable unit of restore for coding-agent
   search.
2. Under a matched token budget, Go-Explore-style branching does not beat
   independent retries on the screened Terminal-Bench subset we tested.
3. Failure is structured, not random.
4. Whether full snapshots beat compressed start states (diff, transcript,
   command replay) is Experiment A and is not claimed until that run
   completes. See
   [docs/experiments/claim1-representation-ablation.md](experiments/claim1-representation-ablation.md).

## What This Project Is For

The Daytona blog and the workshop paper share this thesis. The blog tells
the engineering story: snapshots as mid-task search nodes. The paper
freezes the headline protocol numbers and adds the representation
ablation and recovery replication. Neither artifact may fill in the
original essay's `[X%]` / `[Y%]` solve-rate gains.
