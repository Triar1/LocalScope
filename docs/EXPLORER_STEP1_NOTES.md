# LocalScope Explorer — step 1 of 5

## Changes
- Compact tab-style controls for Folders / Categories / File types and Bubbles / Bars.
- Original `layout_bubbles`, `Bubble`, zoom, pan and folder navigation retained.
- Categories and file types can be opened to a second-level bubble or bar view; Back returns to the category/type overview.
- Second-level lists show at most 45 bubbles or 150 bars; the inspector shows 250 entries. No file changes.
- All category/type attribution remains heuristic; no claims that duplicates are safe to delete.

## Install and test (PowerShell)
```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m localscope
```

## Limitations
- The second-level file type view displays the largest matching files rather than a folder-grouped hierarchy.
- Scanning a full drive can be slow; perspective analysis reuses scan data.
- GUI interaction should be validated on Windows with PySide6; automated tests only cover existing test suite.
