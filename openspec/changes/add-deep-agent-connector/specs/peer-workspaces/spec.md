# Spec Delta

## MODIFIED Requirements

### Requirement: A peer reaches workspaces through one grant
A peer or command that declares `HookWorkspace` SHALL be granted `workspace(name=None, *, create=True)`, a coroutine. Called with no name, it SHALL return the caller's own workspace, which can read and write. Called with another peer's name, it SHALL return that peer's workspace as a view that can only read. Calling it from a peer for its own name MUST return its own writable workspace. Calling it when the session has no provider MUST raise an error saying so. Naming no peer in the session and no workspace that exists MUST raise `KeyError` naming it. A command calling it with no name MUST raise an error, because a command owns no workspace. With `create=False`, a workspace that does not exist yet MUST raise `KeyError` naming it, and the call MUST create nothing, for the caller's own workspace as for anyone else's.

#### Scenario: Its own workspace
- **WHEN** peer `dev` calls `workspace()` and then `write("a.txt", "hi")`
- **THEN** `a.txt` holds `hi` in `dev`'s workspace

#### Scenario: Another peer's workspace is read-only
- **WHEN** peer `reviewer` calls `workspace("dev")`
- **THEN** it can `ls`, `read`, `glob`, `grep`, `diff` and `log` dev's workspace, and the object it got has no `write`, `edit`, `delete` or `commit`

#### Scenario: No provider
- **WHEN** a peer declaring `HookWorkspace` calls `workspace()` in a session given no `workspaces`
- **THEN** the call raises an error saying the session has no workspace provider

#### Scenario: An unknown name
- **WHEN** a peer calls `workspace("nobody")` and no peer or workspace is named `nobody`
- **THEN** the call raises `KeyError` naming `nobody`

#### Scenario: Asking without creating
- **WHEN** peer `lead` calls `workspace("dev", create=False)` and `dev`, a peer in the chat, has never had a workspace
- **THEN** the call raises `KeyError` naming `dev`, and no worktree or branch is created for it

#### Scenario: Asking for one that exists
- **WHEN** `dev` has a workspace and `lead` calls `workspace("dev", create=False)`
- **THEN** it gets dev's workspace as a read-only view
