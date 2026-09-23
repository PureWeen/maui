"""Invented fixtures, not captures of historical MAUI executions."""


def scenario():
    identity = {
        "pipelineId": 313, "testName": "Example.LayoutTests",
        "arguments": "Android).FirstNavigation", "argumentHash": "",
        "queue": "", "testRunName": "synthetic-android-ui",
        "workItemFriendlyName": "synthetic-layout",
    }
    question = {
        "buildIds": list(range(101, 107)), "identity": identity,
        "originalName": "Example.LayoutTests(Android).FirstNavigation",
        "logTitle": "FirstNavigation", "error": "Expected width 42",
    }
    base_row = {
        "BuildDefinitionId": 313, "TestName": identity["testName"],
        "Arguments": identity["arguments"], "ArgumentHash": "", "QueueName": "",
        "TestRunName": identity["testRunName"],
        "WorkItemFriendlyName": identity["workItemFriendlyName"],
        "Outcome": "Failed", "JobName": None, "WorkItemId": None,
        "WorkItemName": None, "Message": question["error"],
    }
    rows = [
        {**base_row, "BuildId": build, "TestRunId": build + 1000,
         "TestResultId": build + 2000}
        for build in range(101, 106)
    ]
    rows[2]["Outcome"] = "Passed"
    rows[2]["Message"] = ""
    rows[3]["QueueName"] = "different-configuration"
    rows[4]["Message"] = "expected width 42"
    fixture = {
        "builds": [
            {"id": build, "repository": {"id": "dotnet/maui"},
             "project": {"name": "public"}, "definition": {"id": 313}}
            for build in question["buildIds"]
        ],
        "rows": rows,
    }
    originals = [
        {"buildId": build, "runId": build + 1000, "resultId": build + 2000,
         "automatedTestName": question["originalName"], "pipelineId": 313,
         "testRunName": identity["testRunName"], "outcome": "Failed",
         "errorMessage": question["error"]}
        for build in (101, 102)
    ]
    originals[1]["automatedTestName"] = "Example.LayoutTests(iOS).FirstNavigation"
    log_text = {
        103: "  Failed FirstNavigation [1 ms]\nExpected width 42\n"
             "  Passed FirstNavigation [1 ms]\n",
        104: "  Failed FirstNavigation [1 ms]\nDifferent error\n",
        105: "  Failed UnrelatedTest [1 ms]\nExpected width 42\n",
    }
    logs = {
        build: {"buildId": build, "pipelineId": 313,
                "testRunName": identity["testRunName"],
                "currentTaskVerified": True, "text": text}
        for build, text in log_text.items()
    }
    current = {"buildId": 999, "headVerified": False, "timelineReadable": False}
    return fixture, question, originals, logs, current
