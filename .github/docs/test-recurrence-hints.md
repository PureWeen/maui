# Experimental test-recurrence hints

**DO NOT MERGE: provider shape only; no behavior change (`provider=none`).**

`Get-CiScanRecurrenceHints.ps1` is a consumer-side placeholder for **a supported
test-history service; none exists for public CI today**. It makes no network
requests, obtains no credentials, selects no builds, and publishes nothing.
The only other provider, `fixture`, is for offline tests and must not be enabled
in workflows.

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
public CI or GitHub Actions access path. This PR implements no live adapter.

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
