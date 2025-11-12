-- Division Mismatch Fix SQL
-- Generated for environment: dev
-- Total mismatches: 57

-- IMPORTANT: Backup first!
-- CREATE TABLE matches_backup AS SELECT * FROM matches;

-- Northeast (1) → New England (7)
UPDATE matches
SET division_id = 7
WHERE id IN (654, 655, 658, 659, 661, 662, 663, 665, 668, 669, 670, 674, 679, 675, 677, 672, 680, 683, 684, 686, 688, 689, 690, 693, 695, 697, 698, 699, 701, 702, 703, 704, 705, 707, 708, 709, 712, 713, 714, 716, 717, 718, 721, 723, 724, 726, 728);

-- Unknown (None) → Northeast (1)
UPDATE matches
SET division_id = 1
WHERE id IN (425, 485, 426, 427, 428, 429, 430, 482, 481, 483);


-- Total matches updated: 57
