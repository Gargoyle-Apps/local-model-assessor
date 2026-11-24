# IDE Model Management

Docs + config references for IDE agents ↔ `model-data/model-assessor.db`.

**Generate:** `./scripts/py scripts/generate-ide-config.py` — `provisioned_models` (+ `models`); `--target continue|cline`, `--active-only`, `--dry-run`. **Sweep (preferred):** `./scripts/py scripts/sweep-ide-config.py` — syncs `is_active` from `ollama list`, regenerates configs for agents named in `software-profile.yaml`, deploys Continue to `~/.continue/config.yaml`. Run after every model add/remove or clone create (`lma-ide-config` skill). Cline/Roo keys sanitize alias (`:` → `-`). Use repo `.venv` via `lma-python-env` skill.

**Embed + Postgres stack:** [embed-retrieval-stack.md](../embed-retrieval-stack/embed-retrieval-stack.md) · `generate-stack-handoff.py` → `integrations/embed-retrieval-stack/out/` (assessed **embedding** in DB).

**DB:** `model-assessor.db` · `./scripts/query-db.sh` · hardware: `computer-profile/hardware-profile.yaml`

---

## Folder layout

Per app: **`config-location.md`** (tracked), **`.gitkeep`**, optional **local config copy** (gitignored).

---

## Overview: Role Mapping

| This repo (`role_model`) | Typical agent use |
|--------------------------|-------------------|
| `coding.primary`         | Chat, Edit, Apply (main agent) |
| `vision.primary`         | Chat with image input |
| `reasoning.primary`      | Chat, Edit (logic / no tools) |
| `autocomplete.balanced`  | Autocomplete / ghost text |
| `embedding.primary`      | Embed / RAG indexing |

Query the DB for current assignments:
```bash
./scripts/query-db.sh "SELECT role, variant, model_id FROM role_model"
./scripts/query-db.sh "SELECT model_id, ctx, tools, vision, reasoning FROM models"
```

---

## Supported Apps

| App | Config format | Subfolder |
|-----|--------------|-----------|
| Continue | `config.yaml` | [continue/](continue/) |
| Cline / Roo Code | JSON (provider settings) | [cline/](cline/) |
| OpenCode | `opencode.json` | [opencode/](opencode/) |
| Goose | `config.yaml` | [goose/](goose/) |
| Pi | `settings.json` + `models.json` | [pi/](pi/) |
| Zed | `settings.json` | [zed/](zed/) |

---

## Timeout Policy

IDEs default to short HTTP timeouts that cause failures when Ollama needs time for cold loads, large context pre-fill, or agentic multi-turn loops. The config generator (`scripts/generate-ide-config.py`) applies these role-based timeouts:

| Role category | Timeout (ms) | Rationale |
|---------------|-------------|-----------|
| **Autocomplete / embedding / OCR** | `60000` (60 s) | Snappy roles — if completion takes > 1 min, the user has moved on |
| **Chat / coding / reasoning / vision / creative / heavy_lifter** | `300000` (5 min) | Deep roles — large context pre-fill and agentic loops need a long leash |

These values map to:
- **Continue:** `requestOptions.timeout` on each `models[]` entry; `autocompleteOptions.modelTimeout` on autocomplete entries
- **Cline / Roo Code:** `requestTimeoutMs` in the API provider configuration
- **Other IDEs:** Apply the same ms values to whatever timeout field the app exposes (see per-app sections)

---

## Continue (VS Code)

**Docs:** [Continue config reference](https://docs.continue.dev/reference)
**Config file:** `config.yaml` — see [continue/config-location.md](continue/config-location.md)
**Default location:** `~/.continue/config.yaml`

### Role mapping → Continue

| DB query | Continue config |
|----------|----------------|
| `role='coding', variant='primary'` | `roles: [chat, edit, apply]`, `capabilities: [tool_use]` |
| `role='vision', variant='primary'` | `roles: [chat]`, `capabilities: [image_input]` |
| `role='reasoning', variant='primary'` | `roles: [chat, edit]` (no capabilities) |
| `role='autocomplete', variant='balanced'` | `roles: [autocomplete]` |
| `role='embedding', variant='primary'` | `roles: [embed]` |
| `role='ocr', variant='primary'` | `roles: [embed]` (OCR uses the embed role path in Continue) |

### Config block template

When provisioned aliases exist, use the alias as `model` and `num_ctx` as `contextLength`:

```yaml
models:
  - name: "qwen3:30b_coding_8k (coding)"
    provider: ollama
    model: qwen3:30b_coding_8k      # provisioned alias from DB
    apiBase: http://localhost:11434
    roles: [chat, edit, apply]
    capabilities: [tool_use]
    defaultCompletionOptions:
      contextLength: 8192            # from provisioned_models.num_ctx
    requestOptions:
      timeout: 300000                # chat/coding → 5 min
```

Autocomplete entries get a shorter timeout:

```yaml
  - name: "granite4:3b_autocomplete_8k (autocomplete)"
    provider: ollama
    model: granite4:3b_autocomplete_8k
    apiBase: http://localhost:11434
    roles: [autocomplete]
    defaultCompletionOptions:
      contextLength: 8192
    requestOptions:
      timeout: 60000
    autocompleteOptions:
      debounceDelay: 250
      maxPromptTokens: 2048
      modelTimeout: 60000
```

### Setup steps (on-demand)

1. Run `./scripts/py scripts/sweep-ide-config.py` (or `generate-ide-config.py --target continue` with `--dry-run` to preview only)
2. Review the generated `integrations/IDE-model-management/continue/generated/config.yaml`
3. `sweep-ide-config.py` merges LMA-managed model entries into `~/.continue/config.yaml` (backs up first, preserves your other keys and custom models). To preview without writing, use `generate-ide-config.py --target continue --dry-run`.
4. Restart Continue to pick up changes

---

## Cline / Roo Code (VS Code)

**Cline docs:** [Cline — GitHub](https://github.com/cline/cline)
**Roo Code docs:** [Roo Code — GitHub](https://github.com/RooVetGit/Roo-Code)
**Config file:** JSON (provider settings) — see [cline/config-location.md](cline/config-location.md)
**Config location:** Managed through the extension UI; export/import as JSON.

Cline and Roo Code are autonomous agent extensions that read/write files in agentic loops. A timeout mid-loop breaks the entire chain, so chat-tier timeouts (300 s) are critical.

### Role mapping → Cline / Roo

| DB query | Cline/Roo config |
|----------|-----------------|
| `role='coding', variant='primary'` | Primary `ollamaModelId` with `requestTimeoutMs: 300000` |
| `role='autocomplete', variant='…'` | Separate profile or model with `requestTimeoutMs: 60000` |
| `role='embedding', variant='primary'` | Roo embedding model (if applicable); use Snappy alias + short timeout |

### Config block template

```json
{
  "apiConfiguration": {
    "apiProvider": "ollama",
    "ollamaModelId": "qwen3:30b_coding_8k",
    "apiBaseUrl": "http://localhost:11434",
    "requestTimeoutMs": 300000
  }
}
```

### Setup steps (on-demand)

1. Run `./scripts/py scripts/sweep-ide-config.py` (or `generate-ide-config.py --target cline` with `--dry-run` to preview only)
2. Review the generated `integrations/IDE-model-management/cline/provider-settings.json`
3. In VS Code, open Cline/Roo settings → API Configuration → import or paste the relevant profile
4. For Roo Code embedding: verify the embedding model timeout is also adequate

---

## OpenCode

**Docs:** [OpenCode config reference](https://opencode.ai/docs/config/)
**Config file:** `opencode.json` or `opencode.jsonc` — see [opencode/config-location.md](opencode/config-location.md)
**Default location:** `~/.config/opencode/opencode.json` (global) or `opencode.json` (project root)

### Role mapping → OpenCode

| DB query | OpenCode config |
|----------|----------------|
| `role='coding', variant='primary'` | `model` (main model) |
| `role='coding', variant='quick'` | `small_model` (lightweight tasks) |
| `role='embedding', variant='primary'` | Not directly configured; use via MCP or external |

OpenCode uses `provider` + `model` at the top level. For Ollama:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {}
  },
  "model": "ollama/model-name:tag",
  "small_model": "ollama/small-model:tag"
}
```

### Config block template

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {}
  },
  "model": "ollama/qwen3-coder:30b",
  "small_model": "ollama/granite4:3b",
  "tools": {}
}
```

### Setup steps (on-demand)

1. Query DB for current role assignments
2. Generate `opencode.json` using the role mapping above
3. Write to project root (`opencode.json`) or `~/.config/opencode/opencode.json` (global)
4. Optionally save a copy to `integrations/IDE-model-management/opencode/opencode.json` as local reference

---

## Goose (CLI / Desktop)

**Docs:** [Goose — Configure LLM Provider](https://block.github.io/goose/docs/getting-started/providers)
**Config file:** `config.yaml` — see [goose/config-location.md](goose/config-location.md)
**Default location:** `~/.config/goose/config.yaml`

### Role mapping → Goose

| DB query | Goose config |
|----------|-------------|
| `role='coding', variant='primary'` | Main model (via `goose configure` or `GOOSE_MODEL`) |

Goose selects one primary model. It supports lead/worker multi-model configs for advanced use.

### Setup steps (on-demand)

1. Query DB for the primary coding model
2. Run `goose configure` → Configure Providers → Ollama → set `OLLAMA_HOST` → select model
3. Or set env: `export OLLAMA_HOST=http://localhost:11434` and `export GOOSE_MODEL=model:tag`
4. Optionally save a copy to `integrations/IDE-model-management/goose/config.yaml` as local reference

---

## Pi (Terminal)

**Docs:** [Pi coding-agent docs](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/docs)
**Config files:** `settings.json` + `models.json` — see [pi/config-location.md](pi/config-location.md)
**Default location:** `~/.pi/agent/settings.json` (global), `.pi/settings.json` (project)

### Role mapping → Pi

| DB query | Pi config |
|----------|----------|
| `role='coding', variant='primary'` | `defaultModel` in `settings.json` |
| All assessed Ollama models | Listed in `models.json` under `providers.ollama.models` |

Pi supports a single active model but can cycle between configured models with Ctrl+P.

### Config block template — `models.json`

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "models": [
        { "id": "model:tag", "name": "Display Name", "contextWindow": 32768 }
      ]
    }
  }
}
```

### Config block template — `settings.json`

```json
{
  "defaultProvider": "ollama",
  "defaultModel": "model:tag",
  "defaultThinkingLevel": "medium"
}
```

### Setup steps (on-demand)

1. Query DB for role assignments and all assessed models
2. Generate `models.json` with Ollama provider and model list (use `ctx` from DB for `contextWindow`)
3. Generate `settings.json` with `defaultProvider: "ollama"` and primary coding model as `defaultModel`
4. Write to `~/.pi/agent/models.json` and `~/.pi/agent/settings.json`
5. Optionally save copies to `integrations/IDE-model-management/pi/` as local reference

---

## Zed (Editor)

**Docs:** [Local models](https://zed.dev/docs/ai/use-a-local-model), [Agent settings](https://zed.dev/docs/ai/agent-settings)
**Config file:** `settings.json` (JSONC) — see [zed/config-location.md](zed/config-location.md) for UI vs file customization, keybindings, tasks, and local providers.
**Default location:** `~/.config/zed/settings.json` (global) or `.zed/settings.json` (project)

Zed supports local Ollama, llama.cpp, and LM Studio providers. For Ollama, explicit `available_models` entries let you override discovered context and capability metadata. Zed's settings UI and JSONC files both expose customization; files also make configuration changes easy to review and reproduce.

### Role mapping → Zed

| DB query | Zed config |
|----------|-----------|
| Installed clone for `role='coding', variant='primary'` | `agent.default_model` (main agent model) |
| Installed conversational Ollama aliases | Listed in `language_models.ollama.available_models` |

Map DB columns to Zed's Ollama per-model fields: `tools` → `supports_tools`, `vision` → `supports_images`, `reasoning` → `supports_thinking`, provisioned `num_ctx` → `max_tokens`. Exclude embedding-only models from the chat list. The example below is synthetic; replace the alias and context with an installed, assessed choice.

### Config block template

```json
{
  "language_models": {
    "ollama": {
      "api_url": "http://localhost:11434",
      "auto_discover": true,
      "context_window": 8192,
      "available_models": [
        {
          "name": "model:tag",
          "display_name": "Display Name",
          "max_tokens": 32768,
          "supports_tools": true,
          "supports_images": false,
          "supports_thinking": false,
          "keep_alive": "5m"
        }
      ]
    }
  },
  "agent": {
    "default_model": {
      "provider": "ollama",
      "model": "model:tag"
    }
  }
}
```

### Setup steps (on-demand)

For initial setup and later updates, follow the [reference-driven configuration workflow](zed/config-location.md#reference-driven-configuration-updates). It covers version checks, JSONC merges, validation, and the full Zed settings reference beyond local-model configuration.

1. Query DB for installed conversational aliases and role assignments.
2. Build `language_models.ollama.available_models` using each alias's `num_ctx` and assessed capabilities.
3. Set `agent.default_model` to the installed primary coding alias.
4. Configure optional llama.cpp or LM Studio provider URLs to match their local servers; see [provider settings](zed/config-location.md#local-model-providers).
5. Back up and merge into user `~/.config/zed/settings.json`, preserving unrelated preferences. Keep supported project-specific overrides separate.
6. Optionally save a copy to `integrations/IDE-model-management/zed/settings.json` as local reference. Zed is currently configured manually; the automatic sweep handles Continue and Cline/Roo.

---

## Adding another app

1. Create `integrations/IDE-model-management/<app-name>/` with:
   - `config-location.md` — where the app loads config from
   - `.gitkeep`
2. Add a section in this file with:
   - Link to the app's config docs
   - Role mapping table (DB roles → app config)
   - Config block template
   - On-demand setup steps
3. Add gitignore entries for the app's local config files
4. Do NOT pre-create config files — only generate when the user asks
