export const PLAYER_POSITIONS = [
  { full_name: 'Goalkeeper', abbreviation: 'GK' },
  { full_name: 'Left Back', abbreviation: 'LB' },
  { full_name: 'Left Center Back', abbreviation: 'LCB' },
  { full_name: 'Right Center Back', abbreviation: 'RCB' },
  { full_name: 'Right Back', abbreviation: 'RB' },
  { full_name: 'Left Central Midfielder', abbreviation: 'LCM' },
  { full_name: 'Central Defensive Midfielder', abbreviation: 'CDM' },
  { full_name: 'Right Central Midfielder', abbreviation: 'RCM' },
  { full_name: 'Left Winger', abbreviation: 'LW' },
  { full_name: 'Striker', abbreviation: 'ST' },
  { full_name: 'Right Winger', abbreviation: 'RW' },
];

// Convenience: just abbreviations for checkboxes
export const POSITION_ABBREVIATIONS = PLAYER_POSITIONS.map(p => p.abbreviation);
