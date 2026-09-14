-- Local Model Assessor Database Schema
-- SQLite 3.x — single source of truth for models, profiles, and assessments
--
-- Table classification:
--   CONTENT tables (models, role_model, constraint_model, task_category,
--     model_docs, provisioned_models) — carry provenance columns.
--   CONFIG tables (meta, hardware_profile, software_profile) — no provenance.
--   LOOKUP tables (decision_tree, rag_pipeline) — lightweight, no provenance.
--
-- Provenance columns (on CONTENT tables):
--   created_at / created_by / created_by_type  — set once on first insert, never overwritten
--   updated_at / updated_by / updated_by_type  — set on every insert or update
--   created_by_type / updated_by_type: 'local' | 'cloud' | 'human'
--
-- Well-known meta keys:
--   last_ollama_scan: ISO 8601 timestamp of last ollama-search.md run
--   last_inventory_reconcile: UTC timestamp of last reconcile-inventory.py --from-ollama run
--
-- Inventory (models.inventory_status):
--   present: still in the assessed catalog (may or may not be pulled yet)
--   removed: known gone from the local fleet; row kept for history (never DELETE)
--   removed_at is optional. removed_at_confidence is 'authoritative' | 'best_guess' | NULL.

-- Meta / config (replaces _meta, recommended_fleet)
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);

-- Models: core model specifications
CREATE TABLE IF NOT EXISTS models (
  model_id TEXT PRIMARY KEY,
  vram REAL NOT NULL,
  ctx INTEGER NOT NULL,
  class TEXT NOT NULL,
  tps INTEGER NOT NULL,
  url TEXT,
  install TEXT NOT NULL,
  runtime TEXT DEFAULT 'ollama',
  vision INTEGER DEFAULT 0,
  tools INTEGER DEFAULT 0,
  reasoning INTEGER DEFAULT 0,
  moe INTEGER DEFAULT 0,
  fim INTEGER DEFAULT 0,
  structured INTEGER DEFAULT 0,
  creative TEXT,
  multilingual INTEGER DEFAULT 0,
  rag INTEGER DEFAULT 0,
  no_corun INTEGER DEFAULT 0,
  latency TEXT,
  superseded_by TEXT,
  user_flag_for_deletion INTEGER DEFAULT 0,
  inventory_status TEXT NOT NULL DEFAULT 'present'
    CHECK (inventory_status IN ('present', 'removed')),
  removed_at TEXT,
  removed_at_confidence TEXT
    CHECK (removed_at_confidence IS NULL
           OR removed_at_confidence IN ('authoritative', 'best_guess')),
  removal_notes TEXT,
  assessed_at TEXT DEFAULT (datetime('now')),
  created_at TEXT DEFAULT (datetime('now')),
  created_by TEXT,
  created_by_type TEXT,
  updated_at TEXT DEFAULT (datetime('now')),
  updated_by TEXT,
  updated_by_type TEXT
);

-- Role assignments: by_role.{role}.{variant} → model
CREATE TABLE IF NOT EXISTS role_model (
  role TEXT NOT NULL,
  variant TEXT NOT NULL,
  model_id TEXT NOT NULL,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  created_by TEXT,
  created_by_type TEXT,
  updated_at TEXT DEFAULT (datetime('now')),
  updated_by TEXT,
  updated_by_type TEXT,
  PRIMARY KEY (role, variant),
  FOREIGN KEY (model_id) REFERENCES models(model_id)
);

-- Constraint assignments: by_constraint.{constraint} → models
CREATE TABLE IF NOT EXISTS constraint_model (
  constraint_name TEXT NOT NULL,
  model_id TEXT NOT NULL,
  sort_order INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  created_by TEXT,
  created_by_type TEXT,
  updated_at TEXT DEFAULT (datetime('now')),
  updated_by TEXT,
  updated_by_type TEXT,
  PRIMARY KEY (constraint_name, model_id),
  FOREIGN KEY (model_id) REFERENCES models(model_id)
);

-- Task categories: by_task_category.{category} → roles
CREATE TABLE IF NOT EXISTS task_category (
  category TEXT NOT NULL,
  role_name TEXT NOT NULL,
  sort_order INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  created_by TEXT,
  created_by_type TEXT,
  updated_at TEXT DEFAULT (datetime('now')),
  updated_by TEXT,
  updated_by_type TEXT,
  PRIMARY KEY (category, role_name)
);

-- Decision tree: need_* → fallback chain
CREATE TABLE IF NOT EXISTS decision_tree (
  need_key TEXT PRIMARY KEY,
  chain_text TEXT NOT NULL
);

-- RAG pipelines
CREATE TABLE IF NOT EXISTS rag_pipeline (
  pipeline_name TEXT PRIMARY KEY,
  embedding_model TEXT,
  synthesis_model TEXT,
  generation_model TEXT,
  rules_model TEXT,
  notes TEXT
);

-- Model documentation (for assessed-models.md generation)
CREATE TABLE IF NOT EXISTS model_docs (
  model_id TEXT PRIMARY KEY,
  spec_table TEXT,
  description TEXT,
  best_for TEXT,
  caveats TEXT,
  creative_tier TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  created_by TEXT,
  created_by_type TEXT,
  updated_at TEXT DEFAULT (datetime('now')),
  updated_by TEXT,
  updated_by_type TEXT,
  FOREIGN KEY (model_id) REFERENCES models(model_id)
);

-- Provisioned model clones: role-tuned Ollama aliases (Modelfile overrides)
CREATE TABLE IF NOT EXISTS provisioned_models (
  alias             TEXT PRIMARY KEY,
  base_model_id     TEXT NOT NULL,
  role              TEXT NOT NULL,
  variant           TEXT NOT NULL DEFAULT 'primary',
  num_ctx           INTEGER NOT NULL,
  temperature       REAL,
  num_predict       INTEGER,
  repeat_penalty    REAL,
  repeat_last_n     INTEGER,
  system_prompt     TEXT,
  modelfile_content TEXT NOT NULL,
  modelfile_path    TEXT NOT NULL,
  create_command    TEXT NOT NULL,
  pull_command      TEXT NOT NULL,
  is_active         INTEGER DEFAULT 0,
  user_flag_for_deletion INTEGER DEFAULT 0,
  created_at        TEXT DEFAULT (datetime('now')),
  created_by        TEXT,
  created_by_type   TEXT,
  updated_at        TEXT DEFAULT (datetime('now')),
  updated_by        TEXT,
  updated_by_type   TEXT,
  FOREIGN KEY (base_model_id) REFERENCES models(model_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_provisioned_base_role_variant
  ON provisioned_models(base_model_id, role, variant);

CREATE INDEX IF NOT EXISTS idx_provisioned_role
  ON provisioned_models(role);

-- Hardware profile (consolidated)
CREATE TABLE IF NOT EXISTS hardware_profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  yaml_content TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Software profile (consolidated)
CREATE TABLE IF NOT EXISTS software_profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  yaml_content TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_models_class ON models(class);
CREATE INDEX IF NOT EXISTS idx_models_vram ON models(vram);
CREATE INDEX IF NOT EXISTS idx_models_inventory_status ON models(inventory_status);
CREATE INDEX IF NOT EXISTS idx_role_model_role ON role_model(role);
CREATE INDEX IF NOT EXISTS idx_constraint_model_constraint ON constraint_model(constraint_name);
