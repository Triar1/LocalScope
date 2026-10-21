# LocalScope v1.0 — first UX integration

This is an incremental v1.0 built from the provided v0.9.4 source, not a full rewrite.

## Included
- Primary **Overview** keeps the existing interactive Bubble Map, zoom, file inspector and back navigation.
- Top navigation: Overview, Storage Explorer, System Health, Developer Hub, Insights.
- System Health explains detected `pagefile.sys`, `hiberfil.sys`, `swapfile.sys`, and `memory.dmp` using **already-scanned metadata**. No cleanup or deletion.
- Existing Developer Audit, Python Environment Map, Project Relationship Map, Redundancy, category breakdown and other inspector remain in the application. Experimental optimization GUI stays hidden.
- 2 additional unit tests for System Health.

## Windows installation (PowerShell)
```powershell
cd "PATH_TO_EXTRACTED_FOLDER"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
python -m localscope.gui
```
If PowerShell blocks activation, run `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` and then `.\.venv\Scripts\python.exe -m localscope.gui`.

## Known limitations / next iteration
- Navigation opens existing dialogs instead of embedding every view into one page.
- Developer Hub currently opens the existing audit; related Python views remain in Advanced Tools.
- System Health recognizes selected system files; it does not calculate WinSxS cleanup potential or offer cleanup actions.
- No Windows GUI smoke test was performed in this Linux environment. Run the app locally and report any UI issues.
- Existing test suite plus new tests: 59 passing in the build environment.

## v1.0.1 — Explorer and System Health

Run the application with `python -m localscope` (not `python -m localscope.gui`).

- Explorer: **Folders**, **Categories**, and **File types**, each available as **Bubbles** or **Bars**. Switching perspectives uses the completed scan in memory; it does not rescan the drive.
- Clicking a category or file type populates the File Inspector with matching items (top 250 displayed). Double-click a folder to enter its physical location.
- System Health includes explanations of Windows memory files, a component-store guide, trade-offs, and read-only redundancy insights.
- Developer Hub retains the existing developer audit, Python environment map, and relationship graph.
- No deletion, command execution, or Windows configuration changes are performed.

The first switch to Categories or File types may take time on a million-file scan because it builds an in-memory classification. Later switches use cached results. This should not increase the *initial disk scan time*; measure the first classification separately.
