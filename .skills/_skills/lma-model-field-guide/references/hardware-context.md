# Hardware context for field guides

This is a reporting contract, not a new hardware-profile schema. No simulation field is required or added to profiles or the database.

## Target, source, and status

- The assessment target is the hardware the user asks about. The executing host is the machine running the tools; do not substitute it for the target. Record their relationship as same, different, or unknown without hostnames or identifiers.
- Use an explicitly supplied target/profile first, then `computer-profile/hardware-profile.yaml`, then the selected database's `hardware_profile` row (`id = 1`) if the file is absent. These fallbacks must describe the same target: do not fill a proposed target's missing fields from an unrelated local profile. Read software/runtime evidence for the same target; do not use the host's installed software to fill hypothetical-target gaps. Explicit user corrections override older profile values; record that provenance without editing the profile.
- **Actual:** the user explicitly identifies the target as existing hardware, or current observations verify that the profile describes that target. Label user-reported and observed evidence separately. A file's presence or a familiar hardware name is not verification.
- **Hypothetical:** the user explicitly describes a proposed, simulated, or what-if target. A legacy profile that explicitly says it is simulated is also evidence, but `mode: "dry_run"` alone is ambiguous and does not establish this status.
- **Unknown:** neither status is supported, the profile is missing, or conflicting evidence is unresolved. Absence of a simulation marker never proves actual hardware. If explicit current instructions do not resolve a conflict, state it and keep the status unknown.
- Record status and its evidence in the ignored report only. A hypothetical assessment still writes its requested report; it does not authorize profile/DB writes. Operation-level dry-run flags describe write behavior, not hardware reality.

## Read-only database fallback

Use the supported query wrapper, which honors `LMA_DB` (otherwise `model-data/model-assessor.db`):

```bash
./scripts/query-db.sh --readonly "SELECT yaml_content FROM hardware_profile WHERE id = 1;"
```

Report the selected source as the profile path or `LMA_DB`/default database plus table; do not dump environment variables or private absolute paths into shared resources. Missing DB, table, row, unreadable YAML, or incomplete data means unavailable evidence. Do not initialize, migrate, import profiles, fall back to a different DB when an override is missing, or query a user's datastore during synthetic evaluations. Follow `lma-db-core` for database conventions and `lma-python-env` for Python execution.

## Derive capacity from supplied evidence

1. Establish units (GB versus GiB), memory type, node count, and whether each value is per node or aggregate. Do not add discrete VRAM to host RAM or count unified memory twice. An unspecified node count or memory scope remains unknown.
2. Interpret `vram_budget.total_available` as the allocation ceiling before `os_headroom_gb`, per the shared template. Per-node effective budget is `total_available - os_headroom_gb`; co-run budget also subtracts `concurrency_reserve`. If source values already subtract a reserve, reconcile them explicitly instead of subtracting twice. Missing or inconsistent reserves require conditional bounds, not invented defaults.
3. Compare the current model/quantization's resident weights, KV cache at the requested context and concurrency, runtime buffers, and auxiliary components against that budget. Disk checkpoint size is not automatically resident memory; active MoE parameter count is not the weight footprint. Label estimates and their sources; do not promise speed from capacity alone.
4. Report aggregate physical memory separately. Multiple nodes do not imply pooled memory: establish runtime sharding support, per-node placement and overhead, and interconnect requirements before a distributed-fit verdict. SSD offload likewise needs documented support and a latency caveat, not an assumed rescue path.
5. Check the target's OS, accelerator and runtime support independently of memory fit. Distinguish “fits the supplied memory estimate” from “deployment supported/verified.” With missing inputs, give conditional guidance and list the unknowns; do not inherit a previous scenario's budget or deployment conclusion.
