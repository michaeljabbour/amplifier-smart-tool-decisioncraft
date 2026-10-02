"""A standard stdio interface for hosts that use MCP. SDK loads only when started."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any

NO_SAMPLING = (
    "This host does not offer MCP sampling, so Decisioncraft can't ask the host's model. "
    "Use your own model instead: call decisioncraft_templates for the shapes and writing "
    "guide, write the model JSON, then call decisioncraft_validate."
)


def _sampling_complete(ctx, loop):
    """A `complete(system, prompt)` that asks the host's own model through MCP sampling.

    The library's model-backed functions are synchronous and run in a worker thread; each
    call is handed back to the server's event loop, where the session lives.
    """
    from mcp import types

    def complete(system: str, prompt: str) -> str:
        coro = ctx.session.create_message(
            messages=[types.SamplingMessage(role="user", content=types.TextContent(type="text", text=prompt))],
            max_tokens=16000,
            system_prompt=system,
        )
        result = asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=900)
        content = result.content
        if isinstance(content, list):
            return "".join(getattr(c, "text", "") for c in content)
        return getattr(content, "text", "") or ""

    return complete


def _can_sample(ctx) -> bool:
    from mcp import types

    try:
        return ctx.session.check_client_capability(types.ClientCapabilities(sampling=types.SamplingCapability()))
    except Exception:  # an older or unusual client: treat as no sampling
        return False


def build_server():
    try:
        from mcp.server.fastmcp import Context, FastMCP
    except ImportError as error:
        raise ValueError("Install the mcp extra to use this interface.") from error
    from . import lib
    from .stats import summary

    active = {}
    server = FastMCP(
        "Decisioncraft",
        instructions=(
            "Start with decisioncraft_discover. Ask its opening questions in conversation, "
            "reusing known answers. Follow up on what matters, how to compare and the stakes. "
            "Use the host's own model to build suitable maps, sources, comparison and role notes; "
            "decisioncraft_templates gives shapes. Do not invent evidence, scores or approval. "
            "Validate the model, then start a review. Wait for the person with "
            "decisioncraft_wait_for_review; repeat while the state is open. When finished, "
            "the result includes a handoff. Follow its agent_request: show stories, acceptance "
            "criteria and a proposed map, explain missing parts, and record the owner's reasoned "
            "choice. Support a quick comparison or a careful trial to suit the stakes. "
            "Deterministic tools need no model: validate, render (writes an HTML canvas and "
            "returns its path), words, questions, merge, diff and example. decisioncraft_draft "
            "and decisioncraft_perspectives ask this host's model through MCP sampling; if the "
            "host has no sampling they fail and say so, and you draft with your own model."
        ),
    )

    @server.tool(structured_output=True)
    def decisioncraft_discover(question: str = "") -> dict[str, Any]:
        """Begin with a few questions about the choice, why it matters and a useful visual."""
        return lib.discover(question)

    @server.tool(structured_output=True)
    def decisioncraft_templates() -> dict[str, Any]:
        """Get supported map shapes and the writing guide for the host's own model."""
        from .model import new_model
        from .intelligence import _guide

        return {
            "templates": lib.templates(),
            "shapes": [new_model(t["id"], "", "The choice") for t in lib.templates()],
            "writing_guide": _guide(),
        }

    @server.tool(structured_output=True)
    def decisioncraft_validate(model: dict) -> dict[str, Any]:
        """Check a model before opening it. No credentials or model call."""
        problems = lib.validate(model)
        return {
            "valid": not any(p["level"] == "error" for p in problems),
            "problems": problems,
        }

    @server.tool(structured_output=True)
    def decisioncraft_start_review(
        model: dict,
        directory: str = "",
        review: dict | None = None,
        source_root: str | None = None,
        prepared_by: str = "AI assistant",
        open_browser: bool = True,
    ) -> dict[str, Any]:
        """Open a browser review. Answers save directly for this agent; no file transfer."""
        session = lib.session(
            model,
            directory or tempfile.mkdtemp(prefix="decisioncraft-"),
            review=review,
            source_root=source_root,
            prepared_by=prepared_by,
        )
        key = session.base.rsplit("/", 1)[-1]
        active[key] = session
        if open_browser:
            import webbrowser

            webbrowser.open(session.url)
        return {
            **session.info(),
            "session_id": key,
            "next": "Call decisioncraft_wait_for_review. When finished, read the returned handoff and follow its agent_request.",
        }

    @server.tool(structured_output=True)
    async def decisioncraft_wait_for_review(
        session_id: str, timeout: float = 25
    ) -> dict[str, Any]:
        """Wait briefly for Finish review, then return answers and the completed handoff."""
        if session_id not in active:
            raise ValueError("This review session was not found.")
        if not 0 <= timeout <= 30:
            raise ValueError("Timeout must be between 0 and 30 seconds.")
        session = active[session_id]
        await asyncio.to_thread(session.wait, timeout)
        return {**session.status(), "session_id": session_id}

    @server.tool(structured_output=True)
    def decisioncraft_render(
        model: dict,
        directory: str = "",
        filename: str = "canvas.html",
        reviews: list[dict] | None = None,
        merged: dict | None = None,
        since: dict | None = None,
    ) -> dict[str, Any]:
        """Draw a model as one offline HTML canvas and return where it was written."""
        if "/" in filename or "\\" in filename or not filename.endswith(".html"):
            raise ValueError("filename must be a plain name ending in .html, for example canvas.html.")
        folder = Path(directory).expanduser() if directory else Path(tempfile.mkdtemp(prefix="decisioncraft-"))
        folder.mkdir(parents=True, exist_ok=True)
        html = lib.render(model, reviews=reviews, merged=merged, since=since)
        path = folder / filename
        path.write_text(html, encoding="utf-8")
        return {"path": str(path.resolve()), "bytes": len(html.encode("utf-8")), "summary": summary(model)}

    @server.tool(structured_output=True)
    def decisioncraft_words(model: dict, reviews: list[dict] | None = None) -> dict[str, Any]:
        """The whole model as readable Markdown, for people who prefer text or for reading back."""
        merged = lib.merge(reviews, model) if reviews else None
        return {"markdown": lib.words(model, merged)}

    @server.tool(structured_output=True)
    def decisioncraft_questions(model: dict, reviews: list[dict] | None = None) -> dict[str, Any]:
        """Every question to decide, most urgent first; reviewers' dots and answers change the order."""
        merged = lib.merge(reviews, model) if reviews else None
        return {"questions": lib.questions(model, merged)}

    @server.tool(structured_output=True)
    def decisioncraft_merge(model: dict, reviews: list[dict]) -> dict[str, Any]:
        """Combine saved reviews: agree and disagree counts, dots, comments and conflicts."""
        return lib.merge(reviews, model)

    @server.tool(structured_output=True)
    def decisioncraft_diff(old: dict, new: dict) -> dict[str, Any]:
        """What was added, removed and changed between two versions of a model."""
        return lib.diff(old, new)

    @server.tool(structured_output=True)
    def decisioncraft_example(name: str) -> dict[str, Any]:
        """A worked example (business, technical, engineering or medical): model, material, reviews."""
        return lib.example(name)

    @server.tool(structured_output=True)
    async def decisioncraft_draft(
        material: list[dict],
        question: str,
        ctx: Context,
        template: str = "auto",
        title: str = "",
        brief: dict | None = None,
    ) -> dict[str, Any]:
        """Draft a full model from material ([{name, text}]) using this host's model via sampling."""
        if not _can_sample(ctx):
            raise ValueError(NO_SAMPLING)
        loop = asyncio.get_running_loop()
        model = await asyncio.to_thread(
            lib.draft, material, template=template, question=question, title=title,
            brief=brief, complete=_sampling_complete(ctx, loop),
        )
        return {"model": model, "summary": summary(model)}

    @server.tool(structured_output=True)
    async def decisioncraft_perspectives(
        model: dict,
        ctx: Context,
        material: list[dict] | None = None,
        per_role: int = 3,
    ) -> dict[str, Any]:
        """Add notes from each role to a model using this host's model via sampling."""
        if not _can_sample(ctx):
            raise ValueError(NO_SAMPLING)
        loop = asyncio.get_running_loop()
        out = await asyncio.to_thread(
            lib.perspectives, model, material=material, per_role=per_role,
            complete=_sampling_complete(ctx, loop),
        )
        return {"model": out, "summary": summary(out)}

    @server.tool(structured_output=True)
    def decisioncraft_handoff(model: dict, review: dict) -> dict[str, Any]:
        """Read a completed review as answers, proposed stories, checks and a proposed map."""
        return lib.handoff(model, review)

    @server.tool(structured_output=True)
    def decisioncraft_close_review(session_id: str) -> dict[str, Any]:
        """Close a browser review after reading its handoff. Saved files remain."""
        if session_id not in active:
            raise ValueError("This review session was not found.")
        session = active.pop(session_id)
        session.close()
        return session.status()

    return server, active


def serve():
    """Run the standard stdio server and close its local sessions when the host leaves."""
    server, active = build_server()
    try:
        server.run(transport="stdio")
    finally:
        for session in active.values():
            session.close()
