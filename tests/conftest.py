"""Tests never call a real model: clear provider keys and use a throwaway config file."""

import os
import tempfile


def pytest_configure(config):
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_PROVIDER", "DECISIONCRAFT_MODEL",
                "DECISIONCRAFT_DEBUG_DIR", "DECISIONCRAFT_HOST"):
        os.environ.pop(key, None)
    # The suite may itself run inside an agent harness; host detection must not leak into tests.
    from decisioncraft.intelligence import HOST_MARKERS

    for _name, keys in HOST_MARKERS:
        for key in keys:
            os.environ.pop(key, None)
    os.environ["DECISIONCRAFT_CONFIG"] = os.path.join(tempfile.mkdtemp(prefix="dc-test-"), "config.json")
