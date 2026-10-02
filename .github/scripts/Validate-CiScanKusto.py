#!/usr/bin/env python3
"""Bounded local corpus comparison. Real downloads must remain outside the repository."""
import argparse
import datetime as dt
import json
import re
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
    history.write_json(output_root / "report.json", report)
    for definition in (302, 313, 314):
        for branch in ("main", "net11.0"):
            window = json.loads((windows_root / f"builds-{definition}-{branch}.json").read_text())["value"]
            if len(window) != 20 or any(b["definition"]["id"] != definition or
                                      b["sourceBranch"] != "refs/heads/" + branch for b in window):
                raise history.EvidenceError("invalid-frozen-corpus-window")
            times = {b["id"]: b["finishTime"] for b in window}
            lane = {"definition": definition, "branch": branch, "build_ids": [b["id"] for b in window],
                    "provider_error": None, "keyed": 0, "unkeyed": 0}
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
                keys, unkeyed = history.discover_keys(transport, build["id"], definition)
                inventory[build["id"]] = {"keys": keys, "unkeyed": unkeyed}
            history.write_json(output_root / f"keys-{definition}-{branch}.json", inventory)
            for build in window[:10]:
                report["simulated_scans"] += 1
                latest = inventory[build["id"]]
                lane["keyed"] += len(latest["keys"])
                lane["unkeyed"] += len(latest["unkeyed"])
                report["keyed_latest"] += len(latest["keys"])
                report["unkeyed_latest"] += len(latest["unkeyed"])
                report["unknown_unkeyed_failure_record_pairs"] += 10 * len(latest["unkeyed"])
                report["latest_failure_records"] += sum(len(k["current_result_refs"]) for k in latest["keys"]) + len(latest["unkeyed"])
                prior = history.select_prior(window, build["id"])
                for entry in latest["keys"]:
                    key = entry["key"]
                    original_ids, routed_ids, scan_available = [build["id"]], [build["id"]], True
                    for old in prior:
                        prior_id = old["id"]
                        report["pairs"] += 1
                        state = history.structured_candidate(transport, key, prior_id, rows, not lane["provider_error"])
                        report["recurred" if state["state"] == "RECURRED" else "unknown"] += 1
                        other = inventory[prior_id]
                        matching = [k for k in other["keys"] if k["key"] == key]
                        if matching:
                            g1 = True
                            report["g1_compared"] += 1
                            original_ids.append(prior_id)
                        elif other["unkeyed"]:
                            report["g1_unavailable"] += 1
                            scan_available = False
                            g1 = None
                        else:
                            g1 = bool(matching)
                            report["g1_compared"] += 1
                            if g1:
                                original_ids.append(prior_id)
                        if state["state"] == "RECURRED":
                            routed_ids.append(prior_id)
                            if g1 is False:
                                report["unsafe_disagreements"].append(
                                    {"build_id": prior_id, "latest_build_id": build["id"],
                                     "definition": definition, "key_digest": history.digest(key), "oracle": "G1"})
                            try:
                                texts = original_logs(transport, prior_id, key)
                                g2 = any(bound_blocks(text, entry["aliases"], key["signature"]) for text in texts)
                                report["g2_compared"] += 1
                                if not g2:
                                    report["unsafe_disagreements"].append(
                                        {"build_id": prior_id, "latest_build_id": build["id"],
                                         "definition": definition, "key_digest": history.digest(key), "oracle": "G2"})
                            except history.BudgetError:
                                raise
                            except (history.EvidenceError, ValueError, KeyError) as error:
                                report["g2_unavailable"] += 1
                                reason = str(error) if isinstance(error, history.EvidenceError) else "original-schema-doubt"
                                report["g2_unavailable_reasons"][reason] = report["g2_unavailable_reasons"].get(reason, 0) + 1
                        elif g1:
                            routed_ids.append(prior_id)
                        if report["unsafe_disagreements"]:
                            report["status"] = "STOP_UNSAFE"
                            report["actual_network"] = summarize(transport)
                            history.write_json(output_root / "report.json", report)
                            return report
                    if scan_available and answer(original_ids, times) == answer(routed_ids, times):
                        report["scan_agreements_g1"] += 1
            report["actual_network"] = summarize(transport)
            history.write_json(output_root / "report.json", report)
    report["status"] = "CANDIDATE_COMPARISON_COMPLETE"
    report["actual_network"] = summarize(transport)
    report["certified_replacements"] = []
    report["uncertified"] = ["Absence/NOT_RECURRED: no run-set or overwritten-attempt coverage proof",
                             "Unkeyed current failures and incomplete G1 comparisons",
                             "Any positive lacking original exact-run/signature G2 proof",
                             "Whole-scanner replacement and original-log end-to-end equivalence"]
    history.write_json(output_root / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", required=True, help="External frozen six-lane top20 files")
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = history.external_directory(args.output)
    try:
        transport = history.Transport(args.cache_root)
        report = validate(transport, Path(args.windows), root)
        print(json.dumps({key: value for key, value in report.items()
                          if key not in ("ingestion_lag_seconds", "lanes")}))
        return 0 if report["status"] == "CANDIDATE_COMPARISON_COMPLETE" else 2
    except history.BudgetError:
        print("STOP: query/download budget reached; corpus remains uncertified.", file=sys.stderr)
    except (history.EvidenceError, ValueError, OSError, KeyError):
        print("STOP: corpus evidence incomplete; no replacements certified.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
