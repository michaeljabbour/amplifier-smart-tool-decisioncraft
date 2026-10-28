# Install Decisioncraft

Install the native tool in an isolated environment with Python 3.11+ and `uv`:

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
decisioncraft doctor
```

The optional provider and MCP extras are installed by this line. They are imported only when needed. No provider is called by installation, doctor, `new`, `validate` or `render`.

## Your first canvas

The following example is fictional. Use a new checkout directory; `first-canvas.html` is a new local output file:

```sh
git clone https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft.git
cd amplifier-smart-tool-decisioncraft
decisioncraft validate examples/engineering/model.json
decisioncraft render examples/engineering/model.json --out first-canvas.html
```

Open `first-canvas.html` in a browser. Explore the claims, options and role notes. Use `decisioncraft new --help` to create a separate starter for your own decision and fill its model from your evidence before validating or rendering it. Validation checks structure; it does not establish that the claims, scores or options are correct.

## Portable skill with code execution

Download the complete [91-file archive](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/downloads/decisioncraft-skill.zip). Keep its library, references and license together in a `decisioncraft` folder supported by your host. The small canonical method folder alone is not the whole Smart Tool. The archive includes 90 native payload files and the MIT notice.

The source site builder is `python3 scripts/build-site.py`. The README and native Smart Tool guide explain optional model routing and MCP setup. Installation and offline conformance checks do not establish outside-user benefit.
