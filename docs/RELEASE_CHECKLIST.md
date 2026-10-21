# LocalScope — Windows release checklist

## Automated
- [ ] Run `python -m pytest -q` in a clean environment.
- [ ] Run `python -m localscope` from the extracted package.

## Explorer
- [ ] Scan a small test folder and then a representative large folder.
- [ ] Check original packed Bubble Map, bubble sizes, zoom, pan, Reset zoom and Back.
- [ ] Verify Folders, Categories and File types in both Bubbles and Bars.
- [ ] Drill down into Games and a file type; confirm no double-counted sizes.
- [ ] Check first-open delays and status text on a large scan.

## System Health
- [ ] Open each of Windows storage overview, Windows files actions and Redundancy insights.
- [ ] Select pagefile.sys / hiberfil.sys if detected and read the guidance.
- [ ] Verify no automatic cleanup, deletion or Windows settings changes.

## Developer Hub
- [ ] Open after a scan and confirm developer audit appears.
- [ ] Open Python environment map and project relationship graph from the Hub.
- [ ] Check links between detected projects, version families and environments.
- [ ] Verify large/empty scan scopes do not crash the Hub.

## Packaging and publication
- [ ] Redact private paths/usernames in screenshots.
- [ ] Verify README, license, version number, and clean-install instructions.
- [ ] Do not advertise a standalone `.exe` unless one has been built and tested.
- [ ] Tag the stable release only after Windows smoke tests pass.
