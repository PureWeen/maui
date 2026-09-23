"""New public synthetic boundary tests, not the historical acceptance suite."""

import argparse
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from demo import load_shared
from maui_adapter import MauiHistory, evaluate, failure_in_log
from synthetic import scenario


class MauiTests(unittest.TestCase):
    def setUp(self):
        self.fixture, self.question, self.originals, self.logs, self.current = scenario()

    def query(self, fixture=None):
        with fixture_service(self.fixture if fixture is None else fixture) as client:
            result = MauiHistory(client).question(
                self.question["buildIds"], self.question["identity"], self.question["error"])
            self.assertEqual(1, len(client.receipts))
            return result

    def evaluate(self, history=None):
        return evaluate(self.query() if history is None else history, self.question,
                        self.originals, self.logs, self.current)

    def test_exact_question_and_all_unverified_fallback(self):
        result = self.evaluate()
        self.assertEqual([101, 102], result["indexedBuildIds"])
        self.assertEqual([101], result["verifiedParentBuildIds"])
        self.assertEqual([102, 103, 104, 105, 106], result["requiredFallbackBuildIds"])
        self.assertEqual([101, 103], result["positiveBuildIds"])
        self.assertEqual([102, 104, 105, 106], result["unknownBuildIds"])

    def test_current_evidence_and_attribution_not_replaced(self):
        before = deepcopy(self.current)
        result = self.evaluate()
        self.assertEqual(before, result["currentEvidence"])
        self.assertEqual(before, self.current)
        self.assertIn("not evaluated", result["prAttribution"])
        self.assertEqual("unknown", result["dataCompleteness"])

    def test_overwritten_failure_is_missing_from_failed_index_but_in_log(self):
        result = self.evaluate()
        self.assertNotIn(103, result["indexedBuildIds"])
        self.assertEqual([103], result["fallbackPositiveBuildIds"])
        with fixture_service(self.fixture) as client:
            inventory = MauiHistory(client).inventory(self.question["buildIds"])
        passed = [g for g in inventory["groups"] if g["identity"]["outcome"] == "Passed"]
        self.assertEqual([103], passed[0]["matchingBuildIds"])

    def test_original_identity_checks_are_all_required(self):
        history = self.query()
        for field, bad in (
            ("buildId", 999), ("runId", 999), ("resultId", 999),
            ("automatedTestName", "different"), ("pipelineId", 314),
            ("testRunName", "different"), ("outcome", "Passed"),
            ("errorMessage", "expected width 42"),
        ):
            with self.subTest(field=field):
                originals = deepcopy(self.originals)
                originals[0][field] = bad
                result = evaluate(history, self.question, originals, self.logs, self.current)
                self.assertEqual([], result["verifiedParentBuildIds"])
                self.assertIn(101, result["requiredFallbackBuildIds"])

    def test_missing_parent_reference_stays_unknown(self):
        self.fixture["rows"][0]["TestResultId"] = None
        result = self.evaluate()
        self.assertIn(101, result["indexedBuildIds"])
        self.assertIn(101, result["unknownBuildIds"])
        self.assertIsNone(result["reportedReferences"][0]["testResultId"])

    def test_zero_rows_does_not_skip_any_build(self):
        self.fixture["rows"] = []
        self.logs = {}
        result = self.evaluate()
        self.assertEqual([], result["positiveBuildIds"])
        self.assertEqual(self.question["buildIds"], result["requiredFallbackBuildIds"])
        self.assertEqual(self.question["buildIds"], result["unknownBuildIds"])

    def test_missing_and_unverified_logs_remain_unknown(self):
        self.logs[103]["currentTaskVerified"] = False
        result = self.evaluate()
        self.assertIn(103, result["unknownBuildIds"])
        self.assertIn("unverified", result["fallbackStatus"]["103"])
        self.assertIn("unavailable", result["fallbackStatus"]["106"])

    def test_log_error_cannot_leak_between_tests_or_after_pass(self):
        for text in (
            " Failed FirstNavigation [1 ms]\nOther error\n"
            " Failed DifferentTest [1 ms]\nExpected width 42\n",
            " Failed FirstNavigation [1 ms]\nOther error\n"
            " Passed FirstNavigation [1 ms]\nExpected width 42\n",
        ):
            self.assertFalse(failure_in_log(text, "FirstNavigation", "Expected width 42"))

    def test_duplicate_rows_do_not_inflate_membership_or_references(self):
        self.fixture["rows"].append(deepcopy(self.fixture["rows"][0]))
        result = self.evaluate()
        self.assertEqual([101, 102], result["indexedBuildIds"])
        self.assertEqual(2, len(result["reportedReferences"]))

    def test_empty_queue_is_not_omitted_predicate(self):
        self.fixture["rows"][0]["QueueName"] = None
        self.assertEqual([102], self.evaluate()["indexedBuildIds"])

    def test_each_case_configuration_predicate_is_exact(self):
        for field, value in (
            ("BuildDefinitionId", 314), ("TestName", "OtherTest"),
            ("Arguments", "iOS).FirstNavigation"), ("ArgumentHash", "other-hash"),
            ("QueueName", "other-queue"), ("TestRunName", "other-run"),
            ("WorkItemFriendlyName", "other-workitem"),
        ):
            with self.subTest(field=field):
                fixture = deepcopy(self.fixture)
                fixture["rows"][0][field] = value
                history = self.query(fixture)
                self.assertEqual([102], self.evaluate(history)["indexedBuildIds"])

    def test_five_references_are_three_builds_not_five_executions(self):
        self.fixture["rows"] = [
            {**self.fixture["rows"][0], "BuildId": build, "TestResultId": result}
            for build, result in ((101, 1), (101, 2), (102, 3), (102, 4), (103, 5))
        ]
        history = self.query()
        self.assertEqual([101, 102, 103], history["groups"][0]["matchingBuildIds"])
        self.assertEqual(5, len(history["groups"][0]["references"]))

    def test_partial_invalid_and_unavailable_are_errors_not_empty_success(self):
        from history_http_client import Problem
        for fault, status in (("partial", 502), ("invalid", 502), ("unavailable", 503)):
            with self.subTest(fault=fault):
                self.fixture["fault"] = {"kind": fault}
                with self.assertRaises(Problem) as raised:
                    self.query()
                self.assertEqual(status, raised.exception.status)

    def test_transport_failure_propagates(self):
        from history_http_client import HistoryClient
        with patch.object(HistoryClient, "query", side_effect=OSError("synthetic disconnect")):
            with self.assertRaisesRegex(OSError, "synthetic disconnect"):
                self.query()

    def test_query_scope_cannot_be_reused_for_another_question(self):
        history = self.query()
        self.question["error"] = "different signature"
        with self.assertRaisesRegex(ValueError, "exact MAUI question"):
            self.evaluate(history)

    def test_fixture_listener_and_token_are_removed(self):
        import socket
        from urllib.parse import urlsplit
        with fixture_service(self.fixture) as client:
            port = urlsplit(client.base_url).port
            token = client.token_file
            self.assertTrue(token.exists())
            client.query("dotnet/maui", {
                "buildIds": [101], "projection": "case", "outcome": "Failed"})
        self.assertFalse(token.exists())
        with socket.socket() as probe:
            self.assertNotEqual(0, probe.connect_ex(("127.0.0.1", port)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    fixture_service = load_shared(args.shared_root)
    unittest.main(argv=[sys.argv[0], *remaining])
