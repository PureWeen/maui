#!/usr/bin/env python3
"""Local-only recurrence preflight. CI continues to use provider=none."""
import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE_SHA = "2067dd42c6032fbc40d2e46245806679a85df5e6"
AZDO = "https://dev.azure.com/dnceng-public/public"
RESULTS = "https://vstmr.dev.azure.com/dnceng-public/public/_apis/testresults/resultsbybuild"
KUSTO = "https://engsrvprod.kusto.windows.net"
DEFINITIONS = {"maui-pr": 302, "maui-pr-devicetests": 314, "maui-pr-uitests": 313}
KEY_FIELDS = ("definition_id", "test_name", "arguments", "queue_name", "test_run_name", "signature")


class EvidenceError(Exception):
    """Only fixed, non-sensitive reason codes may cross the CLI boundary."""


class BudgetError(EvidenceError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize_signature(message):
    """Trim line indentation/empty lines and normalize newlines; preserve all content."""
    if not isinstance(message, str) or not message.strip():
        return ""
    if len(message) > 100_000 or re.search(r"truncat(?:ed|ion)|\x1b", message, re.I):
        return ""
    return "\n".join(line.strip() for line in message.replace("\r\n", "\n").splitlines() if line.strip())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def external_directory(value):
    path = Path(value).resolve()
    repo = Path(__file__).resolve().parents[2]
    if path == repo or repo in path.parents:
        raise EvidenceError("real-evidence-directory-must-be-outside-repository")
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise EvidenceError("real-evidence-directory-must-be-outside-all-checkouts")
    path.mkdir(parents=True, exist_ok=True)
    return path


class Transport:
    def __init__(self, root, max_queries=30, max_bytes=2_000_000_000):
        self.root = external_directory(root)
        self.state_path = self.root / "accounting.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "kusto_queries": 0, "downloaded_bytes": 0, "requests": []}
        self.max_queries = min(max_queries, 30)
        self.max_bytes = min(max_bytes, 2_000_000_000)
        if self.max_queries < 0 or self.max_bytes < 0:
            raise EvidenceError("invalid-negative-budget")
        self.opener = urllib.request.build_opener(NoRedirect())
        self.credential = None
        self.reads = []

    def persist(self):
        write_json(self.state_path, self.state)

    def json_request(self, label, url, payload=None, authenticated=False, fresh=False, text=False, allow_list=False):
        cache = self.root / (digest({"url": url, "payload": payload}) + (".text" if text else ".json"))
        receipt_path = cache.with_suffix(".receipt.json")
        if not fresh and cache.exists() and receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt.get("complete") and receipt.get("sha256") == hashlib.sha256(cache.read_bytes()).hexdigest():
                value = cache.read_text() if text else json.loads(cache.read_text())
                if not text and not (isinstance(value, dict) or allow_list and isinstance(value, list)):
                    raise EvidenceError("invalid-cached-response-shape")
                self.reads.append({"request_id": cache.name, "label": label, "cache_hit": True,
                                   "bytes": receipt.get("bytes", 0), "complete": True})
                return value, receipt
        if self.state["downloaded_bytes"] >= self.max_bytes:
            raise BudgetError("download-budget-reached")
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "text/plain" if text else "application/json", "Accept-Encoding": "identity"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            if url != KUSTO + "/v1/rest/query":
                raise EvidenceError("credential-destination-not-allowlisted")
            if self.state["kusto_queries"] >= self.max_queries:
                raise BudgetError("query-budget-reached")
            if self.credential is None:
                try:
                    process = subprocess.run(
                        ["az", "account", "get-access-token", "--resource", KUSTO,
                         "--query", "accessToken", "-o", "tsv"],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=45, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    raise EvidenceError("developer-authentication-unavailable") from None
                if process.returncode or not process.stdout.strip():
                    raise EvidenceError("developer-authentication-unavailable")
                self.credential = process.stdout.decode().strip()
            headers["Authorization"] = "Bearer " + self.credential
            self.state["kusto_queries"] += 1
        receipt = {"label": label, "complete": False, "bytes": 0,
                   "requested_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        self.state["requests"].append(receipt)
        self.persist()
        try:
            request = urllib.request.Request(url, data=data, headers=headers)
            with self.opener.open(request, timeout=60) as response:
                receipt["status"] = response.status
                if response.status != 200:
                    raise EvidenceError("unexpected-http-status")
                room = min(50_000_000, self.max_bytes - self.state["downloaded_bytes"])
                chunks = []
                size = 0
                while size < room:
                    chunk = response.read(min(65536, room - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    self.state["downloaded_bytes"] += len(chunk)
                receipt["bytes"] = size
                if size >= room:
                    if self.state["downloaded_bytes"] >= self.max_bytes:
                        raise BudgetError("download-budget-reached")
                    raise EvidenceError("response-size-limit-reached")
                raw = b"".join(chunks)
                content_type = response.headers.get("Content-Type", "")
                if not text and "json" not in content_type.lower():
                    raise EvidenceError("non-json-response")
                parsed = raw.decode("utf-8") if text else json.loads(raw)
                if not text and not (isinstance(parsed, dict) or allow_list and isinstance(parsed, list)):
                    raise EvidenceError("invalid-response-shape")
                receipt["continuation"] = response.headers.get("x-ms-continuationtoken", "")
                receipt["sha256"] = hashlib.sha256(raw).hexdigest()
                receipt["complete"] = True
                cache.write_bytes(raw)
                write_json(receipt_path, receipt)
                return parsed, receipt
        except urllib.error.HTTPError as error:
            receipt["status"] = error.code
            receipt["error"] = "http-error-or-redirect"
            raise EvidenceError(receipt["error"]) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            receipt["error"] = "transport-error"
            raise EvidenceError(receipt["error"]) from None
        except (ValueError, UnicodeError):
            receipt["error"] = "invalid-json"
            raise EvidenceError(receipt["error"]) from None
        finally:
            self.reads.append({"request_id": cache.name, "label": label, "cache_hit": False,
                               "bytes": receipt.get("bytes", 0), "complete": receipt["complete"]})
            self.persist()

    def text_request(self, label, url):
        target = urllib.parse.urlsplit(url)
        if target.scheme != "https" or target.username or target.password or not (
                target.hostname in ("dev.azure.com", "helix.dot.net") or
                (target.hostname or "").endswith(".blob.core.windows.net")):
            raise EvidenceError("untrusted-original-log-url")
        return self.json_request(label, url, text=True)


def builds(transport, definition, branch):
    query = urllib.parse.urlencode({
        "definitions": definition, "branchName": "refs/heads/" + branch,
        "statusFilter": "completed", "resultFilter": "succeeded,failed,partiallySucceeded",
        "queryOrder": "finishTimeDescending", "$top": 20, "api-version": "7.1"})
    data, _ = transport.json_request("build-window", AZDO + "/_apis/build/builds?" + query)
    values = data.get("value")
    if not isinstance(values, list):
        raise EvidenceError("invalid-build-window")
    if any(b.get("definition", {}).get("id") != definition or
           b.get("sourceBranch") != "refs/heads/" + branch or b.get("status") != "completed" or
           b.get("result") not in ("succeeded", "failed", "partiallySucceeded") or
           not b.get("finishTime") for b in values):
        raise EvidenceError("build-window-scope-mismatch")
    if len({b["id"] for b in values}) != len(values):
        raise EvidenceError("duplicate-builds")
    times = [b["finishTime"] for b in values]
    if times != sorted(times, reverse=True):
        raise EvidenceError("build-window-order-mismatch")
    return values


def select_prior(values, latest_id):
    indices = [i for i, b in enumerate(values) if b["id"] == latest_id]
    if len(indices) != 1:
        raise EvidenceError("frozen-latest-not-in-window")
    prior = values[indices[0] + 1:indices[0] + 11]
    if len(prior) != 10:
        raise EvidenceError("incomplete-prior-window")
    return prior


def public_failures(transport, build):
    values, seen_pages, seen_results = [], set(), set()
    continuation = ""
    for _ in range(100):
        query = {"buildId": build, "outcomes": "Failed", "$top": 500, "api-version": "7.1-preview.1"}
        if continuation:
            query["continuationToken"] = continuation
        data, receipt = transport.json_request("public-failed-results", RESULTS + "?" + urllib.parse.urlencode(query))
        page = data.get("value")
        if not isinstance(page, list) or data.get("count") != len(page):
            raise EvidenceError("invalid-results-page")
        for result in page:
            ref = (result.get("runId"), result.get("id"))
            if any(type(x) is not int or x <= 0 for x in ref) or ref in seen_results:
                raise EvidenceError("duplicate-or-invalid-result-reference")
            seen_results.add(ref)
            values.append(result)
        continuation = receipt.get("continuation", "")
        if not continuation:
            return values
        if continuation in seen_pages or not page:
            raise EvidenceError("results-pagination-doubt")
        seen_pages.add(continuation)
    raise EvidenceError("results-page-limit")


def public_run_results(transport, run):
    values, seen_refs = [], set()
    for page in range(100):
        query = urllib.parse.urlencode({"outcomes": "Failed", "detailsToInclude": "Iterations",
                                       "$top": 1000, "$skip": page * 1000, "api-version": "7.1"})
        data, receipt = transport.json_request(
            "public-run-failed-details", AZDO + f"/_apis/test/Runs/{run}/Results?" + query)
        rows = data.get("value")
        if not isinstance(rows, list) or data.get("count") != len(rows) or receipt.get("continuation"):
            raise EvidenceError("run-results-pagination-doubt")
        for row in rows:
            ref = row.get("id")
            if type(ref) is not int or ref <= 0 or ref in seen_refs or row.get("outcome") != "Failed":
                raise EvidenceError("run-results-reference-doubt")
            seen_refs.add(ref)
            values.append(row)
        if len(rows) < 1000:
            return values
    raise EvidenceError("run-results-page-limit")


def public_detail(transport, build, result):
    run, ref = result["runId"], result["id"]
    detail = None
    if not transport.state.get("anonymous_run_results_unavailable"):
        try:
            values = public_run_results(transport, run)
            matches = [value for value in values if value.get("id") == ref]
            if len(matches) != 1:
                raise EvidenceError("public-result-not-in-run")
            detail = matches[0]
        except EvidenceError:
            if transport.state["requests"][-1].get("status") not in (301, 302, 401, 403):
                raise
            transport.state["anonymous_run_results_unavailable"] = True
            transport.persist()
    if detail is None:
        detail, _ = transport.json_request(
            "public-result-detail", AZDO +
            f"/_apis/test/Runs/{run}/Results/{ref}?detailsToInclude=Iterations&api-version=7.1")
    summary, _ = transport.json_request("public-run-detail", AZDO + f"/_apis/test/runs/{run}?api-version=7.1")
    if (detail.get("id") != ref or int(detail.get("testRun", {}).get("id", 0)) != run or
            int(detail.get("build", {}).get("id", 0)) != build or
            int(summary.get("build", {}).get("id", 0)) != build or
            summary.get("state") != "Completed" or detail.get("outcome") != "Failed"):
        raise EvidenceError("public-result-scope-or-terminal-state-mismatch")
    return detail, summary


def exact_key(detail, run, definition):
    title = detail.get("testCaseTitle", "")
    automated = detail.get("automatedTestName", "")
    name = automated or title
    for prefix in ("Microsoft.Maui.TestCases.Tests.Issues.", "Microsoft.Maui.TestCases.Tests.",
                   "Microsoft.Maui.IntegrationTests."):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    run_name = run.get("name", "")
    match = re.search(r"((?:ubuntu|osx|windows)\.[A-Za-z0-9_.-]+\.open)", run_name)
    if not match:
        raise EvidenceError("queue-unavailable")
    queue = match[1]
    arguments = ""
    # Fixture parameters are part of the name; theory arguments are not safely
    # separable without an explicit public result field.
    if name.endswith(")") and "(" in name.rsplit(".", 1)[-1]:
        raise EvidenceError("theory-arguments-unavailable")
    signature = normalize_signature(detail.get("errorMessage"))
    if not name or not run_name or not signature:
        raise EvidenceError("exact-name-run-or-signature-unavailable")
    return {"definition_id": definition, "test_name": name, "arguments": arguments, "argument_hash": "",
            "queue_name": queue, "test_run_name": run_name, "signature": signature}


def public_timeline(transport, build):
    value, receipt = transport.json_request(
        "attempt-timeline", AZDO + f"/_apis/build/builds/{build}/timeline?api-version=7.1")
    if receipt.get("continuation") or not isinstance(value.get("records"), list):
        raise EvidenceError("attempt-timeline-incomplete")
    return value


def final_attempt_binding(timeline, run, build, definition):
    """Bind one run to a unique current stage/phase/job, never a build-wide maximum."""
    reference = run.get("pipelineReference", {})
    if (not isinstance(reference, dict) or not isinstance(run.get("build"), dict) or
            reference.get("pipelineId") != build or reference.get("pipelineDefinitionId") != definition or
            str(run.get("build", {}).get("id")) != str(build) or run.get("state") != "Completed"):
        raise EvidenceError("attempt-run-scope-or-state-doubt")
    records = timeline.get("records")
    if not isinstance(records, list) or any(not isinstance(r, dict) or not r.get("id") for r in records):
        raise EvidenceError("attempt-timeline-schema-doubt")
    if len({r["id"] for r in records}) != len(records):
        raise EvidenceError("attempt-timeline-duplicate-records")
    selected, parent, identifier = [], None, ""
    for kind, field, name_field in (
            ("Stage", "stageReference", "stageName"),
            ("Phase", "phaseReference", "phaseName"),
            ("Job", "jobReference", "jobName")):
        part = reference.get(field, {})
        if not isinstance(part, dict):
            raise EvidenceError("attempt-run-reference-missing")
        name, attempt = part.get(name_field), part.get("attempt")
        if not isinstance(name, str) or not name or type(attempt) is not int or attempt <= 0:
            raise EvidenceError("attempt-run-reference-missing")
        identifier = identifier + "." + name if identifier else name
        candidates = [r for r in records if r.get("type") == kind and
                      r.get("identifier") == identifier and r.get("parentId") == parent]
        if len(candidates) != 1:
            raise EvidenceError("attempt-job-identity-ambiguous")
        record = candidates[0]
        current, previous = record.get("attempt"), record.get("previousAttempts")
        if (type(current) is not int or current <= 0 or record.get("state") != "completed" or
                record.get("result") not in ("succeeded", "succeededWithIssues", "failed") or
                not isinstance(previous, list)):
            raise EvidenceError("attempt-final-record-incomplete")
        if any(not isinstance(p, dict) or type(p.get("attempt")) is not int or
               not 0 < p["attempt"] < current or not p.get("recordId") or not p.get("timelineId")
               for p in previous) or len({p["attempt"] for p in previous}) != len(previous):
            raise EvidenceError("attempt-history-ambiguous")
        if attempt > current:
            raise EvidenceError("attempt-run-newer-than-timeline")
        selected.append((record, attempt))
        parent = record["id"]
    # Older stages/jobs must be explicitly represented in previousAttempts.
    # Phase records often carry an empty history, so stage/job supply that proof.
    older = any(record["attempt"] != attempt for record, attempt in selected)
    if older:
        for record, attempt in (selected[0], selected[2]):
            if record["attempt"] != attempt and attempt not in {p["attempt"] for p in record["previousAttempts"]}:
                raise EvidenceError("attempt-prior-history-missing")
        return {"state": "PRIOR", "reason": "run-not-final-attempt"}
    return {"state": "FINAL", "stage": selected[0][0]["identifier"],
            "stage_attempt": selected[0][1], "job_id": selected[2][0]["id"],
            "job_attempt": selected[2][1], "test_run_name": run.get("name")}


def final_attempt_rows(transport, key, build, rows):
    relevant = [r for r in rows if r.get("BuildId") == build and
                r.get("BuildDefinitionId") == key["definition_id"] and
                r.get("TestName") == key.get("test_name") and
                r.get("Arguments") == key.get("arguments") and
                r.get("ArgumentHash") == key.get("argument_hash") and
                r.get("QueueName") == key.get("queue_name") and
                r.get("TestRunName") == key.get("test_run_name")]
    if not relevant:
        return []
    timeline = public_timeline(transport, build)
    final = []
    for run_id in sorted({r.get("TestRunId") for r in relevant}, key=str):
        if type(run_id) is not int or run_id <= 0:
            raise EvidenceError("attempt-run-id-missing")
        run, _ = transport.json_request(
            "attempt-run-detail", AZDO + f"/_apis/test/runs/{run_id}?api-version=7.1")
        if run.get("id") != run_id or run.get("name") != key["test_run_name"]:
            raise EvidenceError("attempt-run-name-or-id-mismatch")
        binding = final_attempt_binding(timeline, run, build, key["definition_id"])
        if binding["state"] == "FINAL":
            final.extend(r for r in relevant if r["TestRunId"] == run_id)
    return final


def deduplicate_rows(rows):
    unique = {}
    for row in rows:
        identity = digest({k: v for k, v in row.items() if k not in ("IndexedAt", "LastIndexedAt")})
        if identity not in unique:
            unique[identity] = dict(row)
        elif row.get("IndexedAt") and unique[identity].get("IndexedAt"):
            unique[identity]["IndexedAt"] = min(row["IndexedAt"], unique[identity]["IndexedAt"])
    return list(unique.values())


def lane_query(definition, branch, ids):
    if definition not in DEFINITIONS.values() or branch not in ("main", "net11.0") or (
            len(ids) > 20 or any(type(i) is not int or i <= 0 for i in ids)):
        raise EvidenceError("invalid-query-scope")
    return f"""AzureDevOpsTests
| where Organization == "dnceng-public" and Project == "public" and Repository == "dotnet/maui"
| where BuildDefinitionId == {definition} and Branch == "{branch}"
| where BuildId in (dynamic({json.dumps(ids)}))
| project BuildId, BuildDefinitionId, Branch, TestName, Arguments, ArgumentHash,
          QueueName, TestRunName, Outcome, Message, TestRunId, TestResultId,
          RunCompleted, IndexedAt=ingestion_time()
| take 50001"""


def kusto_rows(transport, definition, branch, ids):
    data, _ = transport.json_request("kusto-history",
        KUSTO + "/v1/rest/query", {"db": "engineeringdata", "csl": lane_query(definition, branch, ids)},
        authenticated=True)
    if data.get("error") or data.get("Exceptions") or not isinstance(data.get("Tables"), list):
        raise EvidenceError("kusto-error-or-incomplete-response")
    tables = [t for t in data["Tables"] if isinstance(t, dict) and
              any(c.get("ColumnName") == "BuildId" for c in t.get("Columns", []))]
    if len(tables) != 1:
        raise EvidenceError("kusto-result-table-missing")
    for table in data["Tables"]:
        if table.get("TableName") == "QueryStatus" and table.get("Rows"):
            raise EvidenceError("kusto-partial-query-status")
    table = tables[0]
    names = [column["ColumnName"] for column in table["Columns"]]
    if len(table["Rows"]) >= 50001 or any(len(row) != len(names) for row in table["Rows"]):
        raise EvidenceError("kusto-truncation-or-schema-doubt")
    rows = [dict(zip(names, row)) for row in table["Rows"]]
    if any(r.get("BuildId") not in ids or r.get("BuildDefinitionId") != definition or
           r.get("Branch") != branch for r in rows):
        raise EvidenceError("kusto-scope-mismatch")
    return deduplicate_rows(rows)


def hint(key, build, rows, transport_complete=True):
    state = {"build_id": build, "state": "UNKNOWN", "reason": "history-gap-or-nonmatch",
             "signature": key.get("signature")}
    if not all(isinstance(key.get(field), str) for field in
               ("test_name", "arguments", "argument_hash", "queue_name", "test_run_name", "signature")) or not (
            key["test_name"] and key["signature"] and key["queue_name"] and key["test_run_name"]):
        state["reason"] = "invalid-or-incomplete-key"
        return state
    if not transport_complete:
        state["reason"] = "provider-error"
        return state
    relevant = [r for r in rows if r.get("BuildId") == build and
                r.get("BuildDefinitionId") == key["definition_id"] and
                r.get("TestName") == key["test_name"] and r.get("Arguments") == key["arguments"] and
                r.get("ArgumentHash") == key["argument_hash"] and
                r.get("QueueName") == key["queue_name"] and r.get("TestRunName") == key["test_run_name"]]
    if not relevant:
        return state
    relevant = deduplicate_rows(relevant)
    try:
        if any(not r.get("IndexedAt") or not r.get("RunCompleted") or
               dt.datetime.fromisoformat(r["IndexedAt"].replace("Z", "+00:00")) <
               dt.datetime.fromisoformat(r["RunCompleted"].replace("Z", "+00:00")) for r in relevant):
            state["reason"] = "ingestion-or-completion-time-doubt"
            return state
    except (ValueError, TypeError):
        state["reason"] = "ingestion-or-completion-time-doubt"
        return state
    refs = {(r.get("TestRunId"), r.get("TestResultId")) for r in relevant}
    if len(refs) != len(relevant) or any(type(x) is not int or x <= 0 for ref in refs for x in ref):
        state["reason"] = "ambiguous-result-references"
    elif all(r.get("Outcome") == "Failed" and normalize_signature(r.get("Message")) == key["signature"]
             for r in relevant):
        state.update(state="RECURRED", reason="exact-failed-observations",
                     result_refs=[{"run_id": r, "result_id": i} for r, i in sorted(refs)])
    else:
        state["reason"] = "mixed-or-nonmatching-observations"
    # NOT_RECURRED is deliberately unavailable: per-run counts do not prove the
    # entire run set or historical failures overwritten by final Passed results.
    return state


def structured_candidate(transport, key, build, rows, complete=True):
    result = hint(key, build, [], complete)
    if not complete or result["reason"] == "invalid-or-incomplete-key":
        return result
    try:
        final = final_attempt_rows(transport, key, build, rows)
    except BudgetError:
        raise
    except (EvidenceError, ValueError, TypeError, KeyError) as error:
        result["reason"] = str(error) if isinstance(error, EvidenceError) else "attempt-schema-doubt"
        return result
    result = hint(key, build, final, complete)
    if result["state"] != "RECURRED":
        return result
    try:
        public = {(r["runId"], r["id"]) for r in public_failures(transport, build)}
        if any((r["run_id"], r["result_id"]) not in public for r in result["result_refs"]):
            result.update(state="UNKNOWN", reason="index-not-reconciled-with-public-failed-results")
        else:
            for reference in result["result_refs"]:
                detail, run = public_detail(transport, build, {
                    "runId": reference["run_id"], "id": reference["result_id"]})
                if exact_key(detail, run, key["definition_id"]) != key:
                    result.update(state="UNKNOWN", reason="index-not-reconciled-with-public-exact-key")
                    break
    except BudgetError:
        raise
    except EvidenceError:
        result.update(state="UNKNOWN", reason="public-run-state-unavailable")
    return result


def consumer_hint(transport, key, build, rows, complete=True):
    result = structured_candidate(transport, key, build, rows, complete)
    if result["state"] == "RECURRED":
        # No real replacement has passed the original-console oracle.
        result.update(state="UNKNOWN", reason="uncertified-positive-requires-original-evidence")
    return result


def discover_keys(transport, build, definition):
    keys, unkeyed = {}, []
    timeline = None
    for result in public_failures(transport, build):
        try:
            run, _ = transport.json_request("public-run-detail",
                AZDO + f"/_apis/test/runs/{result['runId']}?api-version=7.1")
            if run.get("id") != result["runId"]:
                raise EvidenceError("attempt-run-id-mismatch")
            if not re.search(r"((?:ubuntu|osx|windows)\.[A-Za-z0-9_.-]+\.open)", run.get("name", "")):
                raise EvidenceError("queue-unavailable")
            if timeline is None:
                timeline = public_timeline(transport, build)
            binding = final_attempt_binding(timeline, run, build, definition)
            if binding["state"] == "PRIOR":
                continue
            detail, run = public_detail(transport, build, result)
            key = exact_key(detail, run, definition)
            identity = digest(key)
            keys.setdefault(identity, {"key": key, "current_result_refs": [], "aliases": []})
            keys[identity]["current_result_refs"].append({"run_id": result["runId"], "result_id": result["id"]})
            for alias in (detail.get("testCaseTitle"), detail.get("automatedTestName"), key["test_name"]):
                if alias and alias not in keys[identity]["aliases"]:
                    keys[identity]["aliases"].append(alias)
        except BudgetError:
            raise
        except (ValueError, TypeError, KeyError):
            unkeyed.append({"run_id": result["runId"], "result_id": result["id"],
                           "test_name": result.get("automatedTestName") or result.get("testCaseTitle"),
                           "reason": "public-detail-schema-doubt"})
        except EvidenceError as error:
            unkeyed.append({"run_id": result["runId"], "result_id": result["id"],
                           "test_name": result.get("automatedTestName") or result.get("testCaseTitle"),
                           "reason": str(error)})
    return list(keys.values()), unkeyed


def preflight(transport, inventory, branch):
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
        raise EvidenceError("invalid-frozen-inventory")
    pipelines = inventory.get("pipelines")
    if not isinstance(pipelines, list) or [p.get("name") for p in pipelines] != list(DEFINITIONS):
        raise EvidenceError("invalid-frozen-pipeline-order")
    output = {"schema_version": 2, "provider": "kusto", "source_sha": SOURCE_SHA,
              "signature_normalization": "trim-lines-preserve-content-v1", "pipelines": [],
              "certification": "none; original-oracle disagreement blocks log omission"}
    for pipeline in pipelines:
        result = {"name": pipeline["name"], "build_id": pipeline.get("build_id"),
                  "keys": [], "unkeyed_failures": [], "status": "UNKNOWN",
                  "current_inventory_coverage": "UNKNOWN"}
        output["pipelines"].append(result)
        if pipeline.get("status") == "skipped-no-recent-build":
            result["reason"] = "frozen-no-recent-build"
            continue
        definition = DEFINITIONS[pipeline["name"]]
        if pipeline.get("definition_id") != definition or type(pipeline.get("build_id")) is not int:
            raise EvidenceError("invalid-frozen-pipeline-key")
        try:
            window = builds(transport, definition, branch)
            prior = select_prior(window, pipeline["build_id"])
            keys, unkeyed = discover_keys(transport, pipeline["build_id"], definition)
            result.update(keys=keys, unkeyed_failures=unkeyed,
                          prior_build_ids=[b["id"] for b in prior], status="ready" if not unkeyed else "partial")
            rows, complete = [], True
            try:
                rows = kusto_rows(transport, definition, branch, [b["id"] for b in prior])
            except BudgetError:
                raise
            except EvidenceError as error:
                complete = False
                result["provider_error"] = str(error)
            for key in keys:
                key["hints"] = [consumer_hint(transport, key["key"], b["id"], rows, complete) for b in prior]
        except BudgetError:
            raise
        except EvidenceError as error:
            result["reason"] = str(error)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--branch", choices=("main", "net11.0"), required=True)
    parser.add_argument("--cache-root", required=True, help="External, local-only evidence directory")
    parser.add_argument("--output", required=True)
    parser.add_argument("--offline", action="store_true", help="Frozen cache replay; never authenticate or download")
    args = parser.parse_args()
    try:
        transport = Transport(args.cache_root, max_queries=0 if args.offline else 30,
                              max_bytes=0 if args.offline else 2_000_000_000)
        result = preflight(transport, json.loads(Path(args.inventory).read_text()), args.branch)
        output = Path(args.output).resolve()
        external_directory(output.parent)
        write_json(output, result)
        print(json.dumps({"provider": "kusto", "pipelines": len(result["pipelines"]),
                          "unknown_pipeline_count": sum(p["status"] == "UNKNOWN" for p in result["pipelines"])}))
    except (EvidenceError, ValueError, OSError):
        print("Local preflight incomplete; original evidence is required.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
