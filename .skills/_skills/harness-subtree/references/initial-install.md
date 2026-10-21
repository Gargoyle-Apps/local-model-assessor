# Initial install

First-time subtree install in a consumer repo (no existing `.skills-harness/`).

## Steps

1. **Add upstream as a remote** (one-time per clone; the remote name is local-only):

   ```bash
   git remote add skills-harness https://github.com/Gargoyle-Apps/skills-harness
   git fetch skills-harness
   ```

2. **Add the subtree at `.skills-harness/`** (one-time per repo, creates a single squash commit):

   ```bash
   git subtree add --prefix=.skills-harness skills-harness main --squash
   ```

   To pin a release tag instead of `main`, see `references/pinning-and-gotchas.md`.

3. **Create the consumer-owned `.skills/` shell:**

   ```bash
   mkdir -p .skills/_skills
   ln -s ../.skills-harness/.skills/_harness .skills/_harness
   for s in .skills-harness/.skills/_skills/*/; do
     name="$(basename "$s")"
     ln -s "../../.skills-harness/.skills/_skills/$name" ".skills/_skills/$name"
   done
   ```

4. **Seed `.skills/_index.md`** by copying the upstream index. Future rows are generated from local skill frontmatter:

   ```bash
   cp .skills-harness/.skills/_index.md .skills/_index.md
   ```

5. **Seed `.skills/_meta.yml`** with the vendored kit version and default native target (mirror, not symlink — you may pin behind upstream intentionally):

   ```bash
   cp .skills-harness/.skills/_meta.yml .skills/_meta.yml
   ```

6. **Bootstrap.** Copy the bootstrap file to the repo root and follow it:

   ```bash
   cp .skills-harness/AGENTS_skills.md AGENTS_skills.md
   ```

   Open `AGENTS_skills.md` with your agent and complete **Single-Tool** (single-tool harness install) or **Tool-Neutral** (agnostic policy). Delete `AGENTS_skills.md` when done.

7. **Update `.gitignore`.** The native-discovery symlink directories (`.agents/skills/`, `.claude/skills/`) are machine-local — they should already be ignored if the Single-Tool setup added them. The selected path is persisted under `native_targets:` in `.skills/_meta.yml`. Symlinks under `.skills/` and the `.skills-harness/` subtree directory itself **are** committed.

8. **Validate:**

   ```bash
   .skills/_harness/check.sh --link
   ```

   This creates/repairs every declared native target and should pass. On subtree or `consumer_skills_dir` installs, `check.sh` also prints each `_skills/<name>/` directory symlink and target (`directory symlink → … ✓`) — use that to confirm sync, not `readlink` on inner `SKILL.md` paths. The kit version assertion compares `.skills/_meta.yml` (consumer copy) against the consumer's root `README.md` and `CHANGELOG.md` if they exist; if your consumer repo doesn't surface kit version in those files, set `SKILLS_CHECK_KIT_SURFACES=0` to skip that check.
