# BookBridge GitHub Pages synthetic load test v0.3

## Purpose

This is a **deployment capacity test**. It does **not** read or publish your existing BookBridge database, index, books, source metadata, or any existing site. The workflow builds only random synthetic binary shards directly on a GitHub Actions runner.

The **full** scale simulates these observed technical properties from your November 13, 2026 private full-index preflight:

- 17,845 synthetic shard files
- ~255.91 MiB of non-compressible shard payload
- one shard ~4.96 MiB
- 1.76 MiB synthetic manifest
- 17,848 published files (shards + HTML + health + manifest)
- ~257.68 MiB site footprint

This is **not** a test of real index searches, metadata licensing, or unattended updates. A successful deployment only validates this particular GitHub Pages payload, plus two sample fetch-and-hash checks. There is no live BookBridge schema/format in this synthetic test.

## Publish in its own new repo (Windows PowerShell)

Unzip `BookBridge_GitHub_Pages_Synthetic_Load_Test_v0.3.zip` on your Desktop. Then:

```powershell
cd "$env:USERPROFILE\Desktop\BookBridge_Pages_Load_Test_v0.3"
git init -b main
git config user.name "dhawk0"
git config user.email "$(gh api user --jq .id)+dhawk0@users.noreply.github.com"
git add .
git commit -m "Add synthetic GitHub Pages load test"
gh repo create dhawk0/bookbridge-pages-load-test --public --source=. --remote=origin --push
```

If the repository already exists, don't run `gh repo create` again; configure a remote and push only after checking its contents.

Open `https://github.com/dhawk0/bookbridge-pages-load-test/settings/pages` and set **Source: GitHub Actions** (not Deploy from a branch).

### Run a lightweight smoke test first

```powershell
gh workflow run pages-load-test.yml --repo dhawk0/bookbridge-pages-load-test -f scale=smoke
gh run list --repo dhawk0/bookbridge-pages-load-test --workflow pages-load-test.yml --limit 3
```

Wait for the GitHub Actions run to complete in the repo's Actions tab and then visit:

`https://dhawk0.github.io/bookbridge-pages-load-test/`

Click **Verify first and largest static shard**. Both should show PASS.

### Then run the full synthetic-scale test

```powershell
gh workflow run pages-load-test.yml --repo dhawk0/bookbridge-pages-load-test -f scale=full
gh run list --repo dhawk0/bookbridge-pages-load-test --workflow pages-load-test.yml --limit 3
```

Open the new run in the Actions tab and inspect whether the Generate, Upload, and Deploy steps complete. Test the site again and record the two fetch times. This replaces only the **separate synthetic load-test site** with a larger synthetic payload.

## Safety and practical cautions

- Do **not** put `bookbridge-gh-full-v1`, the SQLite DB, or any real LibGen.li archive in the load-test repo.
- The initial git push is tiny: the 258 MiB synthetic site is generated in Actions, not committed to Git.
- The published site is public and serves **only random synthetic data**.
- Pages has a 1 GB published size limit and a 10-minute deployment timeout; deployment may fail despite passing a local size preflight.
- This workflow has no scheduled trigger, automatic updates, database import, or acquisition actions.
- Running the full test uses GitHub Actions minutes, storage and Pages bandwidth. Avoid repeated full runs without a reason.
- Never equate a successful synthetic deployment with authorization to publicly redistribute the actual LibGen metadata.

## Local smoke test (optional)

```bash
python3 generate_synthetic_site.py --scale smoke --output /tmp/bookbridge-pages-smoke
```

Expected: 64 shards, 67 files, approximately 2.01 MiB. Do not point `--output` at an existing nonempty directory.
