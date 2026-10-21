# System Health update (based on v1.0.3)

- New **Windows storage overview** tab reports observed Windows, ProgramData, Recycle Bin, System Volume Information and Windows-managed root files.
- Shows scan-derived sizes and safety guidance, without touching disk, rescanning, or estimating recoverable space.
- Existing Windows files & actions and Redundancy insights remain available.
- Original Explorer packed bubble map, navigation, and Developer Hub are unchanged.
- 63 automated tests pass (`PYTHONPATH=src python -m pytest -q` in the build environment).
- Verify the GUI on Windows after installation; it was not visually tested here.
