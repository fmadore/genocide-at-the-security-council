# If the rebuild breaks

The website is rebuilt and redeployed by GitHub Actions whenever a change reaches
`main`. This note is for whoever has to deal with a failed deploy, including
someone new to the project. The commands are in the
[pipeline guide](../scripts/README.md); the workflow itself is
[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

**First, nothing is lost.** The deploy job only runs after the build has
succeeded, so a failed run leaves the previous version of the site online.

## How a deploy works

The workflow "Deploy dashboard" starts on a push to `main` that changes
`config/`, `scripts/`, `web/`, `annotations/`, `model_annotations/`,
`requirements.lock`, the `Makefile`, the payload contract or the workflow file. It
can also be started by hand from the Actions tab ("Run workflow").

1. It installs the locked Python environment and reads the dataset version from
   `scripts/lib/paths.py`.
2. It looks for a saved copy of the derived data (the **derived cache**), keyed on
   every input that determines it. If one exists, it skips straight to step 6 and
   never contacts Dataverse.
3. Otherwise it restores the saved copy of the corpus files (the **raw cache**),
   if there is one, and restores the semantic map from its pinned GitHub release
   (`python scripts/fetch_semantic.py`).
4. It runs `make payload`: the whole pipeline, starting with step 00, which checks
   the corpus files against the checksums in `config/dataset-pin.json` and
   downloads them from Harvard Dataverse only if they are missing.
5. It saves both caches, but only after every earlier step has succeeded.
6. It checks the data files (`python scripts/export_web.py --check`), builds the
   website and publishes it.

A rebuild without the derived cache takes about 25 minutes; the job stops after
45. Until review item B12 (8 October 2026) is fixed, the deploy does not wait for
the test workflow ("Checks"), so a change that fails the tests can still deploy.
Check that "Checks" passed too.

## Find the failing step

Open the failed run in the repository's Actions tab and expand the step with the
red cross. The last lines of its log usually name the problem. Most of the
pipeline's own errors say what to do next.

If the failure looks accidental (a network timeout, a runner problem), use
"Re-run failed jobs" once before investigating.

## Harvard Dataverse is unreachable

**Symptom:** the step "Rebuild data payload" fails in step 00 with a network
error, an HTTP error or a page that is not the expected file. In August 2026 a
bot check in front of Dataverse failed three deploys this way.

**Why it happens:** Dataverse is needed only when neither cache holds the data:
after an input changed and the raw cache has also been evicted.

**What to do:**

- Wait and re-run. Check whether <https://dataverse.harvard.edu> responds in a
  browser.
- Do not change the pin, and do not point the build at another copy of the
  files to get round it. The checksums in `config/dataset-pin.json` are what make
  the build reproducible.
- There is no second source for the corpus yet. The review of 8 October 2026
  (A9) suggests depositing the pinned files on Zenodo as one; see
  [RELEASING.md](RELEASING.md).

## A cache problem

The caches are a speed-up, never a dependency: deleting them costs a full rebuild,
nothing more. GitHub also removes caches that go unused, so a slow rebuild after a
quiet period is normal.

**Symptom:** "Verify restored or rebuilt payload" fails, or the published site
does not match the code.

**What to do:** delete the derived cache and re-run, so that the data are rebuilt
from scratch. The caches are listed under Actions → Caches; with the GitHub
command-line tool, `gh cache list` and `gh cache delete <key>`. The derived
cache's key starts with `derived-v5.0-`, the raw cache's is `raw-v5.0`.

## The semantic map cannot be restored

**Symptom:** the step "Restore the pinned semantic release" fails.

`fetch_semantic.py` downloads the archive named in
`config/semantic-release.json` from the GitHub release `semantic-2026-09-11` and
checks its SHA-256 checksums.

- **Download error:** check that the release and its file
  (`semantic-775870.zip`) still exist on GitHub. If the file was removed,
  re-attach the same file; its checksum must match the pin.
- **Checksum or corpus mismatch:** never edit the pin to match a different file.
  A new semantic map needs a new embedding run, a new release and a reviewed
  change to the pin ([CLUSTER.md](CLUSTER.md), [PLAN.md](PLAN.md#4-optional-topics-and-embeddings)).
  A corpus change that alters any speech's text, such as restoring the 24
  trimmed openings, will cause this, which is why that fix waits for the next
  embedding run (ROADMAP open item 6).

## A pipeline step refuses to continue

Many steps stop on purpose when an input is not what they expect. These refusals
protect the published numbers: fix the input, never loosen the check. To see the
error in full, rebuild locally in a fresh clone (x64 Python 3.12, GNU make 4.3 or
later; on Windows use WSL):

```bash
python -m pip install --require-hashes -r requirements.lock
python scripts/fetch_semantic.py
make payload
```

Common refusals:

| Where | Message is about | Usual cause and fix |
|---|---|---|
| Step 01 | population totals | The corpus files are not the pinned ones. Check the pin and the download. |
| Step 03 | counts differ from `config/lexicon.counts.json` | The lexicon changed without its committed counts. Follow "Changing the lexicon" in the pipeline guide. |
| Step 03 | a pattern edited without its version bump | Run `python tools/lock_lexicon.py` after bumping the term's `pattern_since`, as the pipeline guide explains. |
| Step 15 | a run that does not cover the population | Only the run named in `model_annotations/genocide/allow_partial_run.txt` may be partial; check `current_run.txt`. Until review item B6 is fixed, running step 15 directly ignores that file; use `make`. |
| Step 15 | an incompatible run (lexicon, referents, prompt) | The committed run no longer matches the corpus or the prompt archive. Do not edit the run; restore the input it was made against. |
| `export_web.py` | the payload contract | A data file's shape changed without `tests/contract/payload.json` being updated in the same change. |

## The website build fails

The steps `npm --prefix web ci` and `npm --prefix web run build` failing points to
the website code or its dependencies, not the data. Locally:

```bash
npm --prefix web ci
npm --prefix web run lint
npm --prefix web run check
npm --prefix web run build
```

## Going back to the previous version

Revert the commit that broke the build (`git revert <commit>`) and push to
`main`; the next deploy publishes the earlier state. Do not force-push `main`.

## What not to do

- Do not run `make clean` in your working copy: until review item B10 is fixed,
  it deletes files the public build cannot recreate, such as the cluster
  embeddings and the raw model responses.
- Do not edit a committed model run or its manifest to make a step pass.
- Do not change `config/dataset-pin.json` or `config/semantic-release.json` to
  match a file that differs from the pinned one.

## Getting help

The project has one maintainer, Frédérick Madore. For the services the build
depends on: Harvard Dataverse support for the corpus, and the GitHub status page
for Actions and Pages.
