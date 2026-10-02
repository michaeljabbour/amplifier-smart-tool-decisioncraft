"""One error type for the command line and hosts: what went wrong, what to do, and an exit code.

The library raises its own errors (`ModelError`, `ProviderError`, `ValueError`, `OSError`).
`classify` turns any of them into a `ToolError` so every surface reports failures the same way.
"""

from __future__ import annotations

# Exit codes. Documented in contracts/cli.v1.md; keep the two in step.
OK = 0
INPUT = 1  # the input has problems: a missing file, bad JSON, an invalid model or review
USAGE = 2  # the command line itself is wrong: unknown command or flag, missing argument
SETUP = 3  # something must be installed or set first: a provider key, an extra, write access
MODEL_CALL = 4  # a language model was asked and the call failed or its reply stayed invalid
INTERRUPTED = 130  # stopped with Ctrl-C before finishing

EXIT_CODES = {
    OK: "Finished.",
    INPUT: "The input has problems (missing file, bad JSON, invalid model or review).",
    USAGE: "The command line is wrong (unknown command or flag, missing argument).",
    SETUP: "Something must be set up first (provider key, optional package, write access).",
    MODEL_CALL: "A model call failed, or its reply was still invalid after one repair.",
    INTERRUPTED: "Stopped with Ctrl-C before finishing.",
}


class ToolError(Exception):
    """A failure with a stable code, a plain message and the next thing to try."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str = "",
        exit_code: int = INPUT,
        file: str | None = None,
        field: str | None = None,
        problems: list[dict] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.exit_code = exit_code
        self.file = file
        self.field = field
        self.problems = problems or []

    def as_dict(self) -> dict:
        out = {"code": self.code, "message": self.message, "hint": self.hint}
        if self.file is not None:
            out["file"] = self.file
        if self.field is not None:
            out["field"] = self.field
        if self.problems:
            out["problems"] = self.problems
        return out


# Phrases the library uses when a provider is not set up, as opposed to a failed call.
_SETUP_PHRASES = ("Set ", "Install the", "Unknown provider", "Name a model", "Pass --provider",
                  "No model is set up", "The anthropic provider needs", "The openai provider needs")


def classify(error: BaseException, *, file: str | None = None, model_backed: bool = False) -> ToolError:
    """Turn a library error into a ToolError with a code, a hint and an exit code."""
    from .intelligence import ProviderError
    from .model import ModelError

    if isinstance(error, ToolError):
        return error
    if isinstance(error, ModelError):
        problems = list(error.problems)
        first = problems[0] if problems else {}
        if model_backed:
            return ToolError(
                "reply_invalid",
                "The model's reply still had problems after a repair (and the stronger model, if one was available).",
                hint="Run the same command again with the other provider (add --provider openai, or "
                "--provider anthropic --model claude-opus-5-5). For map, --starter lets you or your agent "
                "fill it in instead. The problems are listed below.",
                exit_code=MODEL_CALL,
                problems=problems,
            )
        return ToolError(
            "invalid_model",
            f"The model has {len(problems)} problem{'s' if len(problems) != 1 else ''} to fix first.",
            hint=f"Run: decisioncraft validate {file}" if file else "Run decisioncraft validate on the file.",
            file=file,
            field=first.get("path"),
            problems=problems,
        )
    if isinstance(error, ProviderError):
        text = str(error)
        if text.startswith(_SETUP_PHRASES):
            return ToolError(
                "provider_not_configured",
                text,
                hint="Check with: decisioncraft doctor   Pick one for good with: decisioncraft config set "
                "provider anthropic   Or route through your own model: --complete-cmd 'your-command'",
                exit_code=SETUP,
            )
        return ToolError(
            "model_call_failed",
            text,
            hint="Check the command or provider, then run again. Add --debug for details.",
            exit_code=MODEL_CALL,
        )
    if isinstance(error, PermissionError):
        return ToolError(
            "no_write_access",
            f"Can't write to {error.filename or 'that place'}.",
            hint="Choose a folder you can write to with --out or --dir.",
            exit_code=SETUP,
            file=error.filename,
        )
    if isinstance(error, FileNotFoundError):
        return ToolError(
            "file_not_found",
            f"Can't find {error.filename or file or 'the file'}.",
            hint="Check the path. To start a new model, run: decisioncraft new",
            file=error.filename or file,
        )
    if isinstance(error, OSError):
        return ToolError("file_error", str(error), hint="Check the path and try again.", file=file)
    if isinstance(error, ValueError):
        if model_backed:
            return ToolError(
                "model_call_failed", str(error),
                hint="Run again, or add --debug for details.", exit_code=MODEL_CALL,
            )
        return ToolError("invalid_input", str(error), hint="Check the input and try again.", file=file)
    if model_backed:
        return ToolError(
            "model_call_failed",
            f"The model call failed: {error}",
            hint="Check your provider or --complete-cmd, then run again. Add --debug for details.",
            exit_code=MODEL_CALL,
        )
    return ToolError(
        "unexpected",
        f"Something went wrong: {error}",
        hint="Run again with --debug to see the details, and report it if it keeps happening.",
    )
