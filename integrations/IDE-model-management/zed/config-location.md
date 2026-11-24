# Zed configuration and local models

Zed is highly configurable through its settings UI and configuration files. Use the UI to discover options and select models; use files for precise overrides, repeatable setup, and reviewable changes. Settings accept JSON with comments and trailing commas (JSONC). The [settings reference](https://zed.dev/docs/reference/all-settings) covers appearance, editor behavior, languages, language servers, and agent settings.

## UI and configuration files

| Area | UI entry point | Configuration file on macOS/Linux |
|---|---|---|
| User settings | `zed: open settings`; `zed: open settings file` for JSON | `~/.config/zed/settings.json` |
| Supported project overrides | `zed: open project settings` | `.zed/settings.json` in the project |
| Keyboard shortcuts | `zed: open keymap`; `zed: open keymap file` | `~/.config/zed/keymap.json` |
| Reusable shell tasks | `zed: open tasks`; `zed: open project tasks` | `~/.config/zed/tasks.json` or `.zed/tasks.json` |
| AI providers and model selection | AI settings and the Agent Panel model picker | `language_models` and `agent` in user `settings.json` |

The keymap editor writes `keymap.json`. Direct editing supports context-specific shortcuts and multi-key sequences. Tasks define commands, arguments, working directories, and terminal behavior. See [keybindings](https://zed.dev/docs/key-bindings) and [tasks](https://zed.dev/docs/tasks).

Use project settings for supported workspace-specific options; not every user preference is a project override. Keep personal endpoints, installed-model inventories, and machine-specific settings in the user file or the ignored local copy below. See [Agent Settings](https://zed.dev/docs/ai/agent-settings) for provider defaults and feature-specific models. External agents and edit prediction have separate configuration paths.

## Local model providers

Zed supports Ollama, llama.cpp, and LM Studio for its built-in AI features. The following URLs are upstream defaults, not assumptions about the local machine. Check occupied ports and configure the provider URL to match its server. [Local model setup](https://zed.dev/docs/ai/use-a-local-model), [default settings](https://github.com/zed-industries/zed/blob/main/assets/settings/default.json)

| Runtime | Settings key | Default API URL | Model availability |
|---|---|---|---|
| Ollama | `language_models.ollama` | `http://localhost:11434` | Discovers pulled models; explicit `available_models` can override metadata. |
| llama.cpp | `language_models["llama.cpp"]` | `http://localhost:8080` | Discovers served models; recent router builds update capabilities as models load. |
| LM Studio | `language_models.lmstudio` | `http://localhost:1234/api/v0` | Discovers models through LM Studio's API server; start it with `lms server start`. |

For Ollama, use installed provisioned aliases and their `num_ctx` as Zed's `max_tokens`. Map `tools`, `vision`, and `reasoning` to `supports_tools`, `supports_images`, and `supports_thinking`. Set a bounded `context_window` for discovered models without explicit entries. Do not copy a model card's maximum context into a workstation configuration without checking memory.

Use `agent.default_model` for the main model. The older `assistant.default_model` example is no longer the current configuration. Keep each provider's own schema: Ollama's `supports_thinking` field is not a generic setting for all runtimes.

This repo's automatic generator/sweep currently handles Continue and Cline/Roo. Zed configuration is a manual, DB-informed merge; Zed's provider discovery can find newly served models, but it does not synchronize LMA's role-specific context overrides. Review explicit entries when aliases change.

## Reference-driven configuration updates

Use this guide for initial configuration and subsequent updates. Consult the [full settings reference](https://zed.dev/docs/reference/all-settings) for each requested behavior, alongside the provider-specific documentation above. The reference covers more than local AI; select settings that serve the requested workflow. Keep unspecified settings inherited from Zed rather than copying its entire defaults file. Upstream defaults can vary by language, platform, and release channel.

For each configuration task:

1. Inspect the installed Zed version, existing user JSONC, applicable project overrides, and the local software profile. For model changes, query the current DB roles and verify runtime/model availability. Do not infer local choices from shared examples.
2. Find the documented key, value type, allowed values, scope, and dependencies for the desired behavior. Check compatibility with the installed release; online documentation or the upstream main branch may describe a newer version. Use Zed's settings completion/diagnostics and installed defaults where available to confirm support.
3. Prepare a focused change in the ignored local copy below. Update existing keys in place and add missing keys within the correct object. Never append a second JSON document or duplicate a property. Merge nested objects while preserving unrelated values; reconcile model arrays by model name rather than replacing the whole inventory. Remove obsolete aliases only when their removal is part of the task.
4. Preserve comments, trailing-comma compatibility, and unrelated preferences with JSONC-aware edits. Parse the result to check syntax and check for duplicate keys; parsing alone does not establish that Zed supports a setting. Review the diff against the requested behavior and verify references such as provider/model pairs and context limits.
5. Back up the live file, recheck that it has not changed since inspection, and merge the prepared changes. If it changed, reconcile against the latest contents first. Check Zed's settings diagnostics and, when available, exercise the affected feature. Report separately what was configured, what was tested, and what still needs a running server or application check.

The same process applies to requested editor, language/LSP, formatting, terminal, appearance, and agent customization. Look up each setting's scope before choosing user or project configuration. Keybindings and tasks use their own files as described above.

These are reusable instructions for an agent-assisted update, not an implemented Zed settings generator. Keep selected values, deployment backups, and machine-specific results local. Store staged `settings.json` changes only at the ignored path below; keep backups beside the external user settings or in ignored local storage. A project `.zed/settings.json` is not automatically local-only: verify its ignore status before placing personal values there. Shared project settings require an intentional, portable repository change.

## Local copy and deployment

Merge changes into the existing user file, preserving unrelated preferences and JSONC comments. Back up before deployment. Keep a local reference at the already-ignored path:

```bash
cp ~/.config/zed/settings.json integrations/IDE-model-management/zed/settings.json
```
