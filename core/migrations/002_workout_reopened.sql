-- A finished workout reopened for editing keeps the ended_at it had, so an
-- edit is distinguishable from a new in-progress workout (and never stale).
-- NULL for every workout not currently reopened; finish clears it.

ALTER TABLE workout ADD COLUMN reopened_from TEXT;
