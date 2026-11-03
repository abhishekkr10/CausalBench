# Development guide

Use Python 3.13 on Windows for the currently exercised environment. The Python
application has no third-party runtime dependencies. Start from the repository
root; modules use local project files and controller sources.

```powershell
python -m causalbench.server --port 8767
python -m unittest discover -s tests -v
node --check web/app.js
node --check web/lab.js
```

Node is needed for JavaScript syntax and browser development checks. Run `npm ci`,
`npx playwright install chromium`, then `npm run test:browser`. The application
itself still requires no Node runtime. The full
test suite exercises native controllers and requires the native example; Windows
has a supplied binary. Rebuild it with the command in README.md, and update the
build manifest if intentionally replacing it. Other platforms require a matching
native build and validation.

Web files are served directly: reload after HTML/CSS/JS edits. Restart the server
after Python changes; loaded source snapshots are intentionally frozen for
reproducibility. For foreground development, Ctrl+C stops the server. The
background launcher writes output to data/server.log.

Before submitting a change:
- Preserve trace schema and existing archive/replay behavior, or document migration.
- Add meaningful tests for changed logic and run the relevant existing checks.
- For UI changes, verify actual API results, keyboard behavior, both themes,
  narrow layouts, reduced motion and visible error states.
- Update current_status.md, docs/VALIDATION.md and docs/ROADMAP.md as appropriate.
- Keep credentials, recordings, SQLite files, generated evidence and logs out of Git.

Do not enable physical actuation as a side effect of a software/UI change.
Do not execute untrusted native plugins or imported archive source. This server
is intended for a trusted local machine, not unauthenticated public hosting.

The repository is licensed under MIT; retain the copyright and license notice.
