# Contributing to Resonance

The production branch is currently `master`. All implementation work must go
through a reviewed pull request before it reaches that branch.

## Delivery workflow

1. Choose or create an issue on the
   [Resonance App Roadmap](https://github.com/users/pem2k/projects/5/views/2).
2. Move the issue to **In Progress**.
3. Create a focused branch from the latest `master`:
   - `feat/<short-name>` for a feature
   - `fix/<short-name>` for a bug fix
   - `chore/<short-name>` for maintenance
4. Add behavior-focused tests before implementation when feasible, then make
   the smallest change that satisfies them.
5. Run the focused tests plus the relevant full suite, frontend build, and
   browser checks.
6. Open a pull request linked to the issue and move the issue to **In Review**.
7. Address or explicitly resolve review findings. Do not merge with failing
   required checks or unresolved blockers.
8. Merge the reviewed pull request into `master`, then move the issue to
   **Done**.
9. Deploy production only from the reviewed `master` branch and smoke test the
   affected live routes.

## Production safety

- Never commit API keys, passwords, database URLs, or `.env` files.
- Create and verify a production database backup before schema changes,
  backfills, or destructive data work.
- Include migration, rollback, and live smoke-test notes in the pull request.
- Keep public and admin authorization checks on the server, not only in the UI.

