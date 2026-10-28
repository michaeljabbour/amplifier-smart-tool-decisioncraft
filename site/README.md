# Website

The product page uses a versioned family theme. Content lives in `site/site.json`.
The theme's MIT notice stays in `site/theme/LICENSE` and is copied into the
generated assets. Independent-project attribution comes from the page config.

## Build and check

From the repository root, with Python 3.11 or later and either `uv` or Python's
`build` package available for wheel comparison:

```sh
python3 scripts/build-site.py
python3 scripts/check-site.py
python3 -m http.server 8000 --directory _site --bind 127.0.0.1
```

The wrapper rebuilds fictional examples without model calls, renders the theme,
copies every actual example canvas and existing film asset, and builds
`_site/downloads/decisioncraft-skill.zip`. It runs the native 17 isolated archive
checks, then checks local page references, exact source bytes of examples/media,
archive files and contents, and both MIT notices. The archive contains the full
native payload plus the product license.

`_site/site-release.json` records source paths and hashes. These checks establish
packaging and offline behavior, not decision quality. The wrapper accepts
`--output`, `--local` and `--family-owner`.

Open http://127.0.0.1:8000. Output is static and ignored by Git. The Pages workflow
builds and uploads this same directory. Changing the repository's Pages source
or publishing remains a separate remote action.

## Theme and media

Local theme patches support demo links, install choices, configured independent
attribution, and smaller product type on narrow phones. The theme and its
license are retained. `site/theme/build.py` alone is the lower-level renderer;
use the product wrapper to include examples and the archive.

Existing recordings and posters stay in `docs/images/`. Regenerating them is
optional and requires Playwright/Chromium and ffmpeg:

```sh
python3 scripts/record-demos.py
```

All examples are fictional. The care example concerns how a ward organises work,
not medical advice.
