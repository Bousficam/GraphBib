#!/usr/bin/env python3
"""SessionStart hook - vault selection prompt.

When the repo holds multiple wiki vaults (or the wiki/raw layout is
ambiguous), inject `additionalContext` telling Claude to ask the user
which vault to use for the session and persist the choice as
`$WIKI_VAULT`. Stays silent in single-vault, legacy, or empty modes
so first-time / single-domain repos see no extra context.

Contract: SessionStart hooks may emit a JSON blob on stdout. We use:

    {"hookSpecificOutput":
      {"hookEventName":"SessionStart","additionalContext":"..."}}
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
sys.path.insert(0, str(REPO_ROOT / "tools"))

try:
    from _lib import ACTIVE_VAULT_MODE, list_raw_vaults, list_vaults  # type: ignore
except Exception:
    # _lib not importable (fresh clone, missing yaml) → stay silent.
    sys.exit(0)

# If the user already picked a vault for this shell, don't re-prompt.
if os.environ.get("WIKI_VAULT", "").strip():
    sys.exit(0)

wiki = list_vaults()
raw = list_raw_vaults()
union = sorted(set(wiki) | set(raw))

ambiguous = ACTIVE_VAULT_MODE == "ambiguous" or len(union) >= 2
if not ambiguous:
    sys.exit(0)

message = (
    f"Multi-vault GraphBib detected. Available vaults: {', '.join(union)}.\n\n"
    "BEFORE running any wiki tool (tools/ingest.py, tools/lint.py, "
    "tools/query.py, tools/health.py, tools/suggest_readings.py, etc.) "
    "or any /wiki-* slash command, ASK THE USER which vault to use for "
    "this session.\n\n"
    "Once chosen, persist it for the whole session by merging into "
    ".claude/settings.local.json:\n\n"
    '  { "env": { "WIKI_VAULT": "<chosen-vault>" } }\n\n'
    "(merge with the existing settings.local.json - do NOT clobber "
    "the permissions block).\n\n"
    "Alternative: prefix every Bash tool call with "
    "WIKI_VAULT=<chosen-vault>. The settings.local.json route is "
    "preferred since it survives sub-agents and avoids forgetting "
    "the prefix."
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": message,
    }
}))
