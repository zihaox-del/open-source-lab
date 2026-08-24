PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE content_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE champions (
    id TEXT PRIMARY KEY,
    champion_key INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    partype TEXT NOT NULL,
    tags_json TEXT NOT NULL CHECK (json_valid(tags_json)),
    stats_json TEXT NOT NULL CHECK (json_valid(stats_json))
) STRICT;

CREATE TABLE champion_abilities (
    champion_id TEXT NOT NULL REFERENCES champions(id) ON DELETE CASCADE,
    slot TEXT NOT NULL CHECK (slot IN ('P', 'Q', 'W', 'E', 'R')),
    ability_id TEXT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    tooltip TEXT NOT NULL,
    cooldown_json TEXT NOT NULL CHECK (json_valid(cooldown_json)),
    cost_json TEXT NOT NULL CHECK (json_valid(cost_json)),
    PRIMARY KEY (champion_id, slot)
) STRICT;

CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    name_raw TEXT NOT NULL,
    description TEXT NOT NULL,
    description_raw TEXT NOT NULL,
    purchasable INTEGER NOT NULL CHECK (purchasable IN (0, 1)),
    in_store INTEGER NOT NULL CHECK (in_store IN (0, 1)),
    gold_json TEXT NOT NULL CHECK (json_valid(gold_json)),
    tags_json TEXT NOT NULL CHECK (json_valid(tags_json)),
    stats_json TEXT NOT NULL CHECK (json_valid(stats_json)),
    from_json TEXT NOT NULL CHECK (json_valid(from_json)),
    into_json TEXT NOT NULL CHECK (json_valid(into_json)),
    image TEXT NOT NULL
) STRICT;

CREATE TABLE augments (
    id INTEGER PRIMARY KEY,
    api_name TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    rarity INTEGER NOT NULL,
    description TEXT NOT NULL,
    description_raw TEXT NOT NULL,
    tooltip TEXT NOT NULL,
    tooltip_raw TEXT NOT NULL,
    icon_small TEXT NOT NULL,
    icon_large TEXT NOT NULL,
    data_values_json TEXT NOT NULL CHECK (json_valid(data_values_json)),
    calculations_json TEXT NOT NULL CHECK (json_valid(calculations_json))
) STRICT;

CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    category TEXT NOT NULL
) STRICT;

CREATE TABLE entity_tags (
    entity_type TEXT NOT NULL CHECK (entity_type IN ('champion', 'item', 'augment')),
    entity_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    weight INTEGER NOT NULL DEFAULT 1,
    reason TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (entity_type, entity_id, tag_id)
) STRICT;

CREATE TABLE synergy_rules (
    id TEXT PRIMARY KEY,
    game_patch TEXT NOT NULL,
    subject_type TEXT NOT NULL CHECK (subject_type IN ('champion', 'item', 'augment', 'tag')),
    subject_id TEXT NOT NULL,
    object_type TEXT NOT NULL CHECK (object_type IN ('champion', 'item', 'augment', 'tag')),
    object_id TEXT NOT NULL,
    weight INTEGER NOT NULL,
    reason TEXT NOT NULL,
    evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json)),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
) STRICT;

CREATE INDEX idx_champions_name ON champions(name);
CREATE INDEX idx_items_name ON items(name);
CREATE INDEX idx_items_purchasable ON items(purchasable, name);
CREATE INDEX idx_augments_name ON augments(name);
CREATE INDEX idx_augments_rarity ON augments(rarity, name);
CREATE INDEX idx_entity_tags_lookup ON entity_tags(entity_type, entity_id);
CREATE INDEX idx_synergy_subject ON synergy_rules(subject_type, subject_id, enabled);
CREATE INDEX idx_synergy_object ON synergy_rules(object_type, object_id, enabled);

