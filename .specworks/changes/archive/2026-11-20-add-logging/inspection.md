# Inspection: add-logging

## Findings

<!-- One finding per note the reviewer left, written with
`specworks finding add <type> "<text>" --proposal "<proposal>" --artifact inspection`.
`- [ ] I<n>` while open, `- [x] I<n>` once an inspection confirmed it. -->

- [ ] I1 **quality** Why do we need the global variables _open and _failed (src/chatinho/logs.py:100-116)? _open is needed: logging is per process, it keeps a second run() from attaching a second handler (no doubled records) and lets close_log() stop the listener and restore the logger. _failed is not: it latches a failed open for the whole process, so after the directory is fixed a later run() in the same process stays silent and off until exit
  - **Proposal**: back to code: drop _failed so each run() retries opening the log (one stderr line per failed run), keep _open; add a test that a run after a failed one opens the file once the directory is fixed

## Summary

<!-- The blocks walked out of the total, and the notes written. -->
