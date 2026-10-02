# Experimental test-recurrence hints

**DO NOT MERGE: no certified replacement; no CI behavior change (`provider=none`).**

`Get-CiScanRecurrenceHints.ps1` has a consumer-side placeholder for **a supported
test-history service; none exists for public CI today**. Default `none` and
test-only `fixture` obtain no credentials and make no network requests.
Opt-in `kusto` is a **local developer experiment**, not a public CI provider.
Nothing publishes issues or changes the scanner's CI default.

The scanner's existing agent-directed lookback remains the consumer, in
`ci-status-main.md` and `ci-status-net11.md` under "Pipelines to scan". Current
failure discovery, diagnosis/classification, original evidence links, the
recurrence threshold, and publication are unchanged.

## Contract

After discovering a test failure from frozen original evidence and selecting the
same prior builds as today, materialize this request (example values):

```json
{
  "schema_version": 1,
  "key": {
    "definition_id": 314,
    "test_name": "GlideStaticEqualsGlideGet",
    "arguments": "",
    "argument_hash": "",
    "queue_name": "ubuntu.2204.amd64.android.33.open",
    "test_run_name": "DeviceTestsAndroid_CoreCLR_ubuntu.2204.amd64.android.33.open_Release_CoreCLR",
    "signature": "System.NullReferenceException : Arg_NullReferenceException"
  },
  "prior_build_ids": [1605031, 1605107]
}
```

```powershell
pwsh -NoProfile -File .github/scripts/Get-CiScanRecurrenceHints.ps1 --provider none --input request.json --output hints.json
```

The result repeats the key and has one `{build_id, state, reason}` hint per
distinct selected prior build. `none` returns **UNKNOWN for every build**.
`RECURRED` means an existential observation of the exact test, arguments,
configuration/run and failure signature in that build, not complete ingestion
or complete test coverage. Missing, ambiguous, errored, mixed, passed-on-rerun
and nonmatching observations are UNKNOWN and require original logs.
A failed original fallback stays incomplete, never "not recurring".

The deterministic workflow step bootstraps an empty `none` hint file because
the current freeze stores raw evidence, not parsed test keys or selected prior
IDs. It does not invent either selection. With this disabled marker, the agent
checks every selected prior build exactly as before, without invoking PowerShell
or widening its existing command allowlist. The per-key invocation above
demonstrates the local consumer contract after discovery/window selection, not
a live service integration. Do not use hints for build breaks, crashes,
deadletters or current-build inventory. Counts deduplicate build IDs.
Keep the scanner's original timestamp source; First seen is window-bounded,
not all-time, and must not come from a provider test-run timestamp.

## Offline fixtures and public pilot

Fixtures under `.github/scripts/fixtures/ci-scan-recurrence-*.json` are **small
synthetic consumer-contract records**, based on public AzDO/Helix observations;
they contain no raw Kusto output, credentials, index schema or result references.
The separate `original` section is used only by tests, never provider eligibility.
The Issue33038 fixture is an **OLD September routing control**, not new coverage
evidence: missing/final-passed cases 1595567, 1597560, 1599656 and 1600800 fall
back, preserving 9/11 positives.

A developer-authenticated local pilot, outside this PR, compared fresh anonymous
original evidence with a retained history query on public definition-314 builds
[1605031](https://dev.azure.com/dnceng-public/public/_build/results?buildId=1605031),
[1605107](https://dev.azure.com/dnceng-public/public/_build/results?buildId=1605107)
and [1605518](https://dev.azure.com/dnceng-public/public/_build/results?buildId=1605518).
It bound the signature to the selected test's own failure block and checked the
final attempt of 1605107. Both paths returned those three distinct builds,
`N=3`, threshold true, and earliest-in-window AzDO `build.finishTime`
`2026-09-21T12:02:16.8695081Z` (a disclosed pilot convention).

| Pilot ledger | Requests | Response-body bytes |
|---|---:|---:|
| Original baseline | 21 | 17,849,433 |
| Modeled routed path | 10 | 5,160,778 |
| Actual experiment total | 22 | 17,853,705 |

Conservative omitted retrievals: **10 reads / 6.18 MB** (timeline, submission,
Helix details, workitems and core console for each prior build). The upper bound
is **12 reads / 12.69 MB**, only if the original agent reads every failed console
to locate the test. Common metadata/current-evidence reuse is not avoided
traffic. The retained query was charged once to modeled routing and actual
total. These are response-body bytes, not measured model-token or wire savings.
This selected sample does not establish production integration or general coverage.

Public Arcade documentation describes `Engsrvprod/engineeringdata`,
`AzureDevOpsTests`, and its sparse collection of `Failed`, `PassedOnRerun` and
`NotExecuted` outcomes, without initial passing rows:
[TestReportingData.md](https://github.com/dotnet/arcade/blob/7042280515eb35cea60b5ba5026825e4674746d9/Documentation/AzureDevOps/TestReportingData.md).
[TestReportingQueries.md](https://github.com/dotnet/arcade/blob/7042280515eb35cea60b5ba5026825e4674746d9/Documentation/AzureDevOps/TestReportingQueries.md)
states that access is Microsoft-employee-only. Developer access is not a
public CI or GitHub Actions access path.

## Local Kusto preflight

Python 3 and Azure CLI are required only for the opt-in local provider.
Use the existing scanner freeze's `latest-build-inventory.json`; do not recreate
current failures from the sparse Kusto index. Real evidence and output must be
outside the checkout.

```bash
az login
pwsh -NoProfile -File .github/scripts/Get-CiScanRecurrenceHints.ps1 --provider kusto --inventory /tmp/maui-history/latest-build-inventory.json --branch net11.0 --cache-root /tmp/maui-history/evidence --output /tmp/maui-history/hints.json
```

The local preflight lists anonymous public `resultsbybuild` failures, reads
known-ID result/run details, extracts explicit configuration, selects ten earlier
completed builds by finish time, and makes at most one history query per lane.
Ten is a disclosed deterministic interpretation of the prompt's "~10", not
an existing production function. A newer build does not change the frozen latest
ID. The build-list response must still contain that ID and all ten predecessors.

Public run/result *listing* can redirect to sign-in even when individual
result/run *details* work anonymously. Missing queue, theory arguments or
failure message leaves a current failure unkeyed and requires the original path.
An absent queue is never treated as a known empty queue.
The live JSON is version 2, with pipeline status, unkeyed-failure diagnostics,
per-key signatures, selected prior IDs and individual hints. Consumers must
ignore a key if their signature/configuration differs.

Signature normalization `trim-lines-preserve-content-v1` replaces CRLF,
trims each line's indentation/trailing whitespace and removes empty lines.
It preserves case, punctuation, paths, numeric IDs, durations and inline spaces.
Missing, over-limit, ANSI-containing or explicitly truncated messages cannot
produce positives. Whole normalized messages must agree; no fuzzy matching.

Exact failed index rows can produce internal **RECURRED** candidates only when their
references and full keys agree with public completed failed-run details.
Completed runs include earlier attempts; this is not proof of the final build attempt.
Identical re-ingestion
duplicates collapse; conflicting rows, mixed outcomes, errors and pagination
doubt produce **UNKNOWN**. **NOT_RECURRED is not enabled**: per-run statistics
cannot prove the complete build run set or historical failures overwritten by
final Passed results. Unkeyed failures, uncovered builds and unknown hints must
use today's logs. Original current inventory and diagnosis remain mandatory.
**No live positive is certified.** The consumer therefore converts every
candidate positive to **UNKNOWN** with an explicit uncertified diagnostic.
The local transport works, but this is additive research: **zero original reads
are currently demonstrated avoidable**.

The standard credential flow obtains an Azure CLI credential in process memory
and sends it only to `engsrvprod`'s Kusto query service. It is never printed,
stored in the evidence cache, put in an environment file, or included in receipts.
Authentication/HTTP/TLS errors stay distinct from a successful query with no rows.
Requests have time/size limits, reject redirects and share a persistent maximum
of **30 query attempts / 2,000,000,000 response-body bytes**. Failed attempts count.
Cache receipts include payload hashes and observed retrieval times; a cached
comparison is a frozen replay, not fresh evidence of ingestion coverage.
`--offline` on the local PowerShell command prohibits authentication and new
downloads; it is only for replaying a complete external cache.

## Corpus comparison

Freeze twenty completed builds for each definition 302/313/314 on main/net11.0
using the scanner's public build-list filters. Name those six external files
`builds-{definition}-{branch}.json`. The validator simulates each first-ten build
as latest against its ten earlier builds, includes unkeyed current failures in
its accounting, and reuses one query per lane across overlapping windows.

```bash
python3 -B .github/scripts/Validate-CiScanKusto.py --windows /tmp/maui-history/windows --cache-root /tmp/maui-history/evidence --output /tmp/maui-history/comparison
python3 -B -m unittest discover -s .github/scripts -p 'test_ci_scan_kusto.py' -v
```

G1 compares public exact-key/signature results for each pair; incomplete public
keys cannot prove absence. G2 binds signatures to the selected test's own failure
block in final-attempt AzDO/Helix evidence for every positive hint. Errors and
incomplete run linkage are **unavailable proof**, not agreement. Any known
disagreement stops the comparison. A completed *candidate* comparison is not
automatically certification or permission to skip logs.
The report separates original-log, public-structured and Kusto download ledgers.
It does not call modeled omission "skipped". Run-completion versus retained
ingestion timestamps describe observed rows only, not coverage or availability
of missing rows. No complete original-log end-to-end equivalence is claimed for
unkeyed/fallback cases.

### Certification stopped: attempt/rerun mismatch

The corpus froze twenty builds per lane (120 builds total) for definitions
302/313/314 on main/net11.0, planning sixty latest-build simulations.
An initial candidate replay enumerated 1,132 failed-result records: 1,107 could
not supply an exact queue/signature key. Twenty-five usable latest-key instances
produced 250 prior pairs, with 222 UNKNOWN candidates (88.8%). These are
**candidate/replay counts, not certified log omissions**.

The correctly configured original-log comparison **stopped at the first unsafe
case**, while visiting simulation 44 and pair 16:
[latest 1617729](https://dev.azure.com/dnceng-public/public/_build/results?buildId=1617729)
versus [prior 1603563](https://dev.azure.com/dnceng-public/public/_build/results?buildId=1603563).
Kusto and public structured results agree on a **Failed attempt 1**, completed
September 19. The selected original timeline/Helix job is **attempt 2**,
completed September 20; the selected test is **PASS** in its console and the
normalized signature is absent from all five real work-item consoles.
The sixth `/workitems` entry is controller bookkeeping, not an omitted test
console; `InitialWorkItemCount` is five.

There is one result for the selected test in the failed run, and a separate
**Passed** result with the same test/configuration in attempt 2. No iteration or
attachment explained the discrepancy. The local candidate failed to bind the
public run attempt to the final original job attempt: **this is a mapping defect,
not an index/source disagreement and not a proven original-scanner blind spot**.
The pinned oracle was preserved. The suggestion to read every exit-zero console
was diagnostic-only and was not adopted as a changed baseline.

| Replacement | Corpus agreement | Unsafe disagreements | Demonstrated reads/bytes avoided |
|---|---|---:|---:|
| Historical exact positive membership | **Not certified**; attempt 1 disagrees with selected attempt 2 | **1** | **0 / 0** |
| Absence, N, >=2, First seen, Occurrences | **Uncertified**; original-path comparison stopped | Not evaluated completely | **0 / 0** |

**Uncertified:** final-attempt mapping, current-key discovery when public fields
are absent, NOT_RECURRED/coverage, complete original-path end-to-end outputs,
and all other scanner fetches. The OLD Issue33038 control remains old evidence.

The entire collection/replays/diagnostic used seven Kusto attempts and
20,827,607 downloaded response-body bytes, including the initial anonymous probe.
These are **actual validation costs**, not three measured execution alternatives:

| Actual validation ledger | Requests | Response-body bytes |
|---|---:|---:|
| Kusto | 7 | 3,700,600 |
| Public structured results/run details and root-cause reads | 3,891 | 13,996,771 |
| Original timeline/log/Helix evidence and diagnostic consoles | 78 | 2,335,255 |
| Initial anonymous access probe | 26 | 794,981 |

The final bounded root-cause step used **0 Kusto queries / 2,218,229 bytes**.
Observed retained ingestion timestamp minus run completion ranged from
45.68 seconds to 62,238.02 seconds (median 2,090.45 seconds over 3,272 deduplicated
rows). This is **not** a coverage/availability guarantee for absent rows.

**REST implication:** no validated replacement can yet specify a shipping call.
Public AzDO already exposes outcomes and run attempts; a supported batched
history service must preserve that attempt identity, bind each result to the
selected final timeline/Helix job (or provide an explicit final-attempt marker),
and report trustworthy coverage. An unscoped batch of Failed rows is insufficient.
This evidence does not justify removing any field from the shared API proposal.

## Local checks

```powershell
pwsh -NoProfile -Command 'Invoke-Pester -Path .github/scripts/Get-CiScanRecurrenceHints.Tests.ps1,.github/scripts/CiScanTrustedInventory.Tests.ps1,.github/scripts/Validate-CiScanPublisher.Tests.ps1 -Output Normal -CI'
```

Compile both scanner locks only with the repository-pinned gh-aw version
(v0.86.2), never by hand:

```bash
# gh-aw-v0.86.2 denotes the checksum-verified release binary.
gh-aw-v0.86.2 compile ci-status-main ci-status-net11 --no-check-update
gh-aw-v0.86.2 compile ci-status-main ci-status-net11 --no-emit --no-check-update
```
