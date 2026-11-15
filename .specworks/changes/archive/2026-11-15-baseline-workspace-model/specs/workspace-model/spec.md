# Spec Delta: workspace-model

## Purpose

Defines what a workspace is, whoever provides it: the operations a reader and an owner have over one git worktree, how they are declared so every consumer discovers them, and the one door through which they reach a path. It has no living spec yet; this records the behaviour it already has.

## ADDED Requirements

### Requirement: REQ-WSM-001 Operations are declared and discovered

Every operation of a workspace SHALL be a coroutine method declared with `@operation(description, writes=False)`. `operations_of` SHALL return the operations of a view or workspace class, or of an instance of one, inherited ones first and in definition order, each with its name, description, whether it writes, and its parameters. A read-only view has `ls`, `read`, `glob`, `grep`, `diff` and `log`; a workspace adds the writing `write`, `edit`, `delete` and `commit`. A declared operation that is not a coroutine MUST raise `TypeError` when its class is defined.

#### Scenario: AC-WSM-001.1 The view's operations

- **WHEN** `operations_of` is called on the read-only view class
- **THEN** it gives `ls`, `read`, `glob`, `grep`, `diff` and `log`, none of them writing

#### Scenario: AC-WSM-001.2 The workspace's operations

- **WHEN** `operations_of` is called on the workspace class
- **THEN** it gives the view's six, then `write`, `edit`, `delete` and `commit`, and only those four write

#### Scenario: AC-WSM-001.3 Description and parameters

- **WHEN** the `grep` operation is read
- **THEN** it carries its description and the parameters `pattern`, `path`, `glob`, `multiline` and `limit`

#### Scenario: AC-WSM-001.4 Of an instance

- **WHEN** `operations_of` is called on an instance of a view
- **THEN** it gives the same as for its class

#### Scenario: AC-WSM-001.5 A plain def

- **WHEN** a class declares a method that is not a coroutine as an operation
- **THEN** defining the class raises `TypeError` naming the method

#### Scenario: AC-WSM-001.6 An added operation

- **WHEN** a subclass of the view declares an operation `symbols`
- **THEN** `operations_of` the subclass lists `symbols` after the inherited ones

### Requirement: REQ-WSM-002 Paths stay inside the workspace

Every operation that takes a path SHALL take it relative to the workspace's root. An absolute path, a path that resolves outside the root through `..` or a symbolic link, and git's own metadata MUST be refused with `ValueError` before anything is read or written. Reading a file that does not exist MUST raise `FileNotFoundError` naming the path.

#### Scenario: AC-WSM-002.1 Escaping with ..

- **WHEN** `read` is called with `../../etc/passwd`
- **THEN** it raises `ValueError` saying the path is outside

#### Scenario: AC-WSM-002.2 An absolute path

- **WHEN** `read` is called with `/etc/passwd`
- **THEN** it raises `ValueError` saying the path is absolute

#### Scenario: AC-WSM-002.3 Escaping through a link

- **GIVEN** a symbolic link in the workspace pointing outside it
- **WHEN** `read` is called on the link
- **THEN** it raises `ValueError`

#### Scenario: AC-WSM-002.4 Git's metadata

- **WHEN** `write` is called on `.git`
- **THEN** it raises `ValueError` naming the metadata

#### Scenario: AC-WSM-002.5 A missing file

- **WHEN** `read` is called on a file that does not exist
- **THEN** it raises `FileNotFoundError` naming the path

### Requirement: REQ-WSM-003 Listing a directory

`ls(path=".")` SHALL return the entries of a directory, directories marked with a trailing `/`, leaving git's own metadata out.

#### Scenario: AC-WSM-003.1 Directories marked, git hidden

- **GIVEN** a workspace with two files at the root and a file under `src`
- **WHEN** `ls()` and `ls("src")` are called
- **THEN** the first lists the two files and `src/`, with no `.git`, and the second lists the file

### Requirement: REQ-WSM-004 Reading a window of a file

`read(path, offset=0, limit=2000)` SHALL return at most `limit` lines of the file as it is now in the working tree, starting at line `offset` (0-indexed), with the 1-indexed number of the first line returned and whether lines remain after the window. A negative `offset` MUST read from the first line, and a `limit` of zero or less MUST return no lines. A reader MUST see the owner's uncommitted work.

#### Scenario: AC-WSM-004.1 A window

- **GIVEN** a file of 10 lines
- **WHEN** `read` is called with `offset=4` and `limit=3`
- **THEN** it returns lines 5 to 7, says the window starts at line 5, and says lines remain

#### Scenario: AC-WSM-004.2 Past the end

- **GIVEN** a file of 10 lines
- **WHEN** `read` is called with `offset=8` and `limit=5`
- **THEN** it returns lines 9 and 10 and says nothing remains

#### Scenario: AC-WSM-004.3 Degenerate windows

- **WHEN** `read` is called with a negative `offset`, and with `limit=0`
- **THEN** the first reads from the first line and the second returns no lines

#### Scenario: AC-WSM-004.4 Uncommitted work through a view

- **WHEN** the owner writes a file without committing and another peer reads it through a view
- **THEN** the reader gets the text the owner wrote

### Requirement: REQ-WSM-005 Finding files

`glob(pattern, path=".")` SHALL return the files under `path`, never directories, whose path relative to `path` matches `pattern`, with `*`, `**` and `?`. A pattern without `/` MUST match the file's name at any depth. Files the repository ignores MUST be left out.

#### Scenario: AC-WSM-005.1 A name at any depth

- **GIVEN** `a.py`, `src/app/main.py` and `src/app/notes.md`
- **WHEN** `glob("*.py")`, `glob("src/**/*.py")` and `glob("*.py", path="src")` are called
- **THEN** the first returns both Python files, and the other two only `src/app/main.py`

#### Scenario: AC-WSM-005.2 Ignored files

- **GIVEN** files the repository's `.gitignore` covers and one it does not
- **WHEN** `glob("*")` is called
- **THEN** the ignored files are not returned

### Requirement: REQ-WSM-006 The diff and the log

`diff()` SHALL return the working tree, uncommitted changes and new files included, against the point where the workspace's branch left the base, without changing the owner's staging area. `log()` SHALL return the commits on the workspace's branch that are not on the base, newest first, each with its short id and subject.

#### Scenario: AC-WSM-006.1 All of the work

- **WHEN** the owner commits a change to one file, then writes another without committing, and `diff()` is called
- **THEN** the diff shows both files

#### Scenario: AC-WSM-006.2 The index is left alone

- **WHEN** `diff()` is called with a new uncommitted file
- **THEN** nothing is staged in the owner's index

#### Scenario: AC-WSM-006.3 Newest first

- **WHEN** the owner commits "one", then "two", and `log()` is called
- **THEN** it lists "two", then "one", each after its short id

### Requirement: REQ-WSM-007 Searching the working tree

`grep(pattern, path=".", glob=None, multiline=False, limit=100)` SHALL search with a regular expression the files under `path` that the repository tracks or would track, optionally only those matching `glob`. Without `multiline`, `.` MUST NOT match a newline; with it, one match may span lines. Each match carries the file's path, the lines where it starts and ends, and the text of the lines it spans, cut at a fixed length saying so. At most `limit` matches are returned, and the result MUST say when more were found. A file that is not UTF-8 text MUST be skipped, and a pattern that is not a valid regular expression MUST raise `ValueError`.

#### Scenario: AC-WSM-007.1 A match on one line

- **GIVEN** a file with `def answer(self):` on line 3
- **WHEN** grep looks for `def answer`
- **THEN** it returns one match starting and ending on line 3, with that line as its text

#### Scenario: AC-WSM-007.2 A match across lines

- **GIVEN** a file with `def answer(` on line 3 and `return Reply` on line 5
- **WHEN** grep looks for `def answer\(.*?return` with `multiline=True`
- **THEN** it returns one match from line 3 to line 5 whose text holds both

#### Scenario: AC-WSM-007.3 The same pattern without multiline

- **WHEN** grep looks for that pattern with `multiline=False`
- **THEN** it returns no match

#### Scenario: AC-WSM-007.4 Ignored files

- **WHEN** an ignored file and a kept one both hold the pattern
- **THEN** only the kept file is returned

#### Scenario: AC-WSM-007.5 Filtered by glob

- **WHEN** grep is given `glob="*.py"` and a `.py` and a `.txt` file both hold the pattern
- **THEN** only the `.py` file is returned

#### Scenario: AC-WSM-007.6 More matches than the limit

- **WHEN** the pattern matches 150 times and `limit` is 100
- **THEN** grep returns 100 matches and says the result was cut

#### Scenario: AC-WSM-007.7 Exactly the limit

- **WHEN** the pattern matches 5 times and `limit` is 5
- **THEN** grep returns 5 matches and does not say the result was cut

#### Scenario: AC-WSM-007.8 A bad pattern

- **WHEN** grep is given `(unclosed`
- **THEN** it raises `ValueError` saying the pattern is invalid

#### Scenario: AC-WSM-007.9 A long match

- **WHEN** a match spans 2000 characters
- **THEN** its text is cut short and says so

#### Scenario: AC-WSM-007.10 A file that is not text

- **WHEN** a file that is not UTF-8 and a text file both hold the pattern
- **THEN** only the text file is returned

### Requirement: REQ-WSM-008 Writing, editing and deleting

A workspace SHALL offer `write(path, text)`, which writes the file and creates the directories it needs; `edit(path, old, new, replace_all=False)`, which replaces the exact text `old` with `new` and returns how many times; and `delete(path)`, which removes a file or a directory. An `edit` whose `old` does not occur, or occurs more than once without `replace_all`, MUST raise `ValueError` saying which and leave the file unchanged. Deleting what does not exist MUST raise `FileNotFoundError`.

#### Scenario: AC-WSM-008.1 Write creates folders

- **WHEN** `write("deep/er/a.txt", "hi")` is called
- **THEN** the file exists with that text

#### Scenario: AC-WSM-008.2 An exact edit

- **GIVEN** a file holding `x = 1` once
- **WHEN** `edit` replaces `x = 1` with `x = 2`
- **THEN** it returns 1 and the file holds `x = 2`

#### Scenario: AC-WSM-008.3 An ambiguous edit

- **GIVEN** a file holding `x = 1` twice
- **WHEN** `edit` replaces `x = 1` without `replace_all`, and then with it
- **THEN** the first raises `ValueError` saying the text is not unique and changes nothing, and the second returns 2

#### Scenario: AC-WSM-008.4 Text that is not there

- **WHEN** `edit` is given text the file does not hold
- **THEN** it raises `ValueError` saying it does not occur

#### Scenario: AC-WSM-008.5 Delete

- **WHEN** a file and a directory are deleted, and the file is deleted again
- **THEN** both are gone, and the second delete raises `FileNotFoundError`

### Requirement: REQ-WSM-009 Committing

`commit(message)` SHALL commit every change in the working tree on the workspace's branch, authored by the workspace's name, and return the commit's id. With nothing to commit it MUST raise `ValueError` saying so and make no commit. It MUST NOT touch the base branch.

#### Scenario: AC-WSM-009.1 Write, commit, log

- **WHEN** the owner writes a file, commits "add a" and calls `log()`
- **THEN** the newest entry is "add a" with the id `commit` returned

#### Scenario: AC-WSM-009.2 Authored by the peer

- **WHEN** the workspace named `dev` commits
- **THEN** the commit's author is `dev`

#### Scenario: AC-WSM-009.3 Nothing to commit

- **WHEN** `commit` is called with no changes
- **THEN** it raises `ValueError` saying there is nothing to commit, and the log stays empty

#### Scenario: AC-WSM-009.4 The base is untouched

- **WHEN** the owner writes and commits
- **THEN** the base branch points where it did

### Requirement: REQ-WSM-010 Writing operations run one at a time

Operations declared as writing SHALL run one at a time on a workspace, in the order they were called, and reading operations MUST NOT wait for each other.

#### Scenario: AC-WSM-010.1 Writes in call order

- **WHEN** two slow writing operations are called together
- **THEN** the second starts after the first ended

#### Scenario: AC-WSM-010.2 Reads together

- **WHEN** two slow reading operations are called together
- **THEN** both start before either ends

#### Scenario: AC-WSM-010.3 Two writes of one file

- **WHEN** two writes of the same file are called together
- **THEN** the file holds what the last call wrote
