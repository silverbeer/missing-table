-- No-op: bracket_tier is already a free-form VARCHAR(50) column.
-- This migration previously dropped a CHECK constraint that no longer exists.
-- Kept for migration history compatibility.
SELECT 1;
