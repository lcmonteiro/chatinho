# Spec Delta

## Purpose

Defines what can be done in a workspace: the operations a reader and its owner have, how they are declared so every consumer discovers them, and how a project adds its own without touching the library.

## ADDED Requirements

### Requirement: Operations are declared, and discovered from the declarations
Every operation of a workspace SHALL be a method declared as an operation, with a description and whether it writes. `operations_of` SHALL return the operations of a view or workspace class (inherited ones included) in definition order, each with its name, description, whether it writes, and its parameters. Every consumer of workspaces (the agent's tools, `/ws`) MUST take the operations from it, so an added operation reaches them all with no other change. A declared operation that is not a coroutine MUST be refused when its class is defined.

#### Scenario: Discovering the default operations
- **WHEN** code calls `operations_of` on the read-only view class
- **THEN** it gets `read`, `ls`, `grep`, `diff` and `log`, none of them writing

#### Scenario: A non-coroutine operation
- **WHEN** a class declares a plain `def` method as an operation
- **THEN** defining the class raises `TypeError` naming the method

### Requirement: Extending by subclassing
A project SHALL add operations by subclassing the read-only view, the writable workspace, or both, and SHALL give the provider the classes to use. The provider MUST refuse, when it is created, a workspace class that is not a subclass of the view class, and a view class that has a writing operation, naming the class and the reason.

#### Scenario: A read operation added
- **WHEN** a project subclasses the view with an operation `symbols`, subclasses the workspace from both, and gives both to the provider
- **THEN** both the owner and other peers can call `symbols`, and the agent gets a tool for it

#### Scenario: A workspace class that does not extend the view
- **WHEN** the provider is given a view with `symbols` and a workspace class that does not subclass that view
- **THEN** creating the provider raises an error saying the workspace must subclass the view

#### Scenario: A writing operation on a view
- **WHEN** the provider is given a view class that declares a writing operation
- **THEN** creating the provider raises an error naming that operation

### Requirement: The read operations
A view, and so also a workspace, SHALL offer:
- `read(path)`: the file's text as it is now in the working tree;
- `ls(path=".")`: the entries of a directory, directories marked with a trailing `/`, and the repository's own metadata left out;
- `diff()`: the working tree, uncommitted changes included, against the point where the workspace's branch left the base;
- `log()`: the commits on the workspace's branch that are not on the base, newest first, each with its short id and subject.

#### Scenario: Reading uncommitted work
- **WHEN** `dev` writes `a.txt` without committing and `reviewer` reads it through dev's view
- **THEN** `reviewer` gets the text `dev` wrote

#### Scenario: The diff shows all of the work
- **WHEN** `dev` commits a change to `a.txt`, then changes `b.txt` without committing
- **THEN** `diff()` shows both files

### Requirement: Paths stay inside the workspace
Every operation that takes a path SHALL take it relative to the workspace's root. A path that resolves outside the root, through `..`, an absolute path or a symbolic link, MUST be refused with `ValueError` before anything is read or written. Reading a file that does not exist MUST raise `FileNotFoundError` naming the path.

#### Scenario: Escaping with ..
- **WHEN** an operation is called with `../../etc/passwd`
- **THEN** it raises `ValueError` and nothing is read

#### Scenario: Escaping through a link
- **WHEN** the workspace holds a symbolic link pointing outside it and an operation reads through it
- **THEN** it raises `ValueError`

### Requirement: grep searches the working tree, across lines if asked
`grep(pattern, path=".", glob=None, multiline=False, limit=100)` SHALL search, with a regular expression, the files under `path` that the repository tracks or would track (new files included, ignored files left out), optionally only those matching `glob`. With `multiline=False`, `^` and `$` MUST match at each line and `.` MUST NOT match a newline. With `multiline=True`, `.` MUST also match a newline, so one match may span lines. Each match SHALL carry the file's path, the line where it starts, the line where it ends, and the matched text. The matched text MUST be cut at a fixed length, saying so. At most `limit` matches SHALL be returned, and the result MUST say when more were found. A file that is not UTF-8 text MUST be skipped. A pattern that is not a valid regular expression MUST raise `ValueError` carrying the reason.

#### Scenario: A match on one line
- **WHEN** a file has `def answer(self):` on line 3 and grep looks for `def answer`
- **THEN** it returns one match with start and end line 3

#### Scenario: A match across lines
- **WHEN** a file has `def answer(` on line 3 and `return Reply` on line 5, and grep looks for `def answer\(.*?return` with `multiline=True`
- **THEN** it returns one match from line 3 to line 5 whose text holds both lines

#### Scenario: The same pattern without multiline
- **WHEN** grep looks for `def answer\(.*?return` with `multiline=False` in that file
- **THEN** it returns no match

#### Scenario: Ignored files are not searched
- **WHEN** a file listed in `.gitignore` contains the pattern
- **THEN** grep does not return it

#### Scenario: More matches than the limit
- **WHEN** the pattern matches 150 times and `limit` is 100
- **THEN** grep returns 100 matches and says the result was cut

#### Scenario: A bad pattern
- **WHEN** grep is given `(unclosed`
- **THEN** it raises `ValueError` saying why the pattern is invalid

### Requirement: The write operations
A workspace SHALL offer, besides the read operations:
- `write(path, text)`: write the file, creating the directories it needs;
- `delete(path)`: remove the file;
- `commit(message)`: commit every change in the working tree on the workspace's branch and return the commit's id.

A commit with nothing to commit MUST raise an error saying so rather than creating an empty commit. None of these operations SHALL touch the base branch or another workspace.

#### Scenario: Write, commit, log
- **WHEN** `dev` writes `a.txt`, commits "add a" and calls `log()`
- **THEN** the log's newest entry is "add a" with the id `commit` returned

#### Scenario: Nothing to commit
- **WHEN** `dev` calls `commit("x")` with no changes
- **THEN** it raises an error saying there is nothing to commit, and no commit is made

#### Scenario: The base is untouched
- **WHEN** `dev` writes and commits in its workspace
- **THEN** the base branch has no new commit
