# LocalScope v1.0.5 — Visual polish & loading feedback

- System Health: clearer hierarchy, subtle teal/blue accents, highlighted tabs, alternating table rows, and compact icon cues.
- Main navigation: restrained icons for System Health and Developer Hub.
- First Categories / File types classification: status bar message before in-memory computation, then cached-ready confirmation.
- System Health opening: status bar message before the dialog builds its metadata analysis.
- No changes to the bubble packing, scanning engine, file contents, or deletion behavior.
- Note: synchronous analysis may still temporarily block the UI; these messages are an interim UX improvement, not a background-worker implementation. Verify visibility on Windows.
- Tests: 63 passed in the build environment.
