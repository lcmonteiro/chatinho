# Inspection: add-logging

## Findings

<!-- One finding per note the reviewer left, written with
`specworks finding add <type> "<text>" --proposal "<proposal>" --artifact inspection`.
`- [ ] I<n>` while open, `- [x] I<n>` once an inspection confirmed it. -->

- [ ] I1 **quality** Why do we need the global variables _open and _failed (src/chatinho/logs.py:100-116)? _open is needed: logging is per process, it keeps a second run() from attaching a second handler (no doubled records) and lets close_log() stop the listener and restore the logger. _failed is not: it latches a failed open for the whole process, so after the directory is fixed a later run() in the same process stays silent and off until exit
  - **Proposal**: back to code: drop _failed so each run() retries opening the log (one stderr line per failed run), keep _open; add a test that a run after a failed one opens the file once the directory is fixed
- [ ] I2 **quality** logging.FileHandler has no way to set file permissions, so open_log needs os interfaces: today it opens the path twice, os.open(path, O_CREAT|O_APPEND, 0o600) then FileHandler (src/chatinho/logs.py:111-112), and neither refuses a symbolic link, so a link planted at the predictable chatinho.<date>.log in a shared directory (the README suggests /tmp) gets the log appended to its target. Is it platform independent? It runs everywhere, but owner-only (0600/0700) is enforced only on POSIX: on Windows os.open keeps only the read-only bit and mkdir ignores its mode, and the tests are skipped there
  - **Proposal**: back to code: open the file once through a FileHandler subclass whose _open passes opener=lambda p, f: os.open(p, f | getattr(os, 'O_NOFOLLOW', 0), 0o600), with a test that a symbolic link at the log path is refused (one stderr line, no write to its target); say in CLAUDE.md that owner-only is enforced on POSIX only

## Summary

<!-- The blocks walked out of the total, and the notes written. -->
