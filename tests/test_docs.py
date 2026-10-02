"""The docs a newcomer follows: every command they show must parse, and the skill must load anywhere."""

import contextlib
import glob
import io
import re
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["README.md", "src/decisioncraft/SMART_TOOL.md", "skills/decisioncraft/SKILL.md",
        *sorted(glob.glob(str(ROOT / "docs" / "*.md"))), *sorted(glob.glob(str(ROOT / "contracts" / "*.md")))]


def _commands():
    for doc in DOCS:
        path = ROOT / doc
        text = path.read_text()
        for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
            block = re.sub(r"\\\n\s*", " ", block)
            for line in block.splitlines():
                line = line.strip().lstrip("$ ").strip()
                if not line.startswith("decisioncraft ") or "..." in line or "<" in line:
                    continue
                cmd = line.split(" #")[0].split(" && ")[0].split(" | ")[0].strip()
                yield path.name, cmd


@pytest.mark.parametrize("doc,cmd", list(_commands()))
def test_every_documented_command_parses(doc, cmd):
    from decisioncraft.cli import build

    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            build().parse_args(shlex.split(cmd)[1:])
    except SystemExit as e:
        assert not e.code, f"{doc}: {cmd!r}\n{err.getvalue()}"


def _front(path):
    text = (ROOT / path).read_text()
    return text.split("---")[1]


def test_skill_frontmatter_loads_in_strict_and_naive_parsers():
    front = _front("skills/decisioncraft/SKILL.md")
    data = yaml.safe_load(front)
    assert data["name"] == "decisioncraft"
    desc = data["description"]
    assert 0 < len(desc) <= 1024  # the Agent Skills limit Amplifier and Codex enforce
    # A naive `key: value` line reader (some loaders) must get the whole description too.
    line = next(ln for ln in front.splitlines() if ln.startswith("description:"))
    assert line.split(":", 1)[1].strip() == desc
    assert ": " not in desc and " #" not in desc


def test_skill_manifest_and_help_share_one_description():
    import decisioncraft as dc

    skill = yaml.safe_load(_front("skills/decisioncraft/SKILL.md"))["description"]
    manifest = yaml.safe_load(_front("src/decisioncraft/SMART_TOOL.md"))["description"]
    assert skill == manifest == dc.manifest()["description"]


def test_readme_tells_a_newcomer_which_model_answers():
    readme = (ROOT / "README.md").read_text()
    first = readme.index("## First run")
    assert first < readme.index("## Point it at anything")
    section = readme[first:readme.index("## Point it at anything")]
    for must in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_PROVIDER", "--complete-cmd", "--starter",
                 "decisioncraft doctor"):
        assert must in section


def test_hosts_doc_lists_every_tool_prompt_and_resource():
    pytest.importorskip("mcp")
    from decisioncraft.mcp_server import build_server

    built = build_server()
    server = built[0] if isinstance(built, tuple) else built
    hosts = (ROOT / "docs" / "HOSTS.md").read_text()
    names = [t.name for t in server._tool_manager.list_tools()]
    names += [p.name for p in server._prompt_manager.list_prompts()]
    names += [str(r.uri) for r in server._resource_manager.list_resources()]
    missing = [n for n in names if n not in hosts]
    assert not missing, f"docs/HOSTS.md does not mention: {missing}"
