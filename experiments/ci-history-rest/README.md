# MAUI CI-history REST experiment

This is a review example, not a production scanner or a service deployment.
It packages the consumer boundary from a closed cross-repository history spike
and runs **new synthetic data through real loopback HTTP**. It does not replay
the original historical corpus. No workflow, shipping default, dependency
manifest, build selection, or PR-attribution policy changes.

## Problem and integration seam

Repeated history reads can discover candidate failures, but an indexed match
is not verified case identity, and an absent match is not a pass. MAUI still
needs original results, current timelines, and exact test failure blocks.
A published `Passed` result can have overwritten an earlier failure.

At the audited fork base `828569a86489228dc66a7867173635a6fb4f27be`:

- [`Get-PipelineHistory`](../../.github/skills/review-test-failures/scripts/Gather-TestFailureContext.ps1#L2329)
  selects explicit target-branch builds via `Get-RecentTargetBranchBuilds`.
  Its historical loop calls `Get-BuildLogTestFailures` and
  `Get-PublicBuildFailureEvidence` at lines 2405-2408. The caller at line 4297
  passes the PR's base branch. This is the existing history-evidence boundary,
  **not a currently pluggable REST provider**.
- The scanner's
  [data-source and classification rules](../../.github/workflows/ci-status-main.md#L1126)
  retain anonymous build/timeline/log reads and Helix console interpretation.
  Authenticated result reads from the spike are not approved for that workflow.

The earlier local prototype's `phase2.question` called `HttpHistory.question`
before checking original run/result/build IDs and the original automated name,
run configuration, failure outcome, and exact error. Its
`history_baseline` then examined **every build minus verified positives**,
not just builds absent from the index. Those prototype files are not shipped
here. [`MauiHistory.question`](maui_adapter.py) and `evaluate` demonstrate that
boundary with synthetic originals and logs, without wiring it into either
production caller.

The adapter uses the canonical case projection unchanged. It passes an explicit
build list, `outcome: "Failed"`, and exact test, arguments, opaque argument hash,
pipeline, queue, run, friendly work-item, and case-sensitive error predicates.
The raw indexed name is never "repaired" into the original case name. Available
physical references stay unverified source references, not execution counts.
`inventory` uses `allOutcomes: true`, not a guessed list of outcomes.

## Run locally

Use Python 3.10+ and the standard library. Obtain the canonical shared example
from **PureWeen/aspnetcore**, under `experiments/ci-history-rest`, alongside
this checkout. The immutable canonical commit pin will be added before
publication. The shared root contains the sole OpenAPI, client, validator,
and fixture service; MAUI does not carry a second implementation.

Once both source checkouts are available, these commands are offline except
for an owned `127.0.0.1` listener:

```sh
SHARED_ROOT=../aspnetcore/experiments/ci-history-rest
python3 -B experiments/ci-history-rest/demo.py --shared-root "$SHARED_ROOT"
python3 -B experiments/ci-history-rest/test_demo.py --shared-root "$SHARED_ROOT" -v
```

`--shared-root` is required and must point to trusted canonical code. No source
credentials, external service, package install, environment proxy, or remote
API is needed. The shared context manager generates a temporary local-only
credential and tears down its listener and credential after each run.
The approved contract's SHA-256 is
`a3f63bb1d6d11455ca7fe569431051cfac88bd0427752247b5cd8962e9e7fe7e`.
The shared harness checks those exact contract bytes.

[`synthetic.py`](synthetic.py) supplies invented builds 101-106. Expected output:

| Evidence | Build IDs |
|---|---|
| Indexed exact failures | 101, 102 |
| Original parent identity verified | 101 |
| Required fallback, including the unverified indexed candidate | 102, 103, 104, 105, 106 |
| Failure recovered from a FAIL-then-PASS log | 103 |
| Combined positive observations | 101, 103 |
| Still unknown | 102, 104, 105, 106 |

Build 102 has the wrong original case. Build 103 has only a published `Passed`
index row. Build 104 has a different indexed queue; build 105 has a different
case-sensitive error; build 106 has no indexed row. The latter three do not
become passes. Missing or unlinked logs remain unknown. The parser confines the
error to the exact test's failure block, including stopping at a later pass.
Current-build evidence is passed through unchanged; no historical observation
establishes the current head, current attempt, or PR-versus-existing verdict.

The tests exercise exact matching, unresolved references, duplicate rows,
empty versus missing values, all-unmatched fallback, overwritten failures,
log isolation, unchanged current evidence, atomic 502/503 errors, propagated
transport failure, and owned listener/credential cleanup. Failure never becomes
an empty successful result. Synthetic linkage flags are inputs, not proof that
production timeline or source identity verification has been implemented.

## What the closed spike established

The [public proposal](https://gist.github.com/PureWeen/b0dc2dc71a9a6c789130b0a5b3327aa0)
provides cross-repository context. The retained MAUI results were seven indexed
UI positives, then **nine of eleven after original evidence and all four
fallback builds**. Two fallback builds had FAIL then PASS with a final published
`Passed` outcome. The device question matched **three of three positive builds
with five parent references**. The separate inventory surface had 271 main
groups, 321 net11 groups, and 66 reference observations. These are bounded
results, not universal parity, passing denominators, or execution counts.

All four repositories passed one final whole HTTP replay. Successful live
components were collected separately; two failed dependency-503 whole-live
invocations remain failed. SDK was integration-only: six of seven indexed
memberships, unchanged eight dossiers, and all 233 logical GETs / 52 unique
requests under synthetic suppression. It demonstrated zero source work removed.

This public synthetic suite is separate from the older 333-HTTP / 338-check
boundary suite. Historical fixture source-path/hash correspondence remains
unsupported. No raw captures, private reports, internal service configuration,
or historical receipt rewrites are included.

## Reviewer questions and adoption limits

Does the proposed provider boundary keep original case checks and every
unverified build's fallback visible? Is the distinction between indexed,
verified, missing, and unknown evidence clear enough for a future caller?
Which approved anonymous enrichment source could satisfy the existing
scanner's authentication restrictions?

Production authentication, hosting, SLOs, complete ingestion, lossless identity,
snapshot/currentness and first-attempt semantics, pass denominators, and full
collector substitution remain unproven. Existing log interpretation,
current-build evidence, branch/window selection, PR-attribution policy,
thresholds, and publication decisions stay with existing callers. This example
does not authorize adoption or change GitHub Actions/settings.
