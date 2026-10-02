#!/usr/bin/env python3
"""Bounded local corpus comparison. Real downloads must remain outside the repository."""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import ci_scan_kusto as history


def bound_blocks(text, names, signature):
    lines, block, hits = text.splitlines(), None, 0
    for raw in lines + ["=== TEST EXECUTION SUMMARY ==="]:
        line = re.sub(r"^\d{4}-\d\d-\d\dT\S+Z\s*", "", raw)
        line = re.sub(r"^\s*\[xUnit.net [0-9:.]+\]\s*", "", line)
        marker = re.search(r"\[(FAIL|PASS|SKIP|IGNORE|INCONCLUSIVE)\]\s+(.+)", line)
        vstest = re.match(r"\s*(Failed|Passed|Skipped)\s+(.+?)\s+\[[^]]+\]\s*$", line)
        end = marker or vstest or "=== TEST EXECUTION SUMMARY ===" in line or "Xml file was written" in line
        if end and block is not None:
            if signature in history.normalize_signature("\n".join(block)):
                hits += 1
            block = None
        if marker and marker[1] == "FAIL" and marker[2].split("   Test name:", 1)[0].strip() in names:
            block = [line]
        elif vstest and vstest[1] == "Failed" and vstest[2].strip() in names:
            block = [line]
        elif block is not None:
            block.append(line)
    return hits


def original_logs(transport, build, key):
    timeline, _ = transport.json_request(
        "original-timeline", history.AZDO + f"/_apis/build/builds/{build}/timeline?api-version=7.1")
    records = timeline.get("records")
    if not isinstance(records, list):
        raise history.EvidenceError("original-timeline-unavailable")
    jobs = {r["id"]: r for r in records if r.get("type") == "Job"}
    texts, scoped = [], 0
    for task in records:
        if task.get("type") != "Task" or task.get("result") == "skipped" or task.get("state") != "completed":
            continue
        log_id = task.get("log", {}).get("id")
        submission = key["definition_id"] == 314 and re.fullmatch(
            r"DeviceTests.+ \((Unix|Windows)\)", task.get("name", ""))
        if not log_id or (not submission and task.get("result") not in ("failed", "succeededWithIssues")):
            continue
        text, _ = transport.text_request("original-azdo-log",
            history.AZDO + f"/_apis/build/builds/{build}/logs/{log_id}?api-version=7.1")
        if not submission:
            if key["test_run_name"] in text:
                texts.append(text)
                scoped += 1
            continue
        runs = set(re.findall(r"Starting Azure Pipelines Test Run (\S+)", text))
        if key["test_run_name"] not in runs:
            continue
        ids = set(re.findall(r"https://helix\.dot\.net/api/jobs/([0-9a-f-]{36})/workitems", text))
        if len(ids) != 1 or runs != {key["test_run_name"]}:
            raise history.EvidenceError("original-submission-ambiguous")
        job_id = next(iter(ids))
        details, _ = transport.json_request("original-helix-details",
            f"https://helix.dot.net/api/jobs/{job_id}/details?api-version=2019-06-17")
        props = details.get("Properties", {})
        parent = jobs.get(task.get("parentId"), {})
        if not (details.get("Name") == job_id and details.get("QueueId") == key["queue_name"] and
                details.get("Finished") and props.get("BuildId") == str(build) and
                props.get("DefinitionId") == str(key["definition_id"]) and
                props.get("System.JobId") == parent.get("id") and
                int(props.get("System.JobAttempt", 0)) == parent.get("attempt")):
            raise history.EvidenceError("original-helix-linkage-doubt")
        items, _ = transport.json_request("original-helix-inventory",
            f"https://helix.dot.net/api/jobs/{job_id}/workitems?api-version=2019-06-17", allow_list=True)
        if not isinstance(items, list):
            raise history.EvidenceError("original-workitem-inventory-unavailable")
        real = [i for i in items if i.get("Name") != "HelixController Work Queueing"]
        if len(real) != details.get("InitialWorkItemCount") or any(
                i.get("State") != "Finished" or type(i.get("ExitCode")) is not int for i in real):
            raise history.EvidenceError("original-workitem-inventory-incomplete")
        for item in real:
            if item["ExitCode"] != 0:
                console, _ = transport.text_request("original-helix-console", item["ConsoleOutputUri"])
                texts.append(console)
        scoped += 1
    if not scoped:
        raise history.EvidenceError("original-exact-run-not-bound")
    return texts


def diagnostic_logs(transport, build, key, references):
    """Read all consoles only for a disagreement; never change the pinned oracle."""
    if key["definition_id"] != 314:
        raise history.EvidenceError("diagnostic-nondevice-linkage-unavailable")
    timeline = history.public_timeline(transport, build)
    job_ids = set()
    for reference in references:
        run, _ = transport.json_request("diagnostic-run-detail", history.AZDO +
            f"/_apis/test/runs/{reference['run_id']}?api-version=7.1")
        binding = history.final_attempt_binding(timeline, run, build, key["definition_id"])
        if binding["state"] != "FINAL":
            raise history.EvidenceError("diagnostic-run-not-final")
        job_ids.add(binding["job_id"])
    texts, scoped = [], False
    for task in timeline["records"]:
        if (task.get("type") != "Task" or task.get("parentId") not in job_ids or
                task.get("state") != "completed" or not task.get("log", {}).get("id") or
                not re.fullmatch(r"DeviceTests.+ \((Unix|Windows)\)", task.get("name", ""))):
            continue
        text, _ = transport.text_request("diagnostic-submission", history.AZDO +
            f"/_apis/build/builds/{build}/logs/{task['log']['id']}?api-version=7.1")
        runs = set(re.findall(r"Starting Azure Pipelines Test Run (\S+)", text))
        if runs != {key["test_run_name"]}:
            continue
        ids = set(re.findall(r"https://helix\.dot\.net/api/jobs/([0-9a-f-]{36})/workitems", text))
        if len(ids) != 1:
            raise history.EvidenceError("diagnostic-job-ambiguous")
        job_id = next(iter(ids))
        details, _ = transport.json_request("diagnostic-helix-details",
            f"https://helix.dot.net/api/jobs/{job_id}/details?api-version=2019-06-17")
        props = details.get("Properties", {})
        parent = next(r for r in timeline["records"] if r["id"] == task["parentId"])
        if (details.get("Name") != job_id or details.get("QueueId") != key["queue_name"] or
                not details.get("Finished") or props.get("BuildId") != str(build) or
                props.get("DefinitionId") != str(key["definition_id"]) or
                props.get("System.JobId") != parent["id"] or
                int(props.get("System.JobAttempt", 0)) != parent["attempt"]):
            raise history.EvidenceError("diagnostic-job-linkage-doubt")
        items, _ = transport.json_request("diagnostic-helix-inventory",
            f"https://helix.dot.net/api/jobs/{job_id}/workitems?api-version=2019-06-17", allow_list=True)
        real = [item for item in items if item.get("Name") != "HelixController Work Queueing"]
        if len(real) != details.get("InitialWorkItemCount") or any(
                item.get("State") != "Finished" or type(item.get("ExitCode")) is not int for item in real):
            raise history.EvidenceError("diagnostic-workitems-incomplete")
        for item in real:
            text, _ = transport.text_request("diagnostic-console", item["ConsoleOutputUri"])
            texts.append(text)
        scoped = True
    if not scoped:
        raise history.EvidenceError("diagnostic-run-not-bound")
    return texts


def answer(build_ids, times):
    ids = sorted(set(build_ids))
    return {"positive_build_ids": ids, "N": len(ids), "ge_2": len(ids) >= 2,
            "first_seen": min((times[b] for b in ids), default=None), "occurrences": len(ids)}


def summarize(transport):
    groups = {}
    for receipt in transport.state["requests"]:
        label = receipt["label"]
        route = "kusto" if label.startswith("kusto") else "original" if label.startswith("original") else "structured"
        value = groups.setdefault(route, {"requests": 0, "downloaded_bytes": 0})
        value["requests"] += 1
        value["downloaded_bytes"] += receipt.get("bytes", 0)
    return groups


def validate(transport, windows_root, output_root):
    report = {"source_sha": history.SOURCE_SHA, "simulated_scans": 0, "latest_failure_records": 0,
              "keyed_latest": 0, "unkeyed_latest": 0, "pairs": 0, "recurred": 0, "unknown": 0,
              "unknown_unkeyed_failure_record_pairs": 0,
              "g1_compared": 0, "g1_unavailable": 0, "g2_compared": 0, "g2_unavailable": 0,
              "unsafe_disagreements": [], "scan_agreements_g1": 0, "lanes": [],
              "not_recurred": 0, "ingestion_lag_seconds": [], "status": "INCOMPLETE"}
    report["g2_unavailable_reasons"] = {}
    report.update(rule_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  frozen_builds_visited=0, scan_keys_g2_identical=0, scan_keys_g2_incomplete=0,
                  prior_attempt_failure_records_discarded=0, scan_answers=[],
                  classifications={"IDENTICAL": 0, "KUSTO_CORRECT_ORIGINAL_MISS": 0, "UNSAFE": 0},
                  blind_spot_exceptions=[], certified_replacements=[],
                  actual_original_network_reads_avoided={"requests": 0, "bytes": 0})
    before_requests = len(transport.state["requests"])
    before_queries = transport.state["kusto_queries"]
    comparisons, baseline_reads, routed_reads, candidate_reads, eligible_reads = [], [], [], [], []

    def oracle(build, entry):
        start = len(transport.reads)
        try:
            texts = original_logs(transport, build, entry["key"])
            value = any(bound_blocks(text, entry["aliases"], entry["key"]["signature"]) for text in texts)
            return value, transport.reads[start:]
        except history.BudgetError:
            raise
        except (history.EvidenceError, ValueError, KeyError) as error:
            reason = str(error) if isinstance(error, history.EvidenceError) else "original-schema-doubt"
            report["g2_unavailable_reasons"][reason] = report["g2_unavailable_reasons"].get(reason, 0) + 1
            return None, transport.reads[start:]

    def replay_cost(reads):
        unique = {r["request_id"]: r for r in reads}
        return {"distinct_evidence_reads": len(unique), "response_body_bytes": sum(r["bytes"] for r in unique.values())}

    def save():
        new = transport.state["requests"][before_requests:]
        attempt = [r for r in new if r["label"].startswith("attempt-")]
        report["new_network"] = {"requests": len(new), "bytes": sum(r.get("bytes", 0) for r in new),
                                 "kusto_queries": transport.state["kusto_queries"] - before_queries}
        report["new_attempt_check_network"] = {
            "requests": len(attempt), "bytes": sum(r.get("bytes", 0) for r in attempt)}
        report["net_actual_network_savings"] = {
            "requests": -len(attempt), "bytes": -sum(r.get("bytes", 0) for r in attempt)}
        report["replay_evidence_ledgers_not_network_savings"] = {
            "original": replay_cost(baseline_reads), "routed_candidate": replay_cost(routed_reads + candidate_reads),
            "positive_evidence_omitted_in_candidate_replay": replay_cost(eligible_reads),
            "note": "Executed frozen-cache paths, not measured avoided HTTP traffic; live consumer stays UNKNOWN."}
        report["actual_network"] = summarize(transport)
        history.write_json(output_root / "pairs.json", comparisons)
        history.write_json(output_root / "report.json", report)

    history.write_json(output_root / "report.json", report)
    for definition in (302, 313, 314):
        for branch in ("main", "net11.0"):
            window = json.loads((windows_root / f"builds-{definition}-{branch}.json").read_text())["value"]
            if len(window) != 20 or any(b["definition"]["id"] != definition or
                                      b["sourceBranch"] != "refs/heads/" + branch for b in window):
                raise history.EvidenceError("invalid-frozen-corpus-window")
            times = {b["id"]: b["finishTime"] for b in window}
            lane = {"definition": definition, "branch": branch, "build_ids": [b["id"] for b in window],
                    "provider_error": None, "keyed": 0, "unkeyed": 0, "timeline_errors": {}}
            report["lanes"].append(lane)
            rows = []
            try:
                rows = history.kusto_rows(transport, definition, branch, lane["build_ids"])
            except history.BudgetError:
                raise
            except history.EvidenceError as error:
                lane["provider_error"] = str(error)
            history.write_json(output_root / f"rows-{definition}-{branch}.json", rows)
            for row in rows:
                if row.get("IndexedAt") and row.get("RunCompleted"):
                    try:
                        indexed = dt.datetime.fromisoformat(row["IndexedAt"].replace("Z", "+00:00"))
                        completed = dt.datetime.fromisoformat(row["RunCompleted"].replace("Z", "+00:00"))
                        report["ingestion_lag_seconds"].append((indexed - completed).total_seconds())
                    except ValueError:
                        continue
            inventory = {}
            for build in window:
                report["frozen_builds_visited"] += 1
                try:
                    history.public_timeline(transport, build["id"])
                except history.BudgetError:
                    raise
                except history.EvidenceError as error:
                    lane["timeline_errors"][str(build["id"])] = str(error)
                keys, unkeyed = history.discover_keys(transport, build["id"], definition)
                source_count = len(history.public_failures(transport, build["id"]))
                discarded = source_count - sum(len(k["current_result_refs"]) for k in keys) - len(unkeyed)
                inventory[build["id"]] = {"keys": keys, "unkeyed": unkeyed,
                                          "source_failed_records": source_count,
                                          "discarded_prior_attempt_records": discarded}
            history.write_json(output_root / f"keys-{definition}-{branch}.json", inventory)
            for build in window[:10]:
                report["simulated_scans"] += 1
                latest = inventory[build["id"]]
                lane["keyed"] += len(latest["keys"])
                lane["unkeyed"] += len(latest["unkeyed"])
                report["keyed_latest"] += len(latest["keys"])
                report["unkeyed_latest"] += len(latest["unkeyed"])
                report["unknown_unkeyed_failure_record_pairs"] += 10 * len(latest["unkeyed"])
                report["latest_failure_records"] += latest["source_failed_records"]
                report["prior_attempt_failure_records_discarded"] += latest["discarded_prior_attempt_records"]
                prior = history.select_prior(window, build["id"])
                for entry in latest["keys"]:
                    key = entry["key"]
                    current_g2, current_reads = oracle(build["id"], entry)
                    baseline_reads.extend(current_reads)
                    routed_reads.extend(current_reads)
                    original_ids = [build["id"]] if current_g2 else []
                    routed_ids = list(original_ids)
                    scan_available, g1_available = current_g2 is True, True
                    g1_ids, g1_routed_ids = [build["id"]], [build["id"]]
                    for old in prior:
                        prior_id = old["id"]
                        report["pairs"] += 1
                        start = len(transport.reads)
                        state = history.structured_candidate(transport, key, prior_id, rows, not lane["provider_error"])
                        candidate_reads.extend(transport.reads[start:])
                        report["recurred" if state["state"] == "RECURRED" else "unknown"] += 1
                        other = inventory[prior_id]
                        matching = [k for k in other["keys"] if k["key"] == key]
                        if matching:
                            g1 = True
                            report["g1_compared"] += 1
                            g1_ids.append(prior_id)
                        elif other["unkeyed"]:
                            report["g1_unavailable"] += 1
                            g1_available = False
                            g1 = None
                        else:
                            g1 = bool(matching)
                            report["g1_compared"] += 1
                            if g1:
                                g1_ids.append(prior_id)
                        g2, original_reads = oracle(prior_id, entry)
                        baseline_reads.extend(original_reads)
                        report["g2_compared" if g2 is not None else "g2_unavailable"] += 1
                        comparison = {"latest_build_id": build["id"], "prior_build_id": prior_id,
                                      "definition": definition, "branch": branch,
                                      "key_digest": history.digest(key), "test_name": key["test_name"],
                                      "hint_state": state["state"], "hint_reason": state["reason"],
                                      "g1": g1, "g2": g2, "classification": "IDENTICAL",
                                      "basis": "same-original-fallback"}
                        if g2:
                            original_ids.append(prior_id)
                        if g2 is None:
                            scan_available = False
                        if state["state"] == "RECURRED":
                            g1_routed_ids.append(prior_id)
                            if g1 is False:
                                report["unsafe_disagreements"].append(
                                    {"build_id": prior_id, "latest_build_id": build["id"],
                                     "definition": definition, "key_digest": history.digest(key), "oracle": "G1"})
                            if g2 is False:
                                try:
                                    texts = diagnostic_logs(transport, prior_id, key, state["result_refs"])
                                    confirmed = any(bound_blocks(t, entry["aliases"], key["signature"]) for t in texts)
                                except history.BudgetError:
                                    raise
                                except (history.EvidenceError, ValueError, KeyError) as error:
                                    confirmed = None
                                    comparison["diagnostic_error"] = (
                                        str(error) if isinstance(error, history.EvidenceError) else "diagnostic-schema-doubt")
                                comparison["diagnostic_confirmed"] = confirmed
                                if confirmed is True:
                                    comparison.update(classification="KUSTO_CORRECT_ORIGINAL_MISS",
                                                      basis="diagnostic-only-console-confirmed")
                                    report["blind_spot_exceptions"].append(dict(comparison))
                                    routed_ids.append(prior_id)
                                elif confirmed is False:
                                    report["unsafe_disagreements"].append(
                                        {"build_id": prior_id, "latest_build_id": build["id"],
                                         "definition": definition, "key_digest": history.digest(key),
                                         "test_name": key["test_name"], "oracle": "G2-and-diagnostic"})
                                else:
                                    comparison["basis"] = "diagnostic-unavailable-original-fallback"
                                    scan_available = False
                                    routed_reads.extend(original_reads)
                            elif g2 is True:
                                comparison["basis"] = "exact-final-attempt-console-agreement"
                                routed_ids.append(prior_id)
                                eligible_reads.extend(original_reads)
                            else:
                                comparison["basis"] = "proof-unavailable-original-fallback"
                                routed_reads.extend(original_reads)
                        else:
                            start = len(transport.reads)
                            fallback, _ = oracle(prior_id, entry)
                            routed_reads.extend(transport.reads[start:])
                            if fallback != g2:
                                report["unsafe_disagreements"].append(
                                    {"build_id": prior_id, "latest_build_id": build["id"],
                                     "definition": definition, "key_digest": history.digest(key),
                                     "test_name": key["test_name"], "oracle": "fallback-replay"})
                            if fallback:
                                routed_ids.append(prior_id)
                            if g1:
                                g1_routed_ids.append(prior_id)
                        if report["unsafe_disagreements"]:
                            comparison["classification"] = "UNSAFE"
                        report["classifications"][comparison["classification"]] += 1
                        comparisons.append(comparison)
                        if report["unsafe_disagreements"]:
                            report["status"] = "STOP_UNSAFE"
                            save()
                            return report
                    if g1_available and answer(g1_ids, times) == answer(g1_routed_ids, times):
                        report["scan_agreements_g1"] += 1
                    original_answer, routed_answer = answer(original_ids, times), answer(routed_ids, times)
                    report["scan_answers"].append({
                        "latest_build_id": build["id"], "key_digest": history.digest(key),
                        "complete": scan_available, "original": original_answer, "routed": routed_answer})
                    exceptions = [p for p in report["blind_spot_exceptions"] if
                                  p["latest_build_id"] == build["id"] and p["key_digest"] == history.digest(key)]
                    if scan_available and original_answer != routed_answer and not exceptions:
                        report["unsafe_disagreements"].append({
                            "latest_build_id": build["id"], "definition": definition,
                            "test_name": key["test_name"], "oracle": "end-to-end"})
                        report["status"] = "STOP_UNSAFE"
                        save()
                        return report
                    if scan_available and original_answer == routed_answer:
                        report["scan_keys_g2_identical"] += 1
                    else:
                        report["scan_keys_g2_incomplete"] += 1
            save()
    report["status"] = "CANDIDATE_COMPARISON_COMPLETE"
    report["uncertified"] = ["Absence/NOT_RECURRED: no run-set or overwritten-attempt coverage proof",
                             "Unkeyed current failures and incomplete G1 comparisons",
                             "Any positive lacking original exact-run/signature G2 proof",
                             "Whole-scanner replacement and original-log end-to-end equivalence"]
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", required=True, help="External frozen six-lane top20 files")
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--reuse-kusto", action="store_true",
                        help="Require frozen Kusto responses; no new queries or authentication")
    args = parser.parse_args()
    root = history.external_directory(args.output)
    try:
        transport = history.Transport(args.cache_root)
        if args.reuse_kusto:
            transport.max_queries = transport.state["kusto_queries"]
        report = validate(transport, Path(args.windows), root)
        print(json.dumps({key: value for key, value in report.items()
                          if key not in ("ingestion_lag_seconds", "lanes", "scan_answers")}))
        return 0 if report["status"] == "CANDIDATE_COMPARISON_COMPLETE" else 2
    except history.BudgetError:
        print("STOP: query/download budget reached; corpus remains uncertified.", file=sys.stderr)
    except (history.EvidenceError, ValueError, OSError, KeyError):
        print("STOP: corpus evidence incomplete; no replacements certified.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
