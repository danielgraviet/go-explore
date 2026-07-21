# Fixed-Budget Task Set

This document freezes the first Terminal-Bench task set for the paper-grade
fixed-budget experiments. It is based on locally cached Harbor metadata on
2026-07-21, before seeing outcomes from the main benchmark.

The selection goal is task-level evidence across diverse task families, not
many repeats of a tiny task set.

## Metadata Check

Validation command:

```bash
uv run python -m go_explore.cli list-cached-tasks
```

Observed local cache:

| Field | Count |
| --- | ---: |
| Raw cached task entries | 91 |
| Unique task names | 90 |
| Easy tasks | 5 |
| Medium tasks | 55 |
| Hard tasks | 30 |
| Medium tasks with agent timeout <= 1200 sec | 41 |
| Medium tasks with agent timeout <= 1800 sec | 47 |

The raw cache includes `chess-best-move` twice, so task counts below use unique
task names.

## Inclusion Rules

Primary tasks must satisfy:

- Terminal-Bench task available in the local Harbor cache.
- Difficulty is `medium`.
- Agent timeout is at most 1800 seconds.
- Category mix covers software engineering, security, data processing,
  debugging, file operations, scientific computing, model work, and system
  administration.
- The task is likely to expose useful intermediate state such as installed
  dependencies, inspected files, generated artifacts, tests, or partial fixes.

Tasks are excluded from the primary set when they are:

- `easy`, because the pilot showed easy tasks can saturate quickly and leave
  little headroom.
- `hard`, because the first main run should avoid confounding snapshot value
  with very low base solve rate.
- Medium but very long timeout, unless needed later for a fallback category.
- Known infrastructure-heavy from metadata alone, such as very long build or
  VM-style tasks.

## Smoke Subset

Run this subset before launching the full primary set. It covers the known
harness canary plus five medium tasks that should exercise different artifact
and command patterns.

| Task | Difficulty | Category | Agent timeout | Rationale |
| --- | --- | --- | ---: | --- |
| `fix-git` | easy | software-engineering | 900 | Known Daytona snapshot harness canary; not part of main evidence. |
| `regex-log` | medium | data-processing | 900 | Fast log parsing task with inspect/edit/test loops. |
| `git-leak-recovery` | medium | software-engineering | 900 | Git state should make snapshot reuse meaningful. |
| `openssl-selfsigned-cert` | medium | security | 900 | Bounded artifact generation with deterministic verifier. |
| `sqlite-db-truncate` | medium | debugging | 900 | Debugging task likely to create useful intermediate diagnosis state. |
| `qemu-startup` | medium | system-administration | 900 | Exercises system setup without a long timeout. |

Smoke pass condition: all methods can write manifests, raw jobs, event logs,
analysis tables, and warnings. The smoke does not need to show snapshot lift.

## Primary Task Set

The primary set contains 43 unique medium tasks. All have agent timeout at or
below 1800 seconds.

| Task | Difficulty | Category | Agent timeout | Verifier timeout | Inclusion rationale |
| --- | --- | --- | ---: | ---: | --- |
| `regex-log` | medium | data-processing | 900 | 900 | Command-line parsing and repeated validation. |
| `log-summary-date-ranges` | medium | data-processing | 900 | 900 | Data summarization with inspect-transform-check loops. |
| `multi-source-data-merger` | medium | data-processing | 900 | 900 | Multi-file data integration and validation. |
| `financial-document-processor` | medium | data-processing | 1200 | 1200 | Document extraction with artifact generation. |
| `hf-model-inference` | medium | data-science | 900 | 900 | Model API/script debugging without a long timeout. |
| `query-optimize` | medium | data-science | 900 | 900 | Iterative performance/debugging task. |
| `mteb-retrieve` | medium | data-science | 1800 | 1800 | Retrieval pipeline work with likely partial state. |
| `build-cython-ext` | medium | debugging | 900 | 900 | Build/debug loop with dependency and compiler state. |
| `merge-diff-arc-agi-task` | medium | debugging | 900 | 900 | Patch/merge debugging with testable artifacts. |
| `sqlite-db-truncate` | medium | debugging | 900 | 900 | Reproducible debugging and file-state inspection. |
| `custom-memory-heap-crash` | medium | debugging | 1800 | 1800 | Deeper diagnosis task while staying under timeout cap. |
| `db-wal-recovery` | medium | file-operations | 900 | 900 | File recovery task with valuable intermediate artifacts. |
| `extract-elf` | medium | file-operations | 900 | 900 | Binary/file inspection and deterministic output. |
| `large-scale-text-editing` | medium | file-operations | 1200 | 1200 | Large text transformation with partial progress states. |
| `caffe-cifar-10` | medium | machine-learning | 1200 | 1200 | ML environment task below timeout cap. |
| `count-dataset-tokens` | medium | model-training | 900 | 900 | Dataset processing and validation. |
| `pytorch-model-cli` | medium | model-training | 900 | 900 | CLI/model packaging task with runnable checks. |
| `pytorch-model-recovery` | medium | model-training | 900 | 900 | Recovery task with useful file/model state. |
| `modernize-scientific-stack` | medium | scientific-computing | 600 | 600 | Short scientific dependency modernization task. |
| `adaptive-rejection-sampler` | medium | scientific-computing | 900 | 900 | Numerical implementation with tests. |
| `raman-fitting` | medium | scientific-computing | 900 | 900 | Data fitting with script and output artifacts. |
| `tune-mjcf` | medium | scientific-computing | 900 | 900 | Structured file/model tuning with verification. |
| `dna-insert` | medium | scientific-computing | 1800 | 1800 | Bioinformatics-style transformation with larger search space. |
| `openssl-selfsigned-cert` | medium | security | 900 | 900 | Bounded security artifact generation. |
| `sanitize-git-repo` | medium | security | 900 | 900 | Git/file mutation task with strong snapshot fit. |
| `vulnerable-secret` | medium | security | 900 | 900 | Security debugging with deterministic checks. |
| `break-filter-js-from-html` | medium | security | 1200 | 1200 | Web/security transformation with inspect/test loops. |
| `crack-7z-hash` | medium | security | 900 | 900 | Security task with bounded computation. |
| `git-leak-recovery` | medium | software-engineering | 900 | 900 | Git history inspection should benefit from preserved state. |
| `headless-terminal` | medium | software-engineering | 900 | 900 | Terminal behavior task with iterative debugging. |
| `kv-store-grpc` | medium | software-engineering | 900 | 900 | Service implementation with tests and generated state. |
| `polyglot-c-py` | medium | software-engineering | 900 | 900 | Cross-language build/debug loop. |
| `pypi-server` | medium | software-engineering | 900 | 900 | Packaging/server workflow with setup reuse potential. |
| `code-from-image` | medium | software-engineering | 1200 | 1200 | Artifact reconstruction task with nontrivial intermediate state. |
| `git-multibranch` | medium | system-administration | 900 | 900 | Git branch operations with clear state lineage. |
| `nginx-request-logging` | medium | system-administration | 900 | 900 | Service configuration and verification. |
| `qemu-startup` | medium | system-administration | 900 | 900 | System setup task below timeout cap. |
| `sqlite-with-gcov` | medium | system-administration | 900 | 900 | Build/instrumentation task with reusable setup. |
| `qemu-alpine-ssh` | medium | system-administration | 900 | 900 | VM-like setup task kept because timeout is bounded. |
| `gcode-to-text` | medium | file-operations | 900 | 900 | File conversion task with deterministic output. |
| `largest-eigenval` | medium | mathematics | 900 | 900 | Numerical task with a distinct category. |
| `constraints-scheduling` | medium | personal-assistant | 1200 | 1200 | Constraint solving task with non-code reasoning pressure. |
| `chess-best-move` | medium | games | 900 | 900 | Distinct game/search category, already seen in smoke metadata. |

## Fallback Task Set

Use fallback tasks when a primary task is unavailable, repeatedly flaky, or
proves infrastructure-blocked before method outcomes are inspected. Replace
tasks within the same category where possible.

| Task | Difficulty | Category | Agent timeout | Verifier timeout | Use when |
| --- | --- | --- | ---: | ---: | --- |
| `rstan-to-pystan` | medium | data-science | 1800 | 1800 | A data-science task is blocked. |
| `filter-js-from-html` | medium | security | 1800 | 900 | A security/web transformation task is blocked. |
| `build-pmars` | medium | software-engineering | 900 | 900 | A software-engineering build task is blocked. |
| `mailman` | medium | system-administration | 1800 | 1800 | A system-administration task is blocked. |
| `mteb-leaderboard` | medium | data-science | 3600 | 3600 | Extra data-science coverage is worth higher cost. |
| `reshard-c4-data` | medium | data-science | 3600 | 3600 | Need data-pipeline coverage after shorter tasks are exhausted. |
| `distribution-search` | medium | machine-learning | 3600 | 3600 | Need additional ML coverage and can afford long timeout. |
| `portfolio-optimization` | medium | optimization | 3600 | 3600 | Need optimization category coverage. |
| `compile-compcert` | medium | system-administration | 2400 | 2400 | Need compiler/system setup coverage and can afford cost. |
| `schemelike-metacircular-eval` | medium | software-engineering | 2400 | 2400 | Need language/runtime implementation coverage. |
| `winning-avg-corewars` | medium | software-engineering | 3600 | 3600 | Need additional game-like programming coverage. |
| `build-pov-ray` | medium | software-engineering | 12000 | 12000 | Last-resort build task; very expensive. |

## Exclusions

These exclusions are based on metadata and pilot findings, not method outcomes.

### Easy Tasks

Easy tasks are kept for smoke tests only because the first live pilot on
`fix-git` solved too readily to measure branching lift.

| Task | Difficulty | Category | Reason |
| --- | --- | --- | --- |
| `hello-world` | easy | programming | Too easy; infrastructure canary only. |
| `fix-git` | easy | software-engineering | Known harness canary; too little headroom. |
| `overfull-hbox` | easy | debugging | Too easy for main evidence. |
| `cobol-modernization` | easy | software-engineering | Too easy for main evidence. |
| `prove-plus-comm` | easy | software-engineering | Too easy for main evidence. |

### Hard Tasks

Hard tasks are deferred until the medium-task harness produces stable tables.
They may be useful for a later stress experiment, but they should not be mixed
into the first fixed-budget comparison.

| Category | Deferred hard tasks |
| --- | --- |
| data-querying | `sparql-university` |
| data-science | `mcmc-sampling-stan`, `sam-cell-seg` |
| file-operations | `extract-moves-from-video` |
| machine-learning | `llm-inference-batching-scheduler` |
| mathematics | `model-extraction-relu-logits`, `feal-differential-cryptanalysis`, `feal-linear-cryptanalysis` |
| model-training | `train-fasttext` |
| scientific-computing | `dna-assembly`, `protein-assembly`, `bn-fit-modify` |
| security | `fix-code-vulnerability`, `password-recovery` |
| software-engineering | `cancel-async-tasks`, `gpt2-codegolf`, `make-doom-for-mips`, `polyglot-rust-c`, `torch-pipeline-parallelism`, `torch-tensor-parallelism`, `write-compressor`, `make-mips-interpreter`, `path-tracing`, `path-tracing-reverse`, `circuit-fibsqrt`, `fix-ocaml-gc`, `regex-chess` |
| system-administration | `configure-git-webserver`, `install-windows-3.11` |
| video-processing | `video-processing` |

### Cost-Deferred Medium Tasks

These are medium tasks but are not in the primary set because their timeout or
infrastructure profile makes them expensive for the first full pass. Some are
available in the fallback set.

| Task | Category | Agent timeout | Status |
| --- | --- | ---: | --- |
| `mteb-leaderboard` | data-science | 3600 | fallback |
| `reshard-c4-data` | data-science | 3600 | fallback |
| `distribution-search` | machine-learning | 3600 | fallback |
| `portfolio-optimization` | optimization | 3600 | fallback |
| `compile-compcert` | system-administration | 2400 | fallback |
| `schemelike-metacircular-eval` | software-engineering | 2400 | fallback |
| `winning-avg-corewars` | software-engineering | 3600 | fallback |
| `build-pov-ray` | software-engineering | 12000 | fallback only as last resort |

## Replacement Policy

If a primary task fails because of task availability, Daytona setup, external
dependency instability, or repeated verifier infrastructure failure, replace it
before inspecting method-level outcomes. Record the replacement in the benchmark
runbook with:

- blocked task,
- replacement task,
- reason,
- artifact path showing the blocker,
- whether any method outcome was observed before replacement.

Do not replace tasks because one method solved or failed them.

## Next Step

P4-T002 should generate fixed-budget manifests for the smoke subset first. If
the smoke produces complete analysis tables, run the primary set. If budget or
runtime is constrained, run the primary set in category-balanced batches and
preserve every manifest and output path.
