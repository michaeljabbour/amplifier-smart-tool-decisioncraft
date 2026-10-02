"""Entry point for the Claude Desktop extension: run the Decisioncraft MCP server over stdio."""

import os

# Empty optional keys from the extension settings must not look like real keys.
for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    if not os.environ.get(key, "").strip() or os.environ.get(key, "").startswith("${"):
        os.environ.pop(key, None)

from decisioncraft.mcp_server import serve  # noqa: E402

if __name__ == "__main__":
    serve()
