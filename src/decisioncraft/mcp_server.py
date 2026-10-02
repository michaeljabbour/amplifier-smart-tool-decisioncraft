"""A standard stdio interface for hosts that use MCP. SDK loads only when started."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any

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


def _key_complete():
    """A `complete` from the user's own API key when the host can't sample, or (None, reason).

    Uses the library's own choice of provider and model when it offers one; otherwise
    DECISIONCRAFT_PROVIDER / DECISIONCRAFT_MODEL, then whichever of ANTHROPIC_API_KEY or
    OPENAI_API_KEY is set. Returns (complete, "provider model") or (None, why not).
    """
    import os

    from . import intelligence

    resolve = getattr(intelligence, "default_complete", None) or getattr(intelligence, "resolve_complete", None)
    if resolve is not None:
        try:
            got = resolve()
            if isinstance(got, tuple):
                return got[0], str(got[1])
            return got, "your API key"
        except Exception as error:  # noqa: BLE001 - report why and fall through to the plain message
            return None, str(error)
    provider = os.environ.get("DECISIONCRAFT_PROVIDER") or (
        "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai" if os.environ.get("OPENAI_API_KEY") else ""
    )
    if not provider:
        return None, "No ANTHROPIC_API_KEY or OPENAI_API_KEY is set for the server either."
    model = os.environ.get("DECISIONCRAFT_MODEL") or None
    try:
        return intelligence.provider_complete(provider, model), f"{provider} {model or ''}".strip()
    except Exception as error:  # noqa: BLE001
        return None, str(error)


def _opted_in(name: str) -> bool:
    import os

    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _routing(ctx, loop):
    """Over MCP the host is the model: the calling assistant writes models itself. The server
    calls a model only when the user opted in: MCP sampling with DECISIONCRAFT_ALLOW_SAMPLING=1
    (and a client that offers it), or their own API key with DECISIONCRAFT_ALLOW_KEYS=1.
    Returns (complete, how) or (None, None)."""
    if _opted_in("DECISIONCRAFT_ALLOW_SAMPLING") and _can_sample(ctx):
        return _sampling_complete(ctx, loop), "this host's model (MCP sampling, opted in)"
    if _opted_in("DECISIONCRAFT_ALLOW_KEYS"):
        complete, how = _key_complete()
        if complete is not None:
            return complete, how
    return None, None


YOU_WRITE = (
    "You (the assistant) write this; Decisioncraft checks and draws it. No API key is used and "
    "no other model is called."
)




def _check_target(target: str) -> str:
    """Refuse a path that doesn't exist instead of silently treating it as a topic."""
    from .mapper import check_target

    try:
        return check_target(target)
    except ValueError as error:
        raise ValueError(f"{error} Pass an absolute path, or put a topic in plain words.") from None


def _writable_dir(directory: str) -> None:
    try:
        Path(directory).expanduser().mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ValueError(f"Can't write to {directory}: {error.strerror}. Choose a folder you can write to.") from error


def build_server():
    try:
        from mcp import types
        from mcp.server.fastmcp import Context, FastMCP
    except ImportError as error:
        raise ValueError("Install the mcp extra to use this interface.") from error
    from . import lib
    from .render import APP_MIME, APP_URI, app_html
    from .stats import describe, summary

    # MCP Apps: tools whose result can be drawn declare this view; hosts without MCP Apps
    # ignore it and use the text result.
    VIEW = {"ui": {"resourceUri": APP_URI}, "ui/resourceUri": APP_URI}

    def visual(text: str, data: dict) -> "types.CallToolResult":
        """A short text for the model and text-only hosts; the full data (with the model) for
        the canvas view as structuredContent."""
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], structuredContent=data)

    def you_write(what: str, steps: list[str], sections: list[tuple[str, str]], data: dict) -> "types.CallToolResult":
        """A task for the calling assistant: what to write, the steps, and everything it needs
        (starter, material, model format, writing rules) in the text it reads."""
        import json as _json

        guide = lib.guide()
        body = [YOU_WRITE, "", f"Task: {what}", "", "Steps:"]
        body += [f"{i}. {step}" for i, step in enumerate(steps, 1)]
        for title, text in sections + [("Model format", guide["model_format"]),
                                        ("Writing rules", guide["writing_guide"])]:
            if text:
                body += ["", f"## {title}", "", text if isinstance(text, str) else _json.dumps(text, indent=2, ensure_ascii=False)]
        return types.CallToolResult(
            content=[types.TextContent(type="text", text="\n".join(body))],
            structuredContent={"you_write": True, "what": what, "next": steps, **data},
        )

    active = {}
    server = FastMCP(
        "Decisioncraft",
        log_level="WARNING",
        instructions=(
            "Use Decisioncraft when someone is weighing a real choice, even without saying "
            "'decision': renew or buy, keep or replace, a job offer, a school, a home, vendors, "
            "quotes or plans, 'should I...', 'torn between', 'pros and cons', 'help me think it "
            "through'. Also use it to show how something works and what is missing: a codebase, "
            "a process, meeting notes, 'as-is and to-be', 'where are the gaps'. Not for factual "
            "questions, trivial picks, or code-level choices inside a coding task. In hosts that "
            "show MCP Apps, render, map, example and quick open the canvas right in the chat. "
            "To show how something works and what is missing, call decisioncraft_map with a repo or "
            "folder path, a file, or a topic (it reads the target, then asks this host's model to "
            "draw today's way, the planned way, gaps with user stories and 'done when' checks, and a "
            "note from each role; dry_run shows what it would read). "
            "When someone is weighing options (even without saying 'decision'), call "
            "decisioncraft_triage with their words. Follow its mode: none means just answer; "
            "quick means decisioncraft_quick in the conversation, no files; guided and team mean "
            "decisioncraft_interview_next one question at a time, then render. Offer, don't take "
            "over: ask before building anything. The prompts decide, compare_options, "
            "what_could_go_wrong, regret_test and review_canvas give ready conversation scripts. "
            "For a team review, start with decisioncraft_discover. Ask its opening questions in conversation, "
            "reusing known answers. Follow up on what matters, how to compare and the stakes. "
            "Use the host's own model to build suitable maps, sources, comparison and role notes; "
            "decisioncraft_templates gives shapes. Do not invent evidence, scores or approval. "
            "Validate the model, then start a review. Wait for the person with "
            "decisioncraft_wait_for_review; repeat while the state is open. When finished, "
            "the result includes a handoff. Follow its agent_request: show stories, acceptance "
            "criteria and a proposed map, explain missing parts, and record the owner's reasoned "
            "choice. Support a quick comparison or a careful trial to suit the stakes. "
            "You are the model. decisioncraft_map, decisioncraft_draft, decisioncraft_perspectives "
            "and decisioncraft_review_notes don't call a model themselves: they hand you a task "
            "(the material or digest with path:line evidence, a starter model, the model format "
            "and the writing rules). You write the model JSON in your own turn, then call "
            "decisioncraft_render with it: render validates it and shows the canvas. No API key "
            "is needed or used. Deterministic tools: validate, render, words, questions, merge, "
            "diff, example, triage, quick, interview_next."
        ),
    )
    from .help import VERSION

    server._mcp_server.version = VERSION

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
    def decisioncraft_validate(model: dict, allow_empty: bool = False) -> dict[str, Any]:
        """Check a model before opening it. No credentials or model call. A model with no
        steps, items, ideas or options is an error unless allow_empty is true."""
        problems = lib.validate(model, allow_empty=allow_empty)
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
            from .term import open_in_browser

            open_in_browser(session.url)
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

    @server.tool(structured_output=True, meta=VIEW)
    def decisioncraft_render(
        model: dict,
        directory: str = "",
        filename: str = "canvas.html",
        reviews: list[dict] | None = None,
        merged: dict | None = None,
        since: dict | None = None,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        """Show a decision model: you (the assistant) write the model JSON, then call this to check
        it and draw it. In hosts with MCP Apps the canvas opens right in the chat; it is also saved
        as one offline HTML file. Lists the problems if the model is invalid, and refuses a model
        with no boxes yet unless allow_empty is true."""
        if "/" in filename or "\\" in filename or not filename.endswith(".html"):
            raise ValueError("filename must be a plain name ending in .html, for example canvas.html.")
        if directory:
            _writable_dir(directory)
        folder = Path(directory).expanduser() if directory else Path(tempfile.mkdtemp(prefix="decisioncraft-"))
        folder.mkdir(parents=True, exist_ok=True)
        html = lib.render(model, reviews=reviews, merged=merged, since=since, allow_empty=allow_empty)
        path = folder / filename
        path.write_text(html, encoding="utf-8")
        from .review import diff as diff_models

        if reviews and merged is None:
            merged = lib.merge(reviews, model)
        data = {"path": str(path.resolve()), "bytes": len(html.encode("utf-8")), "summary": summary(model),
                "model": model, "merged": merged, "since": diff_models(since, model) if since else None}
        return visual(f"Drew {model.get('title', 'the map')} ({describe(model)}). Canvas: {data['path']} "
                      "(opens offline in any browser).", data)

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

    @server.tool(structured_output=True, meta=VIEW)
    def decisioncraft_example(name: str) -> dict[str, Any]:
        """Show what a finished map looks like: a worked example by id (map, car, business,
        technical, engineering or medical) with its model, material and reviews. Opens as a
        canvas in hosts with MCP Apps."""
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
        """Turn material ([{name, text}]) into a decision model. You (the assistant) write the
        model: this returns a starter for the template, the model format and the writing rules;
        then call decisioncraft_render with your model to check and show it. No API key is used."""
        loop = asyncio.get_running_loop()
        complete, how = _routing(ctx, loop)
        if complete is None:
            from .model import new_model

            starter = new_model(template if template != "auto" else "decision-chain",
                                title or question, question)
            return you_write(
                f"Write a Decisioncraft model that answers: {question}",
                ["Read the material you were given and decide which maps fit (see the model format).",
                 "Fill in the starter below: maps with boxes, sources and evidence quoted exactly "
                 "from the material, gaps as user stories with 'done when' checks, and a short note "
                 "from each role ending in one question.",
                 "Call decisioncraft_render with model=<your JSON>. Fix any problems it lists and "
                 "call it again; it shows the canvas when the model is valid."],
                [("Starter model", starter)],
                {"starter_model": starter, "question": question},
            )
        model = await asyncio.to_thread(
            lib.draft, material, template=template, question=question, title=title,
            brief=brief, complete=complete,
        )
        return {"model": model, "summary": summary(model), "drafted_with": how}

    @server.tool(structured_output=True)
    async def decisioncraft_perspectives(
        model: dict,
        ctx: Context,
        material: list[dict] | None = None,
        per_role: int = 3,
    ) -> dict[str, Any]:
        """Add a note from each role to a model. You (the assistant) write the notes: this
        returns the roles and the note format; then call decisioncraft_render with the updated
        model. No API key is used."""
        loop = asyncio.get_running_loop()
        complete, how = _routing(ctx, loop)
        if complete is None:
            roles = model.get("roles") or lib.roles()
            return you_write(
                f"Add up to {per_role} notes from each role to the model",
                ["For each role below, add up to " + str(per_role) + " entries to the model's `notes`: "
                 "{id, role, anchor (a box or gap id), title, body, recommend, question, urgency "
                 "(must/should/info), evidence[], author: 'AI assistant'}. Each note ends in one "
                 "question that could change the choice; cite evidence only from the material.",
                 "Call decisioncraft_render with model=<the updated model> to check it and show it."],
                [("Roles", [{"id": r["id"], "label": r.get("label", r["id"]), "asks": r.get("asks", "")} for r in roles])],
                {"model": model, "roles": roles},
            )
        out = await asyncio.to_thread(
            lib.perspectives, model, material=material, per_role=per_role, complete=complete,
        )
        return {"model": out, "summary": summary(out), "drafted_with": how}

    @server.tool(structured_output=True)
    async def decisioncraft_review_notes(
        model: dict,
        review: dict,
        ctx: Context,
        roles: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Expert replies to reviewers' rough notes (a saved answers file). You (the assistant)
        write the replies: this lists each note and the roles to answer it, with the reply format;
        then show them with decisioncraft_render(model, reviews=[review]). dry_run only lists what
        would be asked. No API key is used.
        """
        from .review import check_review, notes_to_ask

        problems = check_review(review)
        if problems:
            raise ValueError(" ".join(problems))
        plan = notes_to_ask(model, review, roles)
        asked = [{"note": p["note"]["id"], "text": p["note"]["text"], "on": p["target"]["title"], "roles": p["roles"]} for p in plan]
        if dry_run or not plan:
            return {"asked": asked, "replies_added": 0, "review": review}
        loop = asyncio.get_running_loop()
        complete, _how = _routing(ctx, loop)
        if complete is None:
            return you_write(
                f"Reply as experts to {len(asked)} reviewer note(s)",
                ["For each note below and each of its roles, add a reply to that note's `replies` in "
                 "the review: {id: '<note id>-<role>', role, view (a short view in that role's voice), "
                 "question (one question that could change the choice), urgency (must/should/info), "
                 "author: 'AI assistant'}. Keep it plain and specific to the note.",
                 "Show the replies to the person in the chat, and call decisioncraft_render with "
                 "model=<the model> and reviews=[<the review with replies>] to draw them as threads."],
                [("Notes to answer", asked)],
                {"asked": asked, "replies_added": 0, "review": review},
            )
        out = await asyncio.to_thread(lib.review_notes, model, review, roles=roles, complete=complete)
        added = sum(len(n.get("replies", [])) for n in out.get("notes", [])) - sum(len(n.get("replies", [])) for n in review.get("notes", []))
        return {"asked": asked, "replies_added": added, "review": out}



    @server.tool(structured_output=True, meta=VIEW)
    async def decisioncraft_map(
        target: str,
        ctx: Context,
        directory: str = "",
        question: str = "",
        roles: list[str] | None = None,
        answers: dict | None = None,
        page_text: str = "",
        dry_run: bool = False,
        starter: bool = False,
    ) -> dict[str, Any]:
        """Show how something works and what is missing ('map this codebase', 'how does X work',
        'as-is and to-be', 'where are the gaps'): point it at a repo or folder path, a notes file,
        a web page's text, or a topic. In hosts with MCP Apps the finished map opens in the chat.

        Reads the target, then asks this host's model (MCP sampling) to draw how it works today
        with evidence by file and line, a planned way, gaps with user stories and 'done when'
        checks, and a note from each role. Writes model.json and canvas.html to `directory` and
        returns their paths. dry_run returns what would be read and asked, with no model call.
        For a web address pass the page's text in page_text; for a topic pass answers
        {how_today, pain, goal} if you have them.

        You (the assistant) draw the map: this reads the target and returns the material digest
        (numbered lines to cite as path:line), a starter model, the model format and the writing
        rules. Fill in the starter in your own turn, then call decisioncraft_render with it; render
        checks it and shows the canvas. No API key is used. Don't stop at a text summary when
        someone asked to see the map. Pass `directory` to also save the starter files.
        """
        target = _check_target(target)
        if directory:
            _writable_dir(directory)
        if dry_run:
            return {"plan": lib.plan_map(target, roles=roles, answers=answers)}
        loop = asyncio.get_running_loop()
        complete = how = None
        if not starter:
            complete, how = _routing(ctx, loop)
        if complete is None:
            import json as _json

            st = await asyncio.to_thread(lib.map_starter, target, roles=roles, question=question,
                                         answers=answers, page_text=page_text)
            paths = {}
            if directory:
                folder = Path(directory).expanduser()
                (folder / "material").mkdir(parents=True, exist_ok=True)
                (folder / "model.json").write_text(_json.dumps(st["model"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                (folder / "material" / "digest.md").write_text(st["digest"], encoding="utf-8")
                (folder / "FILL-IN.md").write_text(st["instructions"], encoding="utf-8")
                paths = {"model_path": str((folder / "model.json").resolve()),
                         "digest_path": str((folder / "material" / "digest.md").resolve()),
                         "instructions_path": str((folder / "FILL-IN.md").resolve())}
            return you_write(
                f"Draw the map of {target}: how it works today, how it could work, the gaps, and a note from each role",
                ["Read the material digest below. Each line starts with its number: cite evidence as "
                 "'path:line' and quote the words exactly.",
                 "Fill in the starter model: today's steps (status works/partial/missing, with evidence), "
                 "the planned steps (status planned, `replaces` where one replaces a today step), the gaps "
                 "as user stories with 'done when' checks, and one note per role in `roles`, each "
                 "pointing at a box and ending in one question.",
                 "Call decisioncraft_render with model=<your filled-in model>. It refuses an empty map "
                 "and lists any problems; fix them and call it again. When valid it shows the canvas."],
                [("Starter model", st["model"]), ("Material digest", st["digest"])],
                {"starter": True, "starter_model": st["model"], "plan": st["plan"], **paths},
            )
        result = await asyncio.to_thread(
            lib.map_target, target, roles=roles, question=question, answers=answers, page_text=page_text,
            complete=complete)
        model = result["model"]
        folder = Path(directory).expanduser() if directory else Path(tempfile.mkdtemp(prefix="decisioncraft-map-"))
        folder.mkdir(parents=True, exist_ok=True)
        import json as _json

        (folder / "model.json").write_text(_json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (folder / "canvas.html").write_text(lib.render(model), encoding="utf-8")
        data = {"model_path": str((folder / "model.json").resolve()), "canvas_path": str((folder / "canvas.html").resolve()),
                "summary": summary(model), "plan": result["plan"], "drafted_with": how, "model": model}
        return visual(f"Mapped {target} ({describe(model)}). Model: {data['model_path']}; canvas: {data['canvas_path']}. "
                      f"Drafted with {how}.", data)

    # ------------------------------------------------------------ modes

    @server.tool(structured_output=True)
    def decisioncraft_triage(
        text: str = "", cost: str = "", reversible: str = "", people: str = "", deadline: str = ""
    ) -> dict[str, Any]:
        """Start here when someone is weighing options: 'should I...', 'renew or buy', 'keep or
        replace', 'torn between', a job offer, vendors. Says how much help the choice needs: none
        (just answer), quick, guided or team. No model call.

        Pass the person's own words in `text` and anything you know. Returns the mode, why,
        questions worth asking, and a sentence to offer help without taking over.
        """
        answers = {k: v for k, v in {"cost": cost, "reversible": reversible, "people": people,
                                     "deadline": deadline}.items() if v}
        return lib.triage(answers, text=text)

    @server.tool(structured_output=True, meta=VIEW)
    def decisioncraft_quick(
        options: list[str],
        criteria: list[str] | None = None,
        scores: list[dict] | None = None,
        question: str = "",
    ) -> dict[str, Any]:
        """Quick side-by-side for a choice ('which is better', 'keep or replace', comparing a few
        options): score options against what matters; returns a Markdown table, a lean and one
        check, and the scoring table as a canvas in hosts with MCP Apps.

        criteria: most important first; prefix 'must:' or 'nice:'. scores: [{option, criterion,
        score 1-5, why}] using names. No files and no model call; show the table in the chat.
        """
        from .modes import quick_model

        result = lib.quick(options, criteria, scores, question=question)
        if result.get("options") and result.get("criteria"):
            result["model"] = quick_model(result)
        return result

    @server.tool(structured_output=True)
    def decisioncraft_interview_next(
        directory: str, answer: str | None = None, question: str = "", kind: str | None = None,
        reset: bool = False,
    ) -> dict[str, Any]:
        """Guided mode for a choice worth a closer look (a car, a home, a job, a vendor): record
        the answer, get the next question (ask it in your own words).

        Repeat until done; finishing writes model.json and material/README.txt in `directory`,
        then call decisioncraft_render. kind: personal, team or system (default chosen for you).
        """
        _writable_dir(directory)
        return lib.interview_step(directory, answer, question=question, kind=kind, reset=reset)

    # ------------------------------------------------------------ MCP Apps view

    @server.resource(
        APP_URI, name="Decisioncraft canvas", mime_type=APP_MIME,
        description="The decision map canvas: today and planned, what changes, scores, costs and "
        "every role's notes, drawn from a tool result. Self-contained; no outside requests.",
        meta={"ui": {"csp": {}, "prefersBorder": False}},
    )
    def decisioncraft_canvas_view() -> str:
        return app_html()

    @server.tool(structured_output=True, meta={"ui": {"resourceUri": APP_URI, "visibility": ["app"]}})
    def decisioncraft_save_review(review: dict, directory: str = "") -> dict[str, Any]:
        """Save a reviewer's answers from the canvas (called by the canvas view, not the model).

        Writes the review JSON to `directory` (default: DECISIONCRAFT_REVIEWS_DIR, else
        ~/Decisioncraft/reviews) and returns its
        path, so the agent can read, merge or hand off the answers."""
        import json as _json
        import time as _time

        from .review import check_review

        problems = check_review(review)
        if problems:
            raise ValueError(" ".join(problems))
        import os as _os

        default = _os.environ.get("DECISIONCRAFT_REVIEWS_DIR") or str(Path.home() / "Decisioncraft" / "reviews")
        folder = Path(directory or default).expanduser()
        _writable_dir(str(folder))
        who = "".join(ch if ch.isalnum() else "-" for ch in str(review.get("reviewer") or "reviewer").lower()).strip("-") or "reviewer"
        path = folder / f"review-{who}-{_time.strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(_json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        answered = len(review.get("answers") or {})
        return {"path": str(path.resolve()), "answered": answered}

    # ------------------------------------------------------------ prompts

    @server.prompt()
    def map_this(target: str = "") -> str:
        """Show how something works today, what could be better, and what each role thinks."""
        return (
            f"Show me how {target or '(ask me what: a repo or folder path, some notes, a page or a topic)'} "
            "works today and what is missing.\n\nCall decisioncraft_map with dry_run first and tell me in "
            "two lines what it will read. Then call decisioncraft_map to draw it. Tell me where the "
            "canvas is, summarise the as-is and to-be in three sentences each, list the gaps with "
            "their user stories, and ask me the two most urgent questions from the role notes."
        )

    @server.prompt()
    def decide(situation: str = "") -> str:
        """Help someone think a choice through, at the right depth."""
        return (
            "Help me think this choice through"
            + (f": {situation}" if situation else ".")
            + "\n\nFirst call decisioncraft_triage with my words. Then follow the mode it returns: "
            "just answer if it is small; for quick, ask what matters, call decisioncraft_quick and "
            "show the table, the lean and the one thing to check; for guided or team, ask before "
            "building anything, then ask the decisioncraft_interview_next questions one at a time "
            "in your own words and render the canvas at the end. Keep it plain and short."
        )

    @server.prompt()
    def compare_options(options: str = "", what_matters: str = "") -> str:
        """Lay options side by side against what matters, in the conversation."""
        return (
            f"Compare these options: {options or '(ask me for them)'}. What matters: "
            f"{what_matters or '(ask me, most important first, and whether anything is a must-have)'}."
            "\n\nAsk me for a rough 1 to 5 for each option on each point where you do not know. "
            "Then call decisioncraft_quick and show its table, the lean with its reason, and the "
            "one thing to check first. Say it is a lean, not a verdict."
        )

    @server.prompt()
    def what_could_go_wrong(choice: str = "") -> str:
        """A pre-mortem: imagine it went badly and work out why, then guard against it."""
        return (
            f"Imagine it is a year from now and this choice went badly: {choice or '(ask me what I chose)'}."
            "\n\nList the five most likely reasons, most likely first, each with an early warning "
            "sign and one thing I could do now to guard against it. Keep each to a line. End with "
            "the single cheapest check I could make this week."
        )

    @server.prompt()
    def regret_test(options: str = "") -> str:
        """How each option is likely to feel in 10 days, 10 months and 10 years."""
        return (
            f"For each option ({options or 'ask me for them'}), describe in a sentence how I am "
            "likely to feel about it in 10 days, 10 months and 10 years, as a small table. Then say "
            "which option I would most likely regret not taking, and why. Ask me one question if "
            "the answer depends on something you do not know about me."
        )

    @server.prompt()
    def review_canvas(model_path: str = "") -> str:
        """Walk someone through a Decisioncraft canvas and collect their answers."""
        return (
            f"Help me review the decision map at {model_path or '(ask me for the model.json path)'}."
            "\n\nRead it with decisioncraft_words. Summarise the choice in two sentences, then go "
            "through decisioncraft_questions most urgent first, one at a time, and record my answers. "
            "Offer to open the canvas with decisioncraft_render or a live review with "
            "decisioncraft_start_review if I would rather click through it."
        )

    # ------------------------------------------------------------ resources

    @server.resource("decisioncraft://templates", mime_type="application/json")
    def templates_resource() -> str:
        """The map templates: id, kind, title and what each is for."""
        import json as _json

        return _json.dumps(lib.templates(), ensure_ascii=False)

    @server.resource("decisioncraft://roles", mime_type="application/json")
    def roles_resource() -> str:
        """The default roles and the question each always asks."""
        import json as _json

        return _json.dumps(lib.roles(), ensure_ascii=False)

    @server.resource("decisioncraft://model-format", mime_type="text/markdown")
    def model_format_resource() -> str:
        """Every field of the decision model, with its rules."""
        from .lib import guide

        return guide()["model_format"]

    @server.resource("decisioncraft://writing-guide", mime_type="text/markdown")
    def writing_guide_resource() -> str:
        """How to write models and notes in plain words."""
        from .intelligence import _guide

        return _guide()

    @server.resource("decisioncraft://interview-questions", mime_type="application/json")
    def interview_resource() -> str:
        """The interview's questions by set (personal, team, system), with why each is asked."""
        import json as _json

        return _json.dumps(lib.interview_questions(), ensure_ascii=False)

    @server.resource("decisioncraft://modes", mime_type="application/json")
    def modes_resource() -> str:
        """The four modes (none, quick, guided, team) and what each does."""
        import json as _json

        return _json.dumps(lib.modes(), ensure_ascii=False)

    @server.resource("decisioncraft://examples", mime_type="application/json")
    def examples_resource() -> str:
        """The worked examples and what each shows."""
        import json as _json

        return _json.dumps([{"name": e["id"], "about": e["about"]} for e in lib.example_names()],
                           ensure_ascii=False)

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
