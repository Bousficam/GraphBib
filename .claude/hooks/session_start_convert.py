#!/usr/bin/env python3
"""SessionStart hook - conversion backend, asked once per session.

Injects `additionalContext` telling Claude to ask the user, at the top
of the session, whether Mistral stays the default PDF converter, and to
persist the answer as `$WIKI_CONVERT_BACKEND` so sub-agents inherit it
and the question is not asked twice.

It also reports whether a Mistral API key is resolvable right now. That
matters because the failure this whole thing exists to prevent is
silent: with no key the converter used to abort, and the agent moved on
to marker or pymupdf4llm, so the corpus ended up converted by the slow
backend without anyone deciding that. A missing key is a question for
the user, never a reason to change backend.

Stays silent once `$WIKI_CONVERT_BACKEND` is set, exactly like the vault
hook.

Contract: SessionStart hooks may emit a JSON blob on stdout:

    {"hookSpecificOutput":
      {"hookEventName":"SessionStart","additionalContext":"..."}}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

# Already decided for this session - say nothing.
if os.environ.get("WIKI_CONVERT_BACKEND", "").strip():
    sys.exit(0)

# Nothing to convert with: not a GraphBib checkout.
if not (REPO_ROOT / "pdf2md" / "pdf2md_mistral.py").is_file():
    sys.exit(0)


def key_source() -> str | None:
    """Where a Mistral key can be read from right now, or None.

    Mirrors `pdf2md_mistral.get_api_key` so the notice cannot promise a
    key the converter will not find.
    """
    if os.environ.get("MISTRAL_API_KEY", "").strip():
        return "the environment"
    try:
        for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
            name, _, value = line.strip().partition("=")
            if name.strip() == "MISTRAL_API_KEY" and value.strip().strip("'\""):
                return ".env"
    except OSError:
        pass
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["security", "find-generic-password", "-s", "MISTRAL_API_KEY", "-w"],
                capture_output=True, text=True, timeout=5, check=True,
            ).stdout.strip()
            if out:
                return "the macOS keychain"
        except (OSError, subprocess.SubprocessError):
            pass
    return None


src = key_source()
key_line = (
    f"A Mistral API key is available (from {src})."
    if src else
    "NO Mistral API key is reachable (not in the environment, not in .env, "
    "not in the macOS keychain). Ask the user for one BEFORE any conversion, "
    "and offer to save it to the gitignored .env so the next session finds it."
)

message = (
    "Conversion default for this session.\n\n"
    "ASK THE USER, once, before any PDF conversion work:\n\n"
    "  Mistral as the default PDF converter? [Yes / No]\n\n"
    "Then persist the answer by merging into .claude/settings.local.json "
    "(merge - do NOT clobber the permissions or env blocks already there):\n\n"
    '  Yes -> { "env": { "WIKI_CONVERT_BACKEND": "mistral" } }\n'
    '  No  -> { "env": { "WIKI_CONVERT_BACKEND": "ask" } }\n\n'
    "With `mistral`, every conversion starts with "
    "`pdf2md/pdf2md_mistral.py` and the other backends are only reached "
    "for PDFs Mistral actually failed on. With `ask`, ask which backend "
    "to use each time.\n\n"
    f"{key_line}\n\n"
    "NON-NEGOTIABLE: exit code 3 from pdf2md_mistral.py means 'no API "
    "key was found', NOT 'this PDF cannot be converted'. On that code, "
    "ask the user for a key and retry Mistral. Never fall back to "
    "marker or pymupdf4llm because a key is missing - that silently "
    "converts the corpus with the slow backend and nobody decided it. "
    "See docs/workflows/conversion.md."
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": message,
    }
}))
