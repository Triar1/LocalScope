# LocalScope — Explorer UX patch (Step 2)

- Moved the existing **Back** button directly below **Reset zoom**, inside the Storage Explorer panel.
- Back is disabled at the root, enabled when a folder or category drill-down is active.
- Original packed bubble renderer, zoom/pan, and read-only scanning are unchanged.
- Launch: `python -m localscope`
- Test: `python -m pytest -q`
