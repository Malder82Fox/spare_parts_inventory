-- Создание таблиц для слотов и монтирований
CREATE TABLE IF NOT EXISTS equipment_slots (
  id INTEGER PRIMARY KEY,
  equipment_id INTEGER NOT NULL REFERENCES equipment(id),
  role VARCHAR(64) NOT NULL,
  position VARCHAR(32) NOT NULL,
  code VARCHAR(128) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT 1,
  CONSTRAINT uq_slot_equipment_role_pos UNIQUE (equipment_id, role, position)
);

CREATE TABLE IF NOT EXISTS tooling_mounts (
  id INTEGER PRIMARY KEY,
  tool_id INTEGER NOT NULL REFERENCES tooling(id),
  slot_id INTEGER NOT NULL REFERENCES equipment_slots(id),
  started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at TIMESTAMP,
  created_by_id INTEGER NOT NULL REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_mounts_active ON tooling_mounts(slot_id, ended_at);

-- Поля в карточке инструментов (если их ещё нет)
ALTER TABLE tooling ADD COLUMN intended_role VARCHAR(64);
ALTER TABLE tooling ADD COLUMN current_diameter NUMERIC(10,3);
ALTER TABLE tooling ADD COLUMN min_diameter NUMERIC(10,3);
ALTER TABLE tooling ADD COLUMN regrind_count INTEGER DEFAULT 0;

-- Обогащение событий (если ещё нет)
ALTER TABLE tooling_events ADD COLUMN slot_id INTEGER REFERENCES equipment_slots(id);
ALTER TABLE tooling_events ADD COLUMN shift VARCHAR(16);
ALTER TABLE tooling_events ADD COLUMN dimension NUMERIC(10,3);
ALTER TABLE tooling_events ADD COLUMN new_dimension NUMERIC(10,3);
ALTER TABLE tooling_events ADD COLUMN note TEXT;
ALTER TABLE tooling_events ADD COLUMN reason VARCHAR(255);
