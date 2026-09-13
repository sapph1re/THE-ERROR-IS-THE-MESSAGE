# Repository history dump

Exports the GitHub API history for a repository and downloads its uploaded attachments. Python 3.10+, no packages or paid services required. AI-assisted implementation by Codex for Roman Vinogradov (@sapph1re).

## Mobile operation

Install `dump.py` and `restore.py` at `tools/repository-dump/` and the supplied workflow at `.github/workflows/repository-dump.yml` on the default branch. In a mobile web browser, open the repository's **Actions**, choose **Save repository history**, then **Run workflow**. Use the default branch. No local computer or personal token is needed for the workflow.

The workflow writes `archive/` on the dedicated `repository-archive` branch, leaving the default branch untouched. Older snapshots remain in that branch's Git history. Branch rules must permit the workflow token to push there. GitHub Actions availability and usage limits apply; this tool does not purchase runner time or storage.

The optional source-repository input can name another public repository for a demonstration. Leave it blank for normal use. Private repositories require appropriate token permissions; the default workflow token is scoped to the hosting repository.

## Local operation

```sh
python3 dump.py OWNER/REPO --output archive --max-download-mib 2048
python3 restore.py archive restored-assets
python3 -m unittest discover -s tests -v
```

An optional `GH_TOKEN` or `GITHUB_TOKEN` gives access to the repository within that token's permissions and raises the API rate limit. The token goes only to `api.github.com` and is removed on cross-host redirects. No token values or signed redirect URLs are saved. Use a least-privilege token with repository metadata, issues, pull requests and contents read access. The exporter itself never writes to GitHub.

## Included

- All open and closed issues and PRs, their original Markdown, authors, timestamps, comments and issue events.
- PR details, reviews, inline review comments (including reply relationships), and commit metadata.
- Releases, release notes, paginated uploaded release assets, source tarballs/ZIPs, and tags.
- GitHub-hosted user-uploaded attachments referenced in the exported text. URLs inside nested records and HTML image attributes are recognized. Media is retained as binary bytes, never executed.
- Raw JSON records, a navigable Markdown index, source URL mappings, SHA-256 checksums and explicit failures.

Assets are split into 40 MiB parts to stay below GitHub's single-file limit. `restore.py` reassembles them and verifies both part and full-file checksums. The manifest retains original release filenames when available, content type, original URL and byte size. Uploaded media without a filename uses a stable URL-derived identifier.

## Completeness and limits

Exit code 0 means all requests and downloads in the documented scope completed. Any failed request or download produces an **INCOMPLETE** manifest and exit code 1. The workflow saves that partial result for inspection and remains visibly failed. A download cap does not silently truncate a successful archive. Raise the cap and rerun into a fresh output folder when appropriate.

This is an API snapshot, not a Git mirror. Clone/mirror the repository separately for every source commit and Git object. Deleted content, content unavailable to the token, external websites, GitHub Discussions, Actions artifacts/logs, wiki history, LFS objects, and files that never finished uploading are outside this export's scope. PR commit metadata is subject to GitHub's endpoint limit. It is not a point-in-time transaction: changes during a run may require another export after activity stops. Public attachments are supported; private attachment URLs that require interactive browser authentication are reported as inaccessible rather than bypassed.

Large repositories can exceed Actions disk, runtime or repository storage limits even when each file is small enough. Check the manifest and storage needs before relying on the archive. The tool never deletes the source repository or invokes downloaded code.
