# Security: remove the git-tracked Gmail app password (file fix + history purge + gc)

**Date:** 2026-06-11 · **Status:** ACTIVE — Step 0 is the owner's, Steps 1-2 immediate, Steps 3-6 scheduled
**Finding (2026-06-11 doc-rationalization audit):** `reproduce/upgrade-validation/email_config.py`
contains a plaintext Gmail **app password** for carrollcdc@gmail.com, git-tracked since commit
`72d96cca` (2026-02-04). Repo is currently **private**, but (a) every clone/collaborator/CI checkout
already has it, and (b) the repo is intended for external availability — the secret would ship in
history. **This plan file must never contain the secret itself.**

## Direct answer to the owner's question

> Can I (1) fix the file itself; (2) purge all history of the file; (3) garbage collect — and fix it that way?

**Yes — that is the right backbone, with two amendments:**

1. **Revoke FIRST (new Step 0).** A purge cleans *this* repository, but the password must be treated as
   compromised already: it exists in every clone (this machine's main checkout, the doc-rationalization
   worktree, your other worktree, any collaborator/CI clone), and purges don't reach clones. Revoking the
   app password (Google Account → Security → 2-Step Verification → App passwords → delete) takes ~1 minute
   and kills the credential **everywhere at once**. After revocation, the string in history is inert and
   the purge becomes pre-publication hygiene rather than an emergency.
2. **gc alone doesn't finish the job on GitHub.** After a history rewrite + force-push, the *old* commits
   remain fetchable by SHA on GitHub's servers until **their** gc runs — local `git gc` doesn't touch that.
   The complete server-side step is: force-push all refs, then (belt-and-braces for a private repo) ask
   GitHub Support to run a server-side gc / use their "remove sensitive data" process. Post-revocation
   this is non-urgent, but do it before any public flip.

## The plan

### Step 0 — REVOKE (owner, now, ~1 min)
Google Account → Security → 2-Step Verification → App passwords → delete the HAFiscal/SMTP one.
If the email-notification pipeline is still wanted: generate a NEW app password and provide it via the
environment (Step 1's pattern), never in a tracked file.

### Step 1 — fix the file (immediate, canonical branch)
Replace the literal with an env read:
```python
SENDER_PASSWORD = os.environ.get("HAFISCAL_SMTP_APP_PASSWORD", "")  # never commit a credential here
```
plus a comment pointing at this plan. (Optional: support an untracked `email_config_local.py` override
+ `.gitignore` entry.) This stops re-exposure going forward; it does NOT clean history — that's Step 3.

### Step 2 — scope verification (immediate, read-only)
- `git log --all -S '<secret>'` → enumerate every commit/branch whose tree contains it (running now;
  results recorded below when done).
- Confirm the secret appears in no other file/blob (`--name-only` union) and in no GitHub-side surface
  (PR bodies, issues, Actions logs — none expected; verify).
- Forks/mirrors check (`gh api .forks_count`, REMARK mirrors): a fork would need its own purge or deletion.
- While here: run a full-history secret scan (`gitleaks detect` or trufflehog) so Step 3 purges
  EVERYTHING in one rewrite, not just this one string.

### Step 3 — history purge (scheduled — see "When", below)
Tool: **`git filter-repo`** (BFG acceptable; deprecated `filter-branch` is not).
Preferred mode: `--replace-text` (secret → `***REMOVED***`) rather than deleting the file path —
it preserves the file's (harmless) history and catches the string in ANY blob, not just that path.
Mechanics — do the rewrite in a **fresh mirror clone** (filter-repo refuses/complicates in-place work,
and this repo has active worktrees):
```
git clone --mirror git@github.com:llorracc/HAFiscal-Latest.git purge-mirror
cd purge-mirror
echo '<secret>==>***REMOVED***' > /tmp/replacements.txt   # file deleted after use
git filter-repo --replace-text /tmp/replacements.txt
git push --force --all && git push --force --tags
```

### Step 4 — server-side cleanup
Force-push (Step 3) replaces all refs. Then: GitHub Support request for server-side gc of the now-dangling
objects (private repo ⇒ low urgency post-revocation, but REQUIRED before flipping public). Re-enable any
branch protections that blocked force-push.

### Step 5 — every working copy resets (coordination — the real cost)
Rewritten history diverges from every existing clone. For each working copy (this machine's main checkout,
the `-doc-rationalization` worktree, the owner's other worktree(s), any collaborator/CI clone): finish/park
in-flight work (commit+push BEFORE Step 3; the rewrite preserves content, only SHAs change), then re-clone
(cleanest) or `git fetch && git reset --hard origin/<branch>` + `git reflog expire --expire=now --all &&
git gc --prune=now --aggressive`. All open side branches survive the rewrite (filter-repo rewrites every
ref) but their local copies must be re-synced; SHA references in docs/conclusions (commit hashes cited in
manifests, plans, BUGS files) will point at pre-rewrite SHAs — acceptable (they remain meaningful labels),
note it in the rewrite commit... (filter-repo keeps a SHA map in `.git/filter-repo/commit-map`; archive it).

### Step 6 — pre-publication gate (standing)
Add to the publication checklist: full-history secret scan (gitleaks) green before any public flip or
external hand-off. This finding is exactly the class such a gate catches.

## When to run Step 3 (the rewrite)
NOT mid-flight. Preconditions: (a) Step 0 done (revoked); (b) Baseline welfare chain finished; (c) the
doc-rationalization branch merged or parked-and-pushed; (d) other active sessions (QE-proof) at a clean
pushed state; (e) ~30-min maintenance window where no one pushes. Post-revocation the risk is dormant,
so correctness of coordination beats speed.

## Rollback / safety
The mirror clone made in Step 3 is itself the backup of pre-rewrite history (keep it offline until the
team confirms nothing was lost, then delete it — it contains the secret). Nothing else destructive happens
until the force-push; up to that moment everything is reversible.

## Execution log
- **Step 0 DONE (2026-06-11): owner revoked the Gmail app password.** The history-resident string is now inert.
- Step 1 DONE earlier (commit 1f677e08): file reads HAFISCAL_SMTP_APP_PASSWORD from the environment.
- Step 2 scope final: 1 introducing commit (72d96cca), 1 file, no other blob; 47 branches. **Forks defused:**
  both forks (econ-ark/HAFiscal-Latest upd. 2026-01-17; ahinsa23/HAFiscal-Latest upd. 2025-12-13) last
  synced BEFORE the credential commit (2026-02-04) — their refs never contained it; no per-fork purge
  needed. Parent-side GitHub-support gc still required before any public flip.
- Purge script ready: /tmp/hafiscal_purge_credential.sh (sudo; enforces no-running-jobs + clean-worktrees;
  rehearse with --no-push). Run after the Baseline welfare chain finishes.
