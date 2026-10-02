# Decisioncraft for Claude Desktop

A Claude Desktop extension that runs the Decisioncraft MCP server, so Claude Desktop can map a
folder, weigh a choice and draw a canvas without a terminal.

Install: download `decisioncraft.mcpb` from the latest release and double-click it
(or drag it into Claude Desktop → Settings → Extensions). Claude Desktop installs Python and
the package for you. Nothing to set up: Claude does the thinking. Decisioncraft hands Claude the
material and the format, Claude writes the map, and the canvas opens right in the chat. No API key
is asked for or used.

Build: `npx -y @anthropic-ai/mcpb validate manifest.json && npx -y @anthropic-ai/mcpb pack . ../dist/decisioncraft.mcpb`
