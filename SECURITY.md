# Security and data handling

Analyze repositories you are authorized to inspect. Oni reads source without executing it.
Use `--offline` for local-only acquisition/model behaviour. Reports can contain proprietary
source, absolute paths and secrets already present in files; review them before sharing.
Oni does not apply `.gitignore` or provide automatic secret redaction.

MCP requires explicit allowed roots and always uses offline analysis. It has no authentication
layer because it runs as a local stdio child of your client; do not expose it through an
unauthenticated network bridge. It is not a sandbox or a resource-limit enforcement system.

Remote CLI acquisition requires network access and handles untrusted archives. Tarball links and
special entries are rejected; Git-cloned links are skipped during source reading. Tarball downloads
are capped at 50 MiB, and extraction at 200 MiB / 20,000 entries. Git cloning has a 180-second
timeout but no byte cap. These limits are not a
CPU/memory sandbox; use a disposable environment for hostile inputs.

For suspected vulnerabilities, use GitHub's private vulnerability reporting if enabled on
this repository. Otherwise ask the maintainer for a private reporting route through a minimal
issue without exploit details, credentials or private source. There is no promised response SLA.
