# #61: feat: add mobile-friendly repository dump workflow

https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/61

State: open; created: 2026-09-13T08:36:28Z

## Summary

Implements the repository dump tool requested in #60.

- Adds a mobile-friendly `workflow_dispatch` workflow with `source_repository`, output directory, and attachment controls.
- Exports all issues, pull requests, issue comments, reviews, inline review comments, releases, release notes, tags, and release assets through the GitHub REST API.
- Downloads GitHub-hosted attachments referenced by discussions while leaving ordinary external links untouched.
- Writes deterministic JSON indexes plus a manifest with counts, hashes, and failed-download records.
- Uses only the Python standard library; no paid service or third-party dependency is required.

## Validation

- `python -m unittest discover -s tests -v`
- `python -m py_compile tools/repo_dump.py`
- `git diff --check`
- Authenticated read-only smoke run against this repository: 60 issues and 4 releases discovered.

The workflow can be started from GitHub's web or mobile Actions UI and commits the resulting dump into `repo-dump/`.


## Conversation

## Reviews

## Inline review comments
