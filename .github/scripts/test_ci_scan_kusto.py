"""Synthetic tests; no network, credentials or raw evidence."""
import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("history", Path(__file__).with_name("ci_scan_kusto.py"))
history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(history)
LOG_SPEC = importlib.util.spec_from_file_location("corpus", Path(__file__).with_name("Validate-CiScanKusto.py"))
corpus = importlib.util.module_from_spec(LOG_SPEC)
with patch.dict("sys.modules", {"ci_scan_kusto": history}):
    LOG_SPEC.loader.exec_module(corpus)

KEY = {"definition_id": 314, "test_name": "SyntheticTest", "arguments": "", "argument_hash": "",
       "queue_name": "synthetic.open", "test_run_name": "SyntheticRun", "signature": "Synthetic error"}
ROW = {"BuildId": 101, "BuildDefinitionId": 314, "Branch": "main", "TestName": "SyntheticTest",
       "Arguments": "", "ArgumentHash": "", "QueueName": "synthetic.open", "TestRunName": "SyntheticRun",
       "Outcome": "Failed", "Message": "Synthetic error", "TestRunId": 1, "TestResultId": 2,
       "RunCompleted": "2026-01-01T00:00:00Z", "IndexedAt": "2026-01-01T00:01:00Z"}


class HintsTests(unittest.TestCase):
    def test_exact_positive(self):
        value = history.hint(KEY, 101, [ROW])
        self.assertEqual("RECURRED", value["state"])
        self.assertEqual(KEY["signature"], value["signature"])

    def test_exact_key_isolation(self):
        for field, value in (("BuildId", 102), ("BuildDefinitionId", 302), ("TestName", "other"),
                             ("Arguments", "other"), ("ArgumentHash", "other"), ("QueueName", "other"),
                             ("TestRunName", "other"), ("Message", "other")):
            with self.subTest(field=field):
                row = dict(ROW, **{field: value})
                self.assertEqual("UNKNOWN", history.hint(KEY, 101, [row])["state"])

    def test_missing_error_and_mixed_outcomes_unknown(self):
        for rows in ([], [dict(ROW, Message="")], [dict(ROW, Outcome="PassedOnRerun")],
                     [ROW, dict(ROW, Outcome="Passed", TestResultId=3)]):
            self.assertEqual("UNKNOWN", history.hint(KEY, 101, rows)["state"])

    def test_missing_key_and_ingestion_time_unknown(self):
        self.assertEqual("UNKNOWN", history.hint(dict(KEY, signature=""), 101, [ROW])["state"])
        for row in (dict(ROW, IndexedAt=None), dict(ROW, IndexedAt="invalid"),
                    dict(ROW, IndexedAt="2025-12-31T00:00:00Z")):
            self.assertEqual("UNKNOWN", history.hint(KEY, 101, [row])["state"])

    def test_provider_error_unknown(self):
        self.assertEqual("UNKNOWN", history.hint(KEY, 101, [ROW], False)["state"])

    def test_uncertified_live_positive_never_allows_log_omission(self):
        with patch.object(history, "structured_candidate", return_value={
                "build_id": 101, "state": "RECURRED", "signature": KEY["signature"]}):
            result = history.consumer_hint(None, KEY, 101, [ROW])
        self.assertEqual("UNKNOWN", result["state"])
        self.assertEqual("uncertified-positive-requires-original-evidence", result["reason"])

    def test_duplicates_deduplicated_but_conflicts_unknown(self):
        self.assertEqual("RECURRED", history.hint(KEY, 101, [ROW, dict(ROW)])["state"])
        self.assertEqual("UNKNOWN", history.hint(KEY, 101, [ROW, dict(ROW, Message="different")])["state"])

    def test_lag_or_final_rerun_unknown(self):
        with patch.object(history, "public_failures", return_value=[]):
            self.assertEqual("UNKNOWN", history.structured_candidate(None, KEY, 101, [ROW])["state"])
        with patch.object(history, "public_failures", side_effect=history.EvidenceError("unavailable")):
            self.assertEqual("UNKNOWN", history.structured_candidate(None, KEY, 101, [ROW])["state"])

    def test_empty_rows_never_mean_negative(self):
        self.assertNotEqual("NOT_RECURRED", history.hint(KEY, 101, [])["state"])

    def test_normalization_preserves_distinctions(self):
        self.assertEqual("Error\nat X", history.normalize_signature("\r\n Error \r\n at X \r\n"))
        for message in ("error", "Error 42", "Error /agent/path", "Error  /agent/path"):
            self.assertEqual(message, history.normalize_signature(message))
        self.assertEqual("", history.normalize_signature("Error (truncated)"))

    def test_window_selection(self):
        values = [{"id": i} for i in range(20, 0, -1)]
        self.assertEqual(list(range(19, 9, -1)), [b["id"] for b in history.select_prior(values, 20)])
        with self.assertRaises(history.EvidenceError):
            history.select_prior(values, 10)

    def test_query_scope_rejected(self):
        for definition, branch, ids in ((0, "main", [1]), (314, "evil", [1]), (314, "main", ["1"])):
            with self.assertRaises(history.EvidenceError):
                history.lane_query(definition, branch, ids)

    def test_raw_evidence_cannot_be_written_inside_repository(self):
        with self.assertRaises(history.EvidenceError):
            history.external_directory(Path(__file__).parent)

    def test_query_and_byte_budgets_fail_before_network(self):
        with tempfile.TemporaryDirectory() as root:
            transport = history.Transport(root, max_bytes=1)
            transport.state["downloaded_bytes"] = 1
            with self.assertRaises(history.BudgetError):
                transport.json_request("synthetic", "https://example.invalid")
            transport.state["downloaded_bytes"] = 0
            transport.max_queries = 0
            with self.assertRaises(history.BudgetError):
                transport.json_request("synthetic", history.KUSTO + "/v1/rest/query", authenticated=True)

    def test_credential_destination_is_allowlisted_before_authentication(self):
        with tempfile.TemporaryDirectory() as root:
            transport = history.Transport(root)
            with patch.object(history.subprocess, "run") as process:
                with self.assertRaisesRegex(history.EvidenceError, "credential-destination-not-allowlisted"):
                    transport.json_request("synthetic", "https://example.invalid", authenticated=True)
                process.assert_not_called()

    def test_credential_stays_in_memory_not_cache_or_receipts(self):
        class Response:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __init__(self):
                self.body = b'{"Tables":[]}'

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, size):
                value, self.body = self.body[:size], self.body[size:]
                return value

        with tempfile.TemporaryDirectory() as root:
            transport = history.Transport(root)
            with patch.object(history.subprocess, "run",
                              return_value=types.SimpleNamespace(returncode=0, stdout=b"synthetic-credential")):
                with patch.object(transport.opener, "open", return_value=Response()) as opened:
                    transport.json_request("kusto-synthetic", history.KUSTO + "/v1/rest/query", {"db": "synthetic"})
                    self.assertNotIn("Authorization", opened.call_args.args[0].headers)
                with patch.object(transport.opener, "open", return_value=Response()) as opened:
                    transport.json_request("kusto-synthetic", history.KUSTO + "/v1/rest/query",
                                           {"db": "synthetic-auth"}, authenticated=True)
                    self.assertEqual("Bearer synthetic-credential", opened.call_args.args[0].headers["Authorization"])
            for file in Path(root).iterdir():
                self.assertNotIn("synthetic-credential", file.read_text())

    def test_missing_queue_stops_before_result_message_download(self):
        class FakeTransport:
            def json_request(self, *args, **kwargs):
                return {"name": "SyntheticRun"}, {}

        with patch.object(history, "public_failures", return_value=[{"runId": 1, "id": 2}]):
            with patch.object(history, "public_detail") as detail:
                keys, unkeyed = history.discover_keys(FakeTransport(), 101, 313)
                detail.assert_not_called()
        self.assertEqual([], keys)
        self.assertEqual("queue-unavailable", unkeyed[0]["reason"])

    def test_messages_required_not_inferred_from_index(self):
        detail = {"automatedTestName": "SyntheticTest", "errorMessage": ""}
        with self.assertRaises(history.EvidenceError):
            history.exact_key(detail, {"name": "Synthetic_ubuntu.2204.amd64.open_Release"}, 314)

    def test_missing_queue_is_not_an_explicit_empty_queue(self):
        with self.assertRaisesRegex(history.EvidenceError, "queue-unavailable"):
            history.exact_key({"automatedTestName": "SyntheticTest", "errorMessage": "Synthetic error"},
                              {"name": "SyntheticRun"}, 313)

    def test_original_binds_signature_only_inside_selected_test_block(self):
        text = "[FAIL] AnotherTest\nSynthetic error\n[FAIL] SyntheticTest\nDifferent error\n[PASS] NextTest"
        self.assertEqual(0, corpus.bound_blocks(text, ["SyntheticTest"], "Synthetic error"))
        self.assertEqual(1, corpus.bound_blocks("[FAIL] SyntheticTest\nSynthetic error\n[PASS] NextTest",
                                              ["SyntheticTest"], "Synthetic error"))

    def test_original_cannot_match_only_a_test_name_elsewhere_in_log(self):
        self.assertEqual(0, corpus.bound_blocks("SyntheticTest\nSynthetic error", ["SyntheticTest"], "Synthetic error"))

    def test_window_bounded_answer_deduplicates_occurrences(self):
        value = corpus.answer([101, 102, 101], {101: "2026-01-02", 102: "2026-01-01"})
        self.assertEqual({"positive_build_ids": [101, 102], "N": 2, "ge_2": True,
                          "first_seen": "2026-01-01", "occurrences": 2}, value)

    def test_query_response_errors_and_truncation_unknown(self):
        class FakeTransport:
            def __init__(self, value):
                self.value = value

            def json_request(self, *args, **kwargs):
                return self.value, {}

        for response in ({"error": {}}, {"Tables": []}, {"Exceptions": ["synthetic"]}):
            with self.assertRaises(history.EvidenceError):
                history.kusto_rows(FakeTransport(response), 314, "main", [101])

    def test_repeated_continuation_fails_closed(self):
        class FakeTransport:
            def json_request(self, *args, **kwargs):
                return {"count": 1, "value": [{"runId": 1, "id": 2}]}, {"continuation": "repeat"}

        with self.assertRaises(history.EvidenceError):
            history.public_failures(FakeTransport(), 101)

    def test_corrupt_cache_cannot_supply_positive(self):
        with tempfile.TemporaryDirectory() as root:
            transport = history.Transport(root, max_bytes=0)
            url = "https://example.invalid"
            cache = Path(root) / (history.digest({"url": url, "payload": None}) + ".json")
            cache.write_text("{}")
            history.write_json(cache.with_suffix(".receipt.json"), {"complete": True, "sha256": "wrong"})
            with self.assertRaises(history.BudgetError):
                transport.json_request("synthetic", url)


if __name__ == "__main__":
    unittest.main()
