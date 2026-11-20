# Worktree operations — conditional checklist

Only read after the user explicitly needs an isolated worktree or an actual cleanup.

## Read-only preflight
- Record `git --no-pager --no-optional-locks -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all --ignore-submodules=none`, `git branch --show-current`, `git worktree list`, base HEAD.
- Classify user's pre-existing dirty paths. Do not stash/commit/reset files or overwrite untracked paths without explicit separate instructions.
- Check whether `.worktrees/`, `worktrees/` or a project-approved external path is already in use and safely ignored; never assume a directory exists.
- Record the isolation goal, `scope_write`, potential shared contract and local device/cache dependencies.

## Authorized creation
- Only after authorization and exact base/source identity, use the target project's reviewed worktree creation method. Validate branch uniqueness, path nonexistence, `.gitignore` exclusions, setup and sample test.
- Do not create executable handoff scripts or automatically run commands from artifacts supplied by worker threads.

## Authorized cleanup
- Show exact created path, parent repo, creator/source evidence, dirty/untracked state, branch reachability, and desired keep/merge/discard decision.
- No destructive command without explicit approval and independent provenance; no silent branch force-delete or `git clean`.
- Re-verify after integration; inability to prove safe deletion means keep and report blocker.

## Unattended execution (only when requested)
- `Automation Risk Decision`: explicit owner, authorized write scope, stop condition, recovery/rollback.
- `Heartbeat / Staleness Threshold`: if stale, pause/replan; never add scheduled model polling when event-driven hooks suffice.
