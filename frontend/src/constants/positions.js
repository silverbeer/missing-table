// Player position taxonomy.
//
// A player's positions are an ORDERED array of specific codes; the first
// entry is their primary position. Each specific code belongs to exactly one
// broad group (GK/DEF/MID/FWD), used for lineup-slot filtering.
//
// KEEP IN SYNC with backend/constants/positions.py (guarded by a backend
// parity test that parses this file).

export const POSITION_GROUPS = {
  GK: ['GK'],
  DEF: ['CB', 'LB', 'RB', 'LWB', 'RWB'],
  MID: ['CDM', 'CM', 'CAM', 'LM', 'RM'],
  FWD: ['LW', 'RW', 'ST', 'CF'],
};

export const GROUP_NAMES = {
  GK: 'Goalkeeper',
  DEF: 'Defender',
  MID: 'Midfielder',
  FWD: 'Forward',
};

// Old side-specific codes that may still exist in cached/stale data.
export const LEGACY_POSITION_MAP = {
  LCB: 'CB',
  RCB: 'CB',
  LCM: 'CM',
  RCM: 'CM',
};

const CODE_TO_GROUP = Object.fromEntries(
  Object.entries(POSITION_GROUPS).flatMap(([group, codes]) =>
    codes.map(code => [code, group])
  )
);

/**
 * Broad group (GK/DEF/MID/FWD) for a specific position code, or null.
 * Consumer: lineup-slot filtering (SB-288).
 */
export function groupForPosition(code) {
  const canonical = LEGACY_POSITION_MAP[code] || code;
  return CODE_TO_GROUP[canonical] || null;
}

/** Primary position = first entry of the ordered positions array. */
export function primaryPosition(positions) {
  return positions && positions.length > 0 ? positions[0] : null;
}

/**
 * Parse a positions value into a clean ordered array of canonical codes.
 * Handles the three shapes that reach the frontend: a real array
 * (players.positions text[]), a JSON string (user_profiles.positions TEXT),
 * and null/undefined. Legacy codes (LCB/RCB/LCM/RCM) are remapped and
 * duplicates dropped (first occurrence wins).
 */
export function parsePositions(positions) {
  let list = positions;
  if (!list) return [];
  if (typeof list === 'string') {
    try {
      list = JSON.parse(list);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(list)) return [];
  const seen = new Set();
  const result = [];
  for (const raw of list) {
    const code = LEGACY_POSITION_MAP[raw] || raw;
    if (!seen.has(code)) {
      seen.add(code);
      result.push(code);
    }
  }
  return result;
}

// Formation SLOT code -> group. Formation slots keep side-specific codes
// (LCB, RST, ...); this maps every slot code in config/formations.js
// (soccer + futsal) to the group used for player filtering.
// Consumer: lineup-slot filtering (SB-288); coverage pinned by the backend
// parity test.
export const SLOT_TO_GROUP = {
  // goalkeeper
  GK: 'GK',
  // defense (soccer)
  CB: 'DEF',
  LCB: 'DEF',
  RCB: 'DEF',
  LB: 'DEF',
  RB: 'DEF',
  LWB: 'DEF',
  RWB: 'DEF',
  // defense (futsal)
  CD: 'DEF',
  LD: 'DEF',
  RD: 'DEF',
  FIX: 'DEF',
  // midfield
  CDM: 'MID',
  LCDM: 'MID',
  RCDM: 'MID',
  CM: 'MID',
  LCM: 'MID',
  RCM: 'MID',
  CAM: 'MID',
  LM: 'MID',
  RM: 'MID',
  // attack (soccer)
  LW: 'FWD',
  RW: 'FWD',
  ST: 'FWD',
  LST: 'FWD',
  RST: 'FWD',
  // attack (futsal)
  PIV: 'FWD',
  LF: 'FWD',
  RF: 'FWD',
};
