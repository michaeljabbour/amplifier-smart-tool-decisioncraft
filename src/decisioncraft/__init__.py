"""Decisioncraft: map how a problem works, gather every point of view, and decide together."""

from .help import VERSION as __version__  # noqa: F401 -- single source of the version
from .lib import (  # noqa: F401
    discover,
    handoff,
    diff,
    draft,
    manifest,
    merge,
    new,
    perspectives,
    questions,
    render,
    roles,
    session,
    templates,
    validate,
    words,
)
