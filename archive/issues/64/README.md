# #64: Repo dump tool: mobile-triggered Actions workflow + stdlib Python exporter (#60)

https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/64

State: open; created: 2026-09-13T09:15:10Z

Implements the repo dump tool from #60.

## What it does

A dependency-free Python 3 exporter (`tools/repo_dump.py`, standard library only) plus a `workflow_dispatch` GitHub Actions workflow, so the whole dump is triggered from a phone: Actions tab -> repo-dump -> Run workflow. No laptop, no local setup, one green button for any team member.

It exports, for open **and** closed items (`state=all`):

- **Issues**: full text, labels, assignees, milestone, reactions, complete comment threads
- **Pull requests**: full text, issue comments, **reviews**, and **inline review comments** (path + line), head/base refs, merge state
- **Releases**: notes, tags, draft/prerelease flags, and the actual **artifact binaries**
- **Attachments**: every `user-attachments` / `user-images` file inside issue/PR/review/release bodies is downloaded into `assets/`, sha256 recorded, and links in the dumped Markdown are rewritten to the local paths so the dump is self-contained

Output lands back in the repo on a configurable branch (default `repo-dump`): one Markdown + one JSON per item, `index.md` summary, and a `manifest.json` with counts, per-asset checksums/sizes and an explicit `failures` list - a failed download is reported, never silently treated as a complete backup.

## Test evidence

- Unit tests: `python3 -m unittest discover -s tests -v` - 7/7 pass (attachment extraction, dedup, issue/PR separation, markdown rewriting, manifest, failure-is-reported-not-fatal)
- Live read-only run against `attogram/attogram`: 12 issues, 3 PRs, 15 releases exported, 24 API requests, 0 failures
- Full acceptance run against this repository (test 1: consume this issue) COMPLETED: https://github.com/navaneethvenu/THE-ERROR-IS-THE-MESSAGE/actions/runs/34749758922 - all 60 issues, 5 PRs, 4 releases exported; 393 attachments downloaded into `assets/` with sha256 checksums, **0 failed downloads**; output committed to the fork's [`repo-dump` branch](https://github.com/navaneethvenu/THE-ERROR-IS-THE-MESSAGE/tree/repo-dump)

## Literal readings of the spec worth noting

- "Dumps ... back into the repository" = committed to a branch of the repo, not pushed elsewhere. Default branch `repo-dump` keeps `main` clean; configurable via workflow input.
- "Executable from a mobile phone" = GitHub mobile web Actions UI (`workflow_dispatch`); also runnable from any shell with `GITHUB_TOKEN` set.
- Dumping a different repo from the fork works for public repos with the automatic `GITHUB_TOKEN`; private cross-repo targets would need a PAT secret.

Files: `tools/repo_dump.py`, `tests/test_repo_dump.py`, `.github/workflows/repo-dump.yml`, `REPO-DUMP.md` (docs kept in a separate file so the repo's own README is untouched).


## Conversation

### navaneethvenu (2026-09-13T09:47:55Z)

https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/64#issuecomment-5652532035

Acceptance run finished (test 1 - this repository consumed by the tool):

**Run:** https://github.com/navaneethvenu/THE-ERROR-IS-THE-MESSAGE/actions/runs/34749758922 (success)

- 60 issues, 5 pull requests, 4 releases - full text, complete comment threads, PR reviews and inline review comments
- 393 attachments/artifacts downloaded into `assets/`, each with sha256 + byte size in `manifest.json`; **0 failed downloads**
- Dumped Markdown rewrites attachment links to local paths, so the export is self-contained
- Output: https://github.com/navaneethvenu/THE-ERROR-IS-THE-MESSAGE/tree/repo-dump (start at `index.md`)
- Unit tests: 8/8 via `python3 -m unittest discover -s tests -v`

Triggered by `workflow_dispatch` from the Actions tab - one tap from a phone browser, no local environment.


## Reviews

## Inline review comments
