#!/usr/bin/env python3
"""SessionStart hook - reference filing, asked once per session.

At the end of an ingest the master PDF can be renamed to the slug and
filed into a reference library. This asks whether that happens, and
where, then the answer is persisted as `$WIKI_REF_FILING` /
`$WIKI_REF_DIR` so sub-agents inherit it and the question is not asked
again.

The library is NOT a replacement for `raw/`. `raw/<vault>/papers/`
holds the converted markdown and the extracted images - the corpus the
wiki was built from, immutable. The library holds the PDFs a human
opens. The source page points at both: `source_file` at the markdown,
`source_pdf` at the master.

Stays silent once `$WIKI_REF_FILING` is set, like the vault and
converter hooks.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

# Already decided for this session.
if os.environ.get("WIKI_REF_FILING", "").strip():
    sys.exit(0)

if not (REPO_ROOT / "tools" / "file_reference.py").is_file():
    sys.exit(0)

configured = os.environ.get("WIKI_REF_DIR", "").strip()
where = (f"A library is already configured: {configured}."
         if configured else
         "No library is configured yet - ask for the path too.")

message = (
    "Reference filing for this session.\n\n"
    "ASK THE USER, once, before the first ingest:\n\n"
    "  Rename the master PDF to its slug and file it in a reference "
    "folder at the end of each ingest? [Yes / No]\n"
    "  If yes: which folder?\n\n"
    f"{where}\n\n"
    "Persist the answer by merging into .claude/settings.local.json "
    "(merge - do NOT clobber the permissions or env blocks already "
    "there):\n\n"
    '  Yes -> { "env": { "WIKI_REF_FILING": "on",\n'
    '                    "WIKI_REF_DIR": "<absolute path>",\n'
    '                    "WIKI_REF_MODE": "copy" } }\n'
    '  No  -> { "env": { "WIKI_REF_FILING": "off" } }\n\n'
    "With `on`, step 21 of the ingest runs\n"
    "  python tools/file_reference.py --source <slug> --apply\n"
    "which files the master as <library>/<theme>/<slug>.pdf and "
    "repoints `source_pdf:`. WIKI_REF_MODE is `copy` (the original is "
    "left alone), `move`, or `rename` (renamed where it is). A master "
    "already inside the library is moved within it rather than "
    "duplicated, whatever the mode.\n\n"
    "It runs LAST, after the DOI lint (step 20): the slug is only "
    "trustworthy once Crossref has confirmed the paper, and a PDF filed "
    "under a wrong slug is worse than one not filed at all.\n\n"
    "This does NOT replace raw/. The converted markdown and the "
    "extracted images stay in raw/<vault>/papers/, which the wiki is "
    "built from and which is immutable. Never point `source_file` at "
    "the library."
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": message,
    }
}))
