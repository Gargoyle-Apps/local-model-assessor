---
name: lma-python-env
description: "Set up and use the repo-local Python virtualenv for all LMA scripts."
triggers:
  - python env
  - venv
  - pip install
  - bootstrap python
  - PEP 668
  - requirements.txt
  - scripts/py
dependencies: []
version: "1.0.0"
---

# LMA Python Environment

## When to use this skill

Load before running **any** Python script in this repo (`add-model-from-yaml.py`, `export-assessed-models.py`, `import-profiles.py`, `generate-ide-config.py`, `sweep-ide-config.py`, `generate-stack-handoff.py`, `lma_paths.py`, `export-lmo-snapshot.py`). Also load when the user hits PEP 668 errors, venv issues, or asks about the Python setup.

## Instructions

### 1. Understand the setup

All Python scripts run through the **`./scripts/py`** wrapper, which:
- Creates `.venv/` (repo-local, gitignored) if missing.
- Re-runs `pip install -r requirements.txt` when `requirements.txt` is newer than the last sync stamp inside `.venv`.
- Executes the script with the venv interpreter.

### 2. First run or after dependency changes

```bash
./scripts/bootstrap-python.sh
```

This creates `.venv/` and installs everything from `requirements.txt`.

### 3. Run any Python script

Always use the wrapper — even for stdlib-only scripts — so every agent uses the same interpreter:

```bash
./scripts/py scripts/<script>.py [args...]
```

### 4. Add new dependencies

1. Add the package to `requirements.txt` (with version pin if appropriate).
2. Run `./scripts/bootstrap-python.sh` or just run any script via `./scripts/py` — it will detect the newer `requirements.txt` and re-sync.

### 5. Manual alternative

If the wrapper isn't available or you need to debug:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
source .venv/bin/activate
```

## Notes

- macOS/Homebrew Python is often **PEP 668** ("externally managed") and will refuse global `pip install`. The venv avoids this.
- `.venv/` is gitignored — never commit it.
- `requirements.txt` currently requires **PyYAML**; future deps belong in the same file.
