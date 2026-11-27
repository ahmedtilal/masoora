# Issue tracker

Masoora tracks issues and specs in GitHub Issues. Use `gh` with `--repo ahmedtilal/masoora` for issue and label commands.

## Issue operations

- Publish a spec or ticket with `gh issue create`. Use a heredoc for a multi-line body.
- Fetch a ticket with `gh issue view <number> --json number,title,body,labels,comments`.
- Find tickets with `gh issue list` and the relevant `--state` and `--label` filters.
- Record parent-child relationships with GitHub sub-issues. If unavailable, add the child to the parent's task list and add `Part of #<parent>` to the child body.
- Record blockers with GitHub issue dependencies. If unavailable, add `Blocked by: #<number>` to the child body. A ticket becomes startable when every blocker is closed.
- Change triage labels with `gh issue edit --add-label` or `--remove-label`. Use the names in `triage-labels.md`.
- Post a closing explanation with `gh issue comment`, then close the ticket with `gh issue close`.

**PRs as a request surface: no.**

## Wayfinding

- Use one issue labeled `wayfinder:map` for the map. Keep notes, decisions, and open questions in its body.
- Link tickets as children of the map and label them `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- Choose the first open, unassigned child in map order whose blockers are all closed. Claim it with `gh issue edit <number> --add-assignee @me` before starting work.
- Resolve a ticket by posting the answer and closing it. Add a short decision and a link to the answer in the map's Decisions-so-far section.
