# LocalScope v0.8.1 — Category Explorer

Windows-first, fully offline, read-only storage visualization.

## New in v0.8.1

- **Category Explorer** button alongside **Storage Insights**.
- Folder-purpose categories: Games, Development, Media, Applications, Documents, Archives, Other.
- Explicit rules, confidence and explanation for each attribution.
- Sort by size, filter by category, double-click a row to navigate to the bubble map.
- Totals partition scanned files rather than double-counting nested folder sizes.
- Uses the already scanned tree; no additional disk scan, AI, or deletion.

**Limitations:** Purpose labels are heuristics, not a list of installed applications. Game recognition is currently limited to a few recognizable folder/runtime markers (including Factorio and Steam libraries). Mixed directories may be listed as Other. A folder may be split into a direct-files attribution and separately attributed subfolders. Scan errors and filesystem allocation differences can affect totals.

## Install / run

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m localscope
```

Scan a folder, open **Category Explorer**, then filter by **Games** to inspect Factorio if present.

---

# LocalScope v0.5 — Python Environment Intelligence

Windows-first, offline, read-only disk explorer with interactive bubbles and developer audit.

## New in v0.5

- **Python environment map** button links scanned `.venv` folders to detected projects.
- Reads `pyvenv.cfg` (`home`, `executable`, `version`) without executing any binary.
- Shows inferred base interpreter path and package metadata counts.
- Separates likely embedded executables from other executable candidates.
- Clearly labels unverified links; no automatic cleanup or claims of safe deletion.

## Install (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m localscope
```

Scan a folder, then select **Python environment map**. Double-click any result to navigate to its folder.

## Limitations

- Scope is the selected scan root, not all drives.
- Interpreter paths are references and are not verified outside the scan.
- An environment can be healthy even when it has the same packages as another.
- Package counts are estimated from scanned metadata directories.
- Scan access errors can hide results.
- No duplicate-content hashing, dependency comparison, or space-recovery estimates yet.

MIT license.


## v0.5.1 — Audit Reliability
- Classifies real installed software paths independently of scan root (Anki, MAMP, Program Files).
- Keeps pytest fixture roots usable for unit tests; separates temporary test environments from active environments.
- Groups explicit `vN` project versions across folders, without assuming their contents are identical.
- Shows explainable confidence labels (High/Medium/Low), not invented probability percentages.
- Improves audit column widths and full-path tooltips.
- Remains offline and read-only. No files are removed.

To upgrade: overwrite source files but **retain your existing `.venv`**, then run `python -m pip install -e ".[dev]"`, `python -m pytest -q`, and `python -m localscope`.


## v0.5.2 Windows test fix

Fixes false temporary classification of synthetic environments when the scan root itself is a pytest temporary fixture. Real full-PC scans continue to separate temporary environments.

## v0.6 — Redundancy Intelligence

New **Redundancy report** button: identifies versioned project families and compares
installed package metadata across linked virtual environments. Findings are
informational, not cleanup instructions. Package similarity is not evidence
that two virtual environments are interchangeable.

The graphical report intentionally **does not hash files**: reading large
files in the UI thread would freeze the application. To explicitly check exact
file duplicates in a selected folder, run:

```powershell
python -m localscope.duplicates_cli "C:\Users\YourName\Downloads"
```

This optional read-only command hashes only files sharing a scanned size,
uses SHA-256, skips symlinks and changed/inaccessible files, and prints
paths of exact-byte matches. By default it does not hash files larger than
2 GiB (adjust using `--max-file-gib`). Large scans may take time.
It never deletes, modifies, or moves files. Identical bytes are **not** a
recommendation to delete either file. Files that changed during scanning,
access-denied paths, hard links, and file-system deduplication can affect
interpretation. Hashing does not establish whether a copy is needed by an
application or whether its deletion would reclaim physical disk space.

### Known limitations

- Classification remains heuristic; project families use explicit `vX.Y` names.
- Environment comparison uses package metadata directory names, not a
  dependency solver or package-content comparison.
- Duplicate hashing is opt-in via CLI; the UI is metadata-only.
- No cleanup or uninstall functionality exists.
- The GUI has not been manually validated on Windows for this release.

## v0.7 — Storage Optimization Center

New **Optimization Center** button (available after scanning a folder). It opens a separate read-only duplicate inspector:

- Run exact SHA-256 comparison in a background Qt thread with progress and cancellation.
- Filter groups by extra identical bytes and inspect all full file paths.
- Select a copy and reveal it in Windows Explorer.
- No deletion, moving, renaming, or file modification.

The scanned directory tree is reused, but files are read again when hashing. Files that changed, are inaccessible, or are symbolic links may be skipped. Per-file hashing is limited to 2 GiB. The computed 'extra identical bytes' is **not** confirmed reclaimable disk space (hardlinks, cloud placeholders, and user workflows can change the interpretation). The previous CLI remains available.

Run: `python -m pytest -q` and `python -m localscope`.

## v0.7.1 — Large-disk scan improvements

- Two-stage exact duplicate search: compare sizes, then sample three 64 KiB regions for files above 2 MiB, then verify matching candidates with full SHA-256. Samples alone never establish duplicates.
- Progress now shows the current phase, number of candidate files, elapsed time, file path, and bytes read.
- Cancel is checked between 1 MiB read blocks; a blocked operating-system file read cannot be forcibly interrupted.
- Windows cloud-only / recall-on-access files are skipped by default without opening them, to reduce unwanted OneDrive hydration. Some cloud states may still be unrecognized.
- A completed scan reports exact duplicate groups and potential redundant bytes; it does not delete anything.
- Large scans can still be slow on HDDs, network drives, or very large groups of equal-size files.

Run `python -m pytest -q` and `python -m localscope` after replacing project files, keeping `.venv`.

## v0.7.2 — progress visibility fix

- Indexing the in-memory scan tree now emits an immediate status and periodic progress even before file hashing starts.
- The progress bar stays indeterminate while the indexing total is unknown; phase counters and paths are displayed.
- Qt status delivery is explicitly queued onto the GUI thread via Qt slots.
- Added regression tests for early progress and cancellation during indexing.
- The duplicate scan remains read-only; OneDrive offline placeholders are skipped by default.

On very large drives, the initial tree-indexing phase can take time. An indeterminate bar during indexing is expected, but the node count should now update.


## v0.7.3 diagnostic update

The CLI now uses the same optimized duplicate finder as the GUI. It prints progress
every ~2 seconds between disk operations and logs reads taking 2 seconds or more.
The GUI shows a heartbeat warning when no progress event has arrived for 5 seconds.
A single blocked OS file read cannot be forcibly interrupted safely in Python;
closing or cancelling may wait until that read returns. No files are deleted.

Run: `python -m localscope.duplicates_cli "C:\Users\YOURNAME\Downloads"`

## v0.7.4 — Optimization Center scope selection

The Optimization Center now shows its actual analysis scope and offers **Choose folder…**.
Selecting a subfolder starts a separate, cancellable, read-only folder scan in the worker thread before duplicate analysis. The original storage visualization is unaffected. For large drives, first test `Downloads` to compare with the CLI. This change does not guarantee a fix for every possible Qt event-loop issue.

## v0.8 — Storage Insights

After scanning a folder or drive, choose **Storage Insights** to see an offline,
read-only breakdown by file extension category and a ranking of the 100 largest
folders. Double-click a folder to return to the interactive bubble explorer.
The results are computed from the existing in-memory scan (no extra disk scan).

Categories are approximate file-type groups based on extensions, **not** a
reliable identification of games, installed software, or personal projects.
The Optimization Center GUI is hidden while its asynchronous scanning issue
is investigated; the duplicate-finder CLI is still available.
No files are modified, deleted, or uploaded.

## v0.8.2 — Category Explorer improvements

- Loose files in a folder are categorized separately by extension instead of being grouped into a single `Other` entry.
- Adds an `Installers` purpose (downloaded installers are not treated as installed applications).
- Adds a **Category bubbles** tab. Bubble area corresponds to attributed bytes; clicking a bubble filters the folder table.
- Direct-file category rows navigate to their containing folder in the original bubble map.
- Heuristic classification remains offline, in-memory, read-only and does not inspect installed apps.

## v0.9 — Project Relationship Map

After scanning a folder, select **Project Relationship Map** to inspect an offline graph
of detected projects, virtual environments and base Python references.
The graph uses `pyvenv.cfg` and project markers; it does not run Python executables.
Mouse wheel zooms; drag pans; click a node for details, double-click to explore
its directory when present in the scan. The table below also supports double-click navigation.

Base interpreter paths are **references, not verified installations**. Shared interpreter
references do not mean environments are redundant. This feature never modifies scanned files.

Run `python -m pytest -q` before starting the app with `python -m localscope`.

## v0.9.1 — game discovery and project-family map

- Category Explorer now descends into application-installation containers instead of
  assigning all of `Program Files` to Applications. Steam `steamapps/common`,
  Epic Games, GOG Games and XboxGames folder layouts are recognized by path.
  Some executable/runtime names are used as additional evidence. This is a
  **heuristic**, not an installed-games inventory: protected Xbox/MSIX content,
  nonstandard libraries and access-denied paths can remain unclassified.
- `Games` is a subtype of applications conceptually, but stays a **separate,
  non-overlapping bucket** in storage totals. No double-counting.
- Relationship Map groups versioned project names into families by default.
  Use **Show individual versions** to expand them. Project → environment →
  interpreter links appear in three columns. Node height represents number of
  connections, **not storage size**; family size is shown in its details.
- Entirely offline and read-only with respect to the scanned files. Scanning
  cannot see inaccessible folders, and confidence labels are not guarantees.

### Windows upgrade

1. Back up your existing project directory. Extract this archive into a new
   directory; **do not copy an old `.venv`**.
2. In PowerShell, from the extracted directory:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   .\.venv\Scripts\python.exe -m pytest -q
   .\.venv\Scripts\python.exe -m localscope
   ```

3. Scan `C:\` (or the drive containing your game libraries). Verify game
   detection and open Project Relationship Map; toggle family grouping.

If you prefer to reuse your current environment, install the extracted project
with `python -m pip install -e ".[dev]"` in the activated environment.

## v0.9.2 — Explain Other

After scanning a folder or drive, click **Explain Other**. This opens an
in-memory, read-only breakdown of items that Category Explorer classifies as
**Other**. The first tab lists the largest unknown locations and individual
unclassified direct files. The second tab summarizes unknown extensions by
bytes and file counts. Double-click a location to explore it in the storage
bubble map. The report is based on the existing scan, does not access the disk
again, and does not change or delete files.

**Important:** Other means *unclassified*, not *unnecessary*. The report does
not automatically reclassify unknown data. The number can remain high until
further evidence-based detectors are added. Files inaccessible during the
original scan are not included in the measured breakdown.


## v0.9.3 — Stability and GOG game recognition

- Recognizes game folders under `GOG Galaxy\Games` rather than attributing the whole GOG installation to Applications.
- **Explain Other** is now **Storage Intelligence Explorer**: worker thread, responsive window, cancellable analysis, top 50 locations and extensions, plus top 50 game directories.
- Top 50 is a *display limit*, not a scan limit; all unclassified files contribute to totals.
- The analysis reuses the in-memory scan and does not access or change disk files.
- A cancellation during the initial purpose-classification pass may only take effect once that pass finishes.
- Read-only classification is heuristic; store/library folders may contain non-game data.

### Windows installation

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m localscope
```

## v0.9.4 — Context-aware storage categories

Category Explorer now includes **System**, with path-based attribution of Windows-managed
files (`pagefile.sys`, `hiberfil.sys`), Windows directory contents, installed games,
Minecraft data, NVIDIA shader caches, Chrome/Outlook/Dassault application data,
and local Ollama models. Folder ownership takes precedence over extension, and
category totals remain mutually exclusive. This is a heuristic *read-only*
classification, not a deletion recommendation. `Other` remains for unresolved files.

### Windows installation

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m localscope
```

Use **Category Explorer** after scanning `C:\`. Compare the category totals to
v0.9.3. Files in protected or inaccessible directories cannot be classified.
No files are modified, moved, or deleted.
