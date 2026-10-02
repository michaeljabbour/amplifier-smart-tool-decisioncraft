"""Entry point for the Claude Desktop extension: run the Decisioncraft MCP server over stdio.

In Claude Desktop, Claude does the thinking: the model-backed tools hand Claude a task and
Claude writes the model, so the extension asks for no API key and reads none.
"""

import os

os.environ.setdefault("DECISIONCRAFT_HOST", "Claude Desktop")
for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_ALLOW_KEYS"):
    os.environ.pop(key, None)

from decisioncraft.mcp_server import serve  # noqa: E402

if __name__ == "__main__":
    serve()
