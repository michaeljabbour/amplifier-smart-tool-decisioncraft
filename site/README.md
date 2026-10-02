# Website

Decisioncraft's product page uses the Amplifier Smart Tools family theme. Page content
lives in `site.json`. `site/theme/` is a versioned copy of the family theme (version
0.1.0, MIT licensed; see `site/theme/LICENSE`), so a build does not depend on a moving
remote theme or an online service.

Local changes to the copy:

- `site/theme/family.json` registers this page under the key `decisioncraft`, because the
  theme looks up each page's repository there.
- `site/theme/build.py`: a capability demo may set `link` and `link_text` to add a link
  next to "Watch full size". The page uses it to open each example canvas, which the
  publish step copies to `examples/<name>.html`.
- An install band under the hero (`install_options` and `install_footnote` in `site.json`, rendered by `install_options()` in `build.py`, styled at the end of `style.css`), and a smaller product name on phones narrower than 520px.

## Build and preview

From the repository root, with Python 3.11 or later:

```sh
python3 -m venv .work/site-venv
.work/site-venv/bin/python -m pip install -r site/requirements.txt
.work/site-venv/bin/python site/theme/build.py
python3 -m http.server 8000 --directory _site --bind 127.0.0.1
```

Open http://127.0.0.1:8000. Output goes to `_site/`, which Git ignores. The page is
static; visitors need no Python and no account.

`build.py` also accepts `--family-owner` (where the family overview and catalog live) and
`--local` (link sibling pages on one preview server). Use the same settings as the rest
of the family.

## Images and video

`build.py` copies the media named in `site.json` from `docs/images/`. The demo videos
and posters are screen recordings of the four examples, made headlessly:

```sh
python3 scripts/build-examples.py
python3 scripts/record-demos.py      # needs Playwright with Chromium, and ffmpeg
```

All examples are fictional. The medical example is about how a ward organises its work
and is not medical advice.

## Updating the theme

Copy a newer `site/theme/` from the family repository, keep the `decisioncraft` entry in
`family.json`, review the diff, and build again. Page content stays in `site.json`.
