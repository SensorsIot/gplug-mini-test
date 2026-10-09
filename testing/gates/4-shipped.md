# Gate: Shipped — closes the release

Read `_common.md` first.

## Requirements

| # | Must be true | Where to look | Evidence |
|---|---|---|---|
| 1 | A release `vX.Y.Z` exists from a tagged commit, built in `espressif/idf:v6.0.2` | GitHub release + its `build.yml` run | Run log shows the container tag and `idf.py --version` |
| 2 | Release carries `gplug-mini.bin` (FSD C-BLD-03) | release assets | `gh release view vX.Y.Z` |
| 3 | The `verify` job of that run is green: the journey ran on the released bytes | that run | `gh run view <id>` shows verify success before release |
| 4 | The release JSON is readable without credentials (FSD C-BLD-04) | `https://api.github.com/repos/SensorsIot/gplug-mini-test/releases/latest` | unauthenticated `curl` returns the new tag |

## Traps

- A release created by hand (not by the workflow) skips verify — check the release was created by the run whose verify job passed.
