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

const POSITION_NAMES = {
  GK: 'Goalkeeper',
  CB: 'Center Back',
  LB: 'Left Back',
  RB: 'Right Back',
  LWB: 'Left Wing Back',
  RWB: 'Right Wing Back',
  CDM: 'Defensive Midfielder',
  CM: 'Central Midfielder',
  CAM: 'Attacking Midfielder',
  LM: 'Left Midfielder',
  RM: 'Right Midfielder',
  LW: 'Left Winger',
  RW: 'Right Winger',
  ST: 'Striker',
  CF: 'Center Forward',
};

// Flat list of { code, name, group } in group order.
export const PLAYER_POSITIONS = Object.entries(POSITION_GROUPS).flatMap(
  ([group, codes]) =>
    codes.map(code => ({ code, name: POSITION_NAMES[code], group }))
);

// Convenience: just codes (legacy export name kept for compatibility).
export const POSITION_ABBREVIATIONS = PLAYER_POSITIONS.map(p => p.code);

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

/** Broad group (GK/DEF/MID/FWD) for a specific position code, or null. */
export function groupForPosition(code) {
  const canonical = LEGACY_POSITION_MAP[code] || code;
  return CODE_TO_GROUP[canonical] || null;
}

/** Primary position = first entry of the ordered positions array. */
export function primaryPosition(positions) {
  return positions && positions.length > 0 ? positions[0] : null;
}

// Formation SLOT code -> group. Formation slots keep side-specific codes
// (LCB, RST, ...); this maps every slot code in config/formations.js
// (soccer + futsal) to the group used for player filtering.
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
