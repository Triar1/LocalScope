# LocalScope — Storage, visualized

**Windows-first · Offline · Read-only · Open source (MIT)**

LocalScope explores a selected drive or folder without uploading data or deleting files. Its interactive, size-proportional **Bubble Map** makes storage easier to understand.

## Features

- **Explorer:** Folders, Categories and File types, each with Bubble Map or Bars; drill into results and inspect files.
- **System Health:** review Windows storage areas, system files and redundancy insights, with explanations and safety guidance. **No automatic cleanup.**
- **Developer Hub:** inspect detected development projects and environments; project relationship tools use scanned metadata.
- **Local-first:** scans the chosen scope and keeps analysis on your computer.

## Quick start — Windows PowerShell

Requires **Python 3.10+** and Windows 10/11. Extract this archive, then open PowerShell in the folder containing `pyproject.toml`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m localscope
```

Using `.venv\Scripts\python.exe` directly avoids PowerShell activation-policy issues. Dependencies are installed through pip, so **installation** may require internet; **scanning and analysis** do not.

## Using LocalScope

1. Select **Scan folder / drive** and choose a location.
2. In Explorer, switch between **Folders**, **Categories** and **File types**; choose **Bubbles** or **Bars**.
3. Click to inspect and navigate into results; use **Back** to return and **Reset zoom** to recenter the map.
4. Review **System Health** for explanations of system storage.
5. Open **Developer Hub** to examine development-related data detected in the scan.

## Performance and limitations

- On very large scans (e.g. ~1 million files), the first opening of **System Health**, **Categories** or **File types** may take several seconds. A status message appears, but some work is still synchronous and the interface may pause briefly.
- File classification and project relationships are **heuristic**; verify findings before acting manually.
- Access-denied files and filesystem metadata can make reported totals incomplete; scanned size is **not** guaranteed reclaimable space.
- Windows component-store hard links can distort naive size totals; do not manually delete WinSxS.
- Redundancy insights based on metadata do **not** prove two files have identical content.
- LocalScope never performs cleanup or changes Windows settings.

## Quality and release status

This archive is a **release candidate**, not a Windows-certified binary. The Python test suite passes in the packaging environment; perform the Windows smoke-test checklist in [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) before tagging a stable release.

## Screenshots

Add actual screenshots from your Windows installation to `docs/screenshots/` before publishing the GitHub release. Suggested views: Explorer Bubble Map, Categories drill-down, System Health and Developer Hub. Do not publish screenshots showing private paths or usernames without redaction.

## License

MIT — see [LICENSE](LICENSE).
