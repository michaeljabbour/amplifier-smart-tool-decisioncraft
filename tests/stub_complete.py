"""A --complete-cmd for tests: reads {system, prompt} JSON on stdin, prints the stub reply."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "src")]
import stub_map  # noqa: E402

request = json.load(sys.stdin)
sys.stdout.write(stub_map.complete(request["system"], request["prompt"]))
