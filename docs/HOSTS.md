# Use the same decision workflow in any host

The Python library and CLI expose discovery, drafting, validation, review and handoff.
The optional MCP server gives a host standard tools without choosing a model provider.
The host can use its own model to draft the JSON and ask the person questions.

Install the adapter:

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
```

Run `decisioncraft mcp` as the stdio server. In a host that uses an `mcpServers` config:

```json
{
  "mcpServers": {
    "decisioncraft": {
      "command": "/absolute/path/to/decisioncraft",
      "args": ["mcp"]
    }
  }
}
```

Use the installed executable's full path if the host does not inherit your shell's PATH.
Each host has its own setup; this tool does not rewrite those configurations.

The agent workflow is the same everywhere:

1. Call discover and ask a few questions in conversation. Reuse known answers.
2. Follow up on what matters, realistic options, how to compare and the stakes.
3. Draft suitable maps and a comparison. Use the host's model, or the draft capability.
4. Validate, then start a review. Answers save on the same computer.
5. Wait for completion. MCP uses `decisioncraft_wait_for_review` with a bounded timeout;
   repeat while the state is open. CLI uses `session --until-finished`.
6. Read the returned handoff. Show stories, acceptance criteria and the proposed-state
   map, identify missing parts, and help the owner make and record a reasoned choice.

MCP returns both structured content and a text JSON version. Library and CLI callers get
the same data. Completion returns through the waiting tool call; it does not send an
unsolicited message to an idle host. A remote host still needs access to the local review
service to open it; the default service binds only to this computer.
