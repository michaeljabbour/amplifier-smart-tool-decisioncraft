"""A standard stdio interface for hosts that use MCP. SDK loads only when started."""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise ValueError("Install the mcp extra to use this interface.") from error
    from . import lib

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
            "choice. Support a quick comparison or a careful trial to suit the stakes."
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
