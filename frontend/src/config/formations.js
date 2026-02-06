/**
 * Formation Templates for Soccer (11v11) and Futsal (5v5)
 *
 * Each formation defines position names and their coordinates on a field.
 * Coordinates are percentages (0-100) where:
 * - x: 0 = left, 100 = right
 * - y: 0 = attacking end (top), 100 = defensive end (bottom/goalkeeper)
 */

export const FORMATIONS = {
  '4-3-3': {
    name: '4-3-3',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LB', x: 15, y: 70 },
      { position: 'LCB', x: 35, y: 75 },
      { position: 'RCB', x: 65, y: 75 },
      { position: 'RB', x: 85, y: 70 },
      { position: 'LCM', x: 30, y: 50 },
      { position: 'CDM', x: 50, y: 55 },
      { position: 'RCM', x: 70, y: 50 },
      { position: 'LW', x: 20, y: 25 },
      { position: 'ST', x: 50, y: 20 },
      { position: 'RW', x: 80, y: 25 },
    ],
  },
  '4-4-2': {
    name: '4-4-2',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LB', x: 15, y: 70 },
      { position: 'LCB', x: 35, y: 75 },
      { position: 'RCB', x: 65, y: 75 },
      { position: 'RB', x: 85, y: 70 },
      { position: 'LM', x: 15, y: 50 },
      { position: 'LCM', x: 38, y: 50 },
      { position: 'RCM', x: 62, y: 50 },
      { position: 'RM', x: 85, y: 50 },
      { position: 'LST', x: 38, y: 22 },
      { position: 'RST', x: 62, y: 22 },
    ],
  },
  '3-5-2': {
    name: '3-5-2',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LCB', x: 25, y: 75 },
      { position: 'CB', x: 50, y: 78 },
      { position: 'RCB', x: 75, y: 75 },
      { position: 'LWB', x: 10, y: 55 },
      { position: 'LCM', x: 30, y: 50 },
      { position: 'CDM', x: 50, y: 55 },
      { position: 'RCM', x: 70, y: 50 },
      { position: 'RWB', x: 90, y: 55 },
      { position: 'LST', x: 38, y: 22 },
      { position: 'RST', x: 62, y: 22 },
    ],
  },
  '4-2-3-1': {
    name: '4-2-3-1',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LB', x: 15, y: 70 },
      { position: 'LCB', x: 35, y: 75 },
      { position: 'RCB', x: 65, y: 75 },
      { position: 'RB', x: 85, y: 70 },
      { position: 'LCDM', x: 38, y: 58 },
      { position: 'RCDM', x: 62, y: 58 },
      { position: 'LW', x: 20, y: 38 },
      { position: 'CAM', x: 50, y: 35 },
      { position: 'RW', x: 80, y: 38 },
      { position: 'ST', x: 50, y: 18 },
    ],
  },
  '4-1-4-1': {
    name: '4-1-4-1',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LB', x: 15, y: 70 },
      { position: 'LCB', x: 35, y: 75 },
      { position: 'RCB', x: 65, y: 75 },
      { position: 'RB', x: 85, y: 70 },
      { position: 'CDM', x: 50, y: 60 },
      { position: 'LM', x: 15, y: 42 },
      { position: 'LCM', x: 38, y: 42 },
      { position: 'RCM', x: 62, y: 42 },
      { position: 'RM', x: 85, y: 42 },
      { position: 'ST', x: 50, y: 18 },
    ],
  },
  '5-3-2': {
    name: '5-3-2',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LWB', x: 10, y: 65 },
      { position: 'LCB', x: 30, y: 75 },
      { position: 'CB', x: 50, y: 78 },
      { position: 'RCB', x: 70, y: 75 },
      { position: 'RWB', x: 90, y: 65 },
      { position: 'LCM', x: 30, y: 48 },
      { position: 'CM', x: 50, y: 52 },
      { position: 'RCM', x: 70, y: 48 },
      { position: 'LST', x: 38, y: 22 },
      { position: 'RST', x: 62, y: 22 },
    ],
  },
  '3-4-3': {
    name: '3-4-3',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LCB', x: 25, y: 75 },
      { position: 'CB', x: 50, y: 78 },
      { position: 'RCB', x: 75, y: 75 },
      { position: 'LM', x: 15, y: 50 },
      { position: 'LCM', x: 38, y: 52 },
      { position: 'RCM', x: 62, y: 52 },
      { position: 'RM', x: 85, y: 50 },
      { position: 'LW', x: 20, y: 25 },
      { position: 'ST', x: 50, y: 20 },
      { position: 'RW', x: 80, y: 25 },
    ],
  },
};

export const FUTSAL_FORMATIONS = {
  '1-2-2': {
    name: '1-2-2',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LD', x: 30, y: 65 },
      { position: 'RD', x: 70, y: 65 },
      { position: 'LF', x: 30, y: 35 },
      { position: 'RF', x: 70, y: 35 },
    ],
  },
  '2-2': {
    name: '2-2',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LD', x: 25, y: 65 },
      { position: 'RD', x: 75, y: 65 },
      { position: 'LF', x: 25, y: 30 },
      { position: 'RF', x: 75, y: 30 },
    ],
  },
  '1-2-1': {
    name: '1-2-1 (Diamond)',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'FIX', x: 50, y: 68 },
      { position: 'LW', x: 22, y: 48 },
      { position: 'RW', x: 78, y: 48 },
      { position: 'PIV', x: 50, y: 25 },
    ],
  },
  '3-1': {
    name: '3-1',
    positions: [
      { position: 'GK', x: 50, y: 90 },
      { position: 'LD', x: 25, y: 65 },
      { position: 'CD', x: 50, y: 68 },
      { position: 'RD', x: 75, y: 65 },
      { position: 'PIV', x: 50, y: 30 },
    ],
  },
};

export const DEFAULT_FORMATION = '4-3-3';
export const DEFAULT_FUTSAL_FORMATION = '1-2-2';

/**
 * Get the formations object for a given sport type.
 */
export function getFormations(sportType = 'soccer') {
  return sportType === 'futsal' ? FUTSAL_FORMATIONS : FORMATIONS;
}

/**
 * Get the default formation for a given sport type.
 */
export function getDefaultFormation(sportType = 'soccer') {
  return sportType === 'futsal' ? DEFAULT_FUTSAL_FORMATION : DEFAULT_FORMATION;
}

/**
 * Get formation options for dropdown selects.
 */
export function getFormationOptions(sportType = 'soccer') {
  const formations = getFormations(sportType);
  return Object.keys(formations).map(key => ({
    value: key,
    label: formations[key].name,
  }));
}
