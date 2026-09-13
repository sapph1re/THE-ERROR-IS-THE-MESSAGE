# #65: Archive repository conversations and media with verifiable recovery

https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/65

State: open; created: 2026-09-13T09:24:30Z

Related to #60. A normal git clone does not preserve issue/PR conversations or uploaded media. This adds a dependency-free Python exporter that saves the public repository's issues, PRs, full comments/reviews, releases, tag metadata, release assets, and GitHub-uploaded files alongside readable Markdown, raw JSON, source mappings and SHA-256 checksums.

Large files are preserved in ordered 48 MiB chunks with a restoration command that verifies each part and the complete original. Missing, inaccessible, oversized or truncated downloads produce a nonzero exit and an explicitly incomplete manifest. Reruns verify cached files before reusing them.

Validation so far: 14 local regression tests pass, including pagination, reply context, attachment formats, credential handling on redirects, incomplete downloads, reruns, corrupt caches, lossless large-file reconstruction, and exact text-file preservation through a real Git round trip with line-ending conversion enabled. A full run against this repository is in progress. The initial live run exposed GitHub's legacy attachment S3 host and malformed URLs in discussion text; both are now handled. Media discovery also excludes fixture URLs inside code diffs while preserving the diffs themselves. **The complete target-repository demonstration is not yet claimed; this PR remains draft until that verification finishes.**

The phone-friendly manual Actions workflow is supplied as `docs/repository-archive.workflow.yml`, with installation and operation instructions in `docs/REPOSITORY_ARCHIVE.md`. GitHub rejected registering the workflow with my current credential because it lacks the `workflow` permission. The template therefore needs a one-time owner copy to `.github/workflows/repository-archive.yml`; no hosted Actions run is claimed. It writes the archive to a dedicated branch and does not replace the source branch.

The documentation explicitly distinguishes this sequential public API snapshot from an atomic backup, and lists unavailable/deleted data, native GitHub Discussions and other out-of-scope resources. No external paid service or new credentials are required by the tool itself.


## Conversation

## Reviews

## Inline review comments
