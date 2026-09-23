"""Experimental MAUI consumer policy. Transport belongs to the shared demo."""

from copy import deepcopy
import re
from typing import Any, Protocol


class HistoryClient(Protocol):
    def query(self, repository: str, request: dict[str, Any]) -> dict[str, Any]: ...


class MauiHistory:
    def __init__(self, client: HistoryClient):
        self.client = client

    def question(self, build_ids, identity, error):
        return self.client.query("dotnet/maui", {
            "buildIds": list(build_ids),
            "projection": "case",
            "outcome": "Failed",
            "filters": {**identity, "errorContains": error},
        })

    def inventory(self, build_ids):
        return self.client.query("dotnet/maui", {
            "buildIds": list(build_ids), "projection": "case", "allOutcomes": True,
        })


def original_matches(original, reference, question):
    """Do not repair the indexed name or treat parent IDs as case identity."""
    identity = question["identity"]
    return (
        all(type(original.get(field)) is int and original[field] == reference[wire]
            for field, wire in (("buildId", "buildId"), ("runId", "testRunId"),
                                ("resultId", "testResultId")))
        and original.get("automatedTestName") == question["originalName"]
        and original.get("pipelineId") == identity["pipelineId"]
        and original.get("testRunName") == identity["testRunName"]
        and original.get("outcome") == "Failed"
        and isinstance(original.get("errorMessage"), str)
        and question["error"] in original["errorMessage"]
    )


def failure_in_log(text, title, error):
    # Any result line terminates the block, including a later successful retry.
    blocks = re.split(
        r"(?m)^.*?\b(Failed|Passed|Skipped) (.+?) \[[^\]\n]+\]\s*$", text)
    return any(
        blocks[index] == "Failed" and blocks[index + 1] == title
        and error in blocks[index + 2]
        for index in range(1, len(blocks), 3)
    )


def evaluate(history, question, originals, logs, current_evidence):
    """Consume a validated response; originals/logs are separate caller evidence."""
    expected_query = {
        "buildIds": sorted(question["buildIds"]), "projection": "case",
        "outcome": "Failed",
        "filters": {**question["identity"], "errorContains": question["error"]},
    }
    if history["repository"] != "dotnet/maui" or history["query"] != expected_query:
        raise ValueError("History does not answer this exact MAUI question")
    expected = set(question["buildIds"])
    indexed, verified = set(), set()
    references = []
    for group in history["groups"]:
        indexed.update(group["matchingBuildIds"])
        for reference in group["references"]:
            references.append(deepcopy(reference))
            if reference["testRunId"] is None or reference["testResultId"] is None:
                continue
            if any(original_matches(original, reference, question) for original in originals):
                verified.add(reference["buildId"])
    if not indexed <= expected or not verified <= expected:
        raise ValueError("History contains an out-of-scope build")

    required = expected - verified
    fallback_positives = set()
    fallback_status = {}
    for build in sorted(required):
        evidence = logs.get(build)
        if evidence is None:
            fallback_status[str(build)] = "UNKNOWN: log unavailable"
            continue
        if not (
            evidence.get("buildId") == build
            and evidence.get("pipelineId") == question["identity"]["pipelineId"]
            and evidence.get("testRunName") == question["identity"]["testRunName"]
            and evidence.get("currentTaskVerified") is True
            and isinstance(evidence.get("text"), str)
        ):
            fallback_status[str(build)] = "UNKNOWN: log linkage unverified"
            continue
        if failure_in_log(evidence["text"], question["logTitle"], question["error"]):
            fallback_positives.add(build)
            fallback_status[str(build)] = "observed failure in linked task log"
        else:
            fallback_status[str(build)] = "UNKNOWN: no matching failure in supplied log"

    positives = verified | fallback_positives
    return {
        "indexedBuildIds": sorted(indexed),
        "verifiedParentBuildIds": sorted(verified),
        "reportedReferences": references,
        "requiredFallbackBuildIds": sorted(required),
        "fallbackPositiveBuildIds": sorted(fallback_positives),
        "positiveBuildIds": sorted(positives),
        "unknownBuildIds": sorted(expected - positives),
        "fallbackStatus": fallback_status,
        "currentEvidence": deepcopy(current_evidence),
        "dataCompleteness": "unknown",
        "currentAttempt": "not established by historical observations",
        "prAttribution": "not evaluated; existing caller policy remains required",
    }
