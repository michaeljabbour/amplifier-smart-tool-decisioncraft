"""A private local review: browser answers are written where the host can read them.

The offline canvas stays offline. This separate mode accepts requests only on this
computer, at a random address, and writes validated review files atomically.
"""

from __future__ import annotations

import copy
import json
import secrets
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .model import require_valid
from .render import _embed, render
from .review import blank_review, check_review, fingerprint
from .workflow import handoff, handoff_words


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


class ReviewSession:
    """A running local review. Read status(), wait for finish, then close()."""

    def __init__(
        self, model: dict, directory, *, review=None, source_root=None, prepared_by="", complete=None
    ):
        require_valid(model)
        self._complete = complete  # a model routing for Ask the experts; None = file handoff instead
        self.model = copy.deepcopy(model)
        if not isinstance(prepared_by, str):
            raise ValueError("Prepared by must be text.")
        self.prepared_by = prepared_by
        self.close_on_finish = False
        self.directory = Path(directory).resolve()
        if (self.directory / "session.json").exists():
            raise ValueError("This session folder already exists. Choose a new folder.")
        self._review = copy.deepcopy(
            review if review is not None else blank_review(model)
        )
        self._check(self._review)
        if self.directory.exists() and any(self.directory.iterdir()):
            raise ValueError("Choose an empty folder for this review session.")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self._handoff = None
        self.review_file = self.directory / "review.json"
        self.session_file = self.directory / "session.json"
        self._lock = threading.RLock()
        self._finished = threading.Event()
        self._version = 0
        self._state = "open"
        self._finished_at = ""
        self._sources = {}
        self._source_root = (
            Path(source_root).resolve() if source_root is not None else None
        )
        if source_root is not None:
            root = Path(source_root).resolve()
            for source in model.get("sources", []):
                ref = source.get("ref", "")
                if not isinstance(ref, str) or urlsplit(ref).scheme:
                    continue
                target = (root / ref).resolve()
                if target.is_relative_to(root) and target.is_file():
                    self._sources[source["id"]] = target
        token = secrets.token_urlsafe(24)
        self.base = "/review/" + token
        session = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, data, kind="application/json; charset=utf-8"):
                body = data if isinstance(data, bytes) else json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data: blob:; connect-src 'self'",
                )
                self.end_headers()
                self.wfile.write(body)

            def allowed(self):
                return (
                    self.headers.get("Host") == session.address
                    and not urlsplit(self.path).query
                )

            def do_GET(self):
                if not self.allowed():
                    return self.reply(403, {"error": "This address is not allowed."})
                path = urlsplit(self.path).path
                if path == session.base + "/":
                    with session._lock:
                        bridge = dict(
                            id=token,
                            base=session.base,
                            state=session._state,
                            review=session._review,
                            handoff=session._handoff,
                            version=session._version,
                            prepared_by=session.prepared_by,
                            experts=session._complete is not None,
                            close_on_finish=session.close_on_finish,
                            sources={
                                k: session.base + "/source/" + k
                                for k in session._sources
                            },
                        )
                        page = render(session.model).replace(
                            "img-src data: blob:",
                            "img-src data: blob:; connect-src 'self'",
                        )
                        page = page.replace(
                            '<script type="application/json" id="dc-model">',
                            '<script type="application/json" id="dc-session">'
                            + _embed(bridge)
                            + '</script>\n<script type="application/json" id="dc-model">',
                        )
                    return self.reply(200, page.encode(), "text/html; charset=utf-8")
                if path == session.base + "/status":
                    return self.reply(200, session.status())
                if path.startswith(session.base + "/source/"):
                    source = session._sources.get(
                        path.removeprefix(session.base + "/source/")
                    )
                    if source:
                        try:
                            if not source.resolve().is_relative_to(
                                session._source_root
                            ):
                                return self.reply(
                                    403,
                                    {
                                        "error": "This source is outside the allowed folder."
                                    },
                                )
                            if source.stat().st_size > 2_000_000:
                                return self.reply(
                                    413,
                                    {"error": "This source is too large to show here."},
                                )
                            data = source.read_text(encoding="utf-8").encode()
                        except (OSError, UnicodeError):
                            return self.reply(
                                404, {"error": "This source cannot be read here."}
                            )
                        return self.reply(200, data, "text/plain; charset=utf-8")
                return self.reply(404, {"error": "This page was not found."})

            def experts(self):
                """Ask the experts about one reviewer note; replies come back, nothing is saved."""
                if session._complete is None:
                    return self.reply(501, {"error": "This review was started without a model, so experts cannot reply here. Save your answers and use the command shown."})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 200_000:
                        return self.reply(413, {"error": "The note is too large or empty."})
                    value = json.loads(self.rfile.read(length))
                    note = value.get("note") if isinstance(value, dict) else None
                    roles = value.get("roles") if isinstance(value, dict) else None
                    if not isinstance(note, dict) or not isinstance(roles, list) or not roles:
                        raise ValueError("Send a note and the roles to ask.")
                    note = {**note, "ask": {"roles": roles}, "replies": [r for r in note.get("replies", []) if isinstance(r, dict)]}
                    mini = {**blank_review(session.model), "notes": [note]}
                    from .intelligence import review_notes
                    out = review_notes(session.model, mini, roles=roles, complete=session._complete)
                    return self.reply(200, {"replies": out["notes"][0].get("replies", [])})
                except (ValueError, TypeError, UnicodeError) as error:
                    return self.reply(400, {"error": str(error)})
                except Exception as error:  # the model call failed; say so plainly
                    return self.reply(502, {"error": f"The experts could not reply: {error}"})

            def do_POST(self):
                path = urlsplit(self.path).path
                if (
                    not self.allowed()
                    or self.headers.get("Origin") != session.origin
                    or self.headers.get("Content-Type", "").split(";")[0]
                    != "application/json"
                ):
                    return self.reply(403, {"error": "This request is not allowed."})
                if path == session.base + "/experts":
                    return self.experts()
                if path not in (session.base + "/answers", session.base + "/finish"):
                    return self.reply(404, {"error": "This page was not found."})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2_000_000:
                        return self.reply(
                            413, {"error": "The answers are too large or empty."}
                        )
                    value = json.loads(self.rfile.read(length))
                    if not isinstance(value, dict):
                        raise ValueError("Expected a review and version.")
                    with session._lock:
                        if value.get("version") != session._version:
                            return self.reply(
                                409,
                                {
                                    "error": "This review changed in another tab. Download a backup of your changes, then reload."
                                },
                            )
                        session._check(value.get("review"))
                        review = copy.deepcopy(value["review"])
                        review["saved_at"] = _now()
                        completed = handoff(session.model, review) if path.endswith("/finish") else None
                        if completed:
                            _write(session.directory / "handoff.json", completed)
                            (session.directory / "user-stories.md").write_text(handoff_words(completed), encoding="utf-8")
                            if completed["proposed_model"]:
                                _write(session.directory / "proposed-model.json", completed["proposed_model"])
                                (session.directory / "proposed-canvas.html").write_text(render(completed["proposed_model"]), encoding="utf-8")
                        session._handoff = completed
                        _write(session.review_file, review)
                        session._review = review
                        session._version += 1
                        session._state = (
                            "finished" if path.endswith("/finish") else "open"
                        )
                        session._finished_at = (
                            _now() if session._state == "finished" else ""
                        )
                        if session._state == "open":
                            session._finished.clear()
                        session._receipt()
                        self.reply(
                            200,
                            {
                                "version": session._version,
                                "saved_at": review["saved_at"],
                                "handoff": session._handoff,
                            },
                        )
                        if session._state == "finished":
                            session._finished.set()
                except (ValueError, TypeError, UnicodeError) as error:
                    return self.reply(400, {"error": str(error)})
                except OSError:
                    return self.reply(
                        500,
                        {
                            "error": "The answers could not be saved. Keep this page open and try again."
                        },
                    )

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.address = "127.0.0.1:" + str(self._server.server_port)
        self.origin = "http://" + self.address
        self.url = self.origin + self.base + "/"
        _write(self.review_file, self._review)
        self._receipt()
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _check(self, review):
        problems = check_review(review)
        if problems:
            raise ValueError(" ".join(problems))
        if review.get("model_fingerprint") != fingerprint(self.model):
            raise ValueError("These answers belong to another version of the decision.")
        if review.get("model") != self.model.get("title"):
            raise ValueError("These answers belong to another decision.")
        notes = {n["id"] for n in self.model.get("notes", [])}
        decisions = {d["id"] for d in self.model.get("decisions", [])}
        if (
            set(review.get("answers", {})) - notes
            or set(review.get("dots", {})) - notes
        ):
            raise ValueError(
                "These answers refer to questions that are not in this decision."
            )
        if set(review.get("decisions", {})) - decisions:
            raise ValueError("These answers refer to an unknown decision.")

    def _receipt(self):
        _write(self.session_file, self.info())

    def info(self):
        return dict(
            format="decisioncraft-session/1",
            url=self.url,
            state=self._state,
            version=self._version,
            review_file=str(self.review_file),
            handoff_file=str(self.directory / "handoff.json") if self._handoff else None,
            session_file=str(self.session_file),
            status_url=self.origin + self.base + "/status",
            finished_at=self._finished_at,
        )

    def status(self):
        with self._lock:
            return {**self.info(), "review": copy.deepcopy(self._review), "handoff": copy.deepcopy(self._handoff)}

    def wait(self, timeout=None):
        return self._finished.wait(timeout)

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        with self._lock:
            self._state = "closed"
            self._receipt()


def session(
    model: dict, directory, *, review=None, source_root=None, prepared_by="", complete=None
) -> ReviewSession:
    """Open a local review that saves responses for its host without file handoff.

    complete: optional model routing (`complete(system, prompt)`); with it, reviewers can
    press Ask the experts on their rough notes and get replies in the page.
    """
    return ReviewSession(
        model,
        directory,
        review=review,
        source_root=source_root,
        prepared_by=prepared_by,
        complete=complete,
    )
