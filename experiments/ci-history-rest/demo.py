"""Run the new synthetic MAUI example over the canonical loopback HTTP service."""

import argparse
import json
from pathlib import Path
import sys

from maui_adapter import MauiHistory, evaluate
from synthetic import scenario


def load_shared(root):
    root = Path(root).resolve()
    for name in ("fixture_service.py", "history_http_client.py", "openapi.json"):
        if not (root / name).is_file():
            raise ValueError(f"--shared-root must contain {name}")
    sys.path.insert(0, str(root))
    from fixture_service import fixture_service
    return fixture_service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", required=True, type=Path)
    args = parser.parse_args()
    fixture_service = load_shared(args.shared_root)
    fixture, question, originals, logs, current = scenario()
    with fixture_service(fixture) as client:
        history = MauiHistory(client).question(
            question["buildIds"], question["identity"], question["error"])
        result = evaluate(history, question, originals, logs, current)
        result["successfulHttpRequests"] = len(client.receipts)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
