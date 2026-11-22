// Stage sections of the tournament match list (SB-1749).
//
// MLS NEXT Fest has rounds that are neither a group stage nor an elimination
// tree: showcase, placement finals and consolation. Each renders as its own
// section rather than falling into the catch-all "Matches" bucket.
//
// For these rounds `tournament_group` carries a stage label rather than a
// group ("HD · Showcase", "HD · Group Play", "GA Cup Qualifier"), and one
// round can hold several of them, so a section is one (round, stage label)
// pair and is titled with the label.

// In playing order within a list. `title` is the section heading when the
// matches carry no stage label.
export const STAGE_ROUND_SECTIONS = [
  { round: 'showcase', title: 'Showcase' },
  { round: 'placement_final', title: 'Placement Finals' },
  { round: 'consolation', title: 'Consolation' },
];

export const STAGE_ROUNDS = new Set(STAGE_ROUND_SECTIONS.map(s => s.round));

/**
 * Heading for one stage section. A label that already names the round stands
 * alone ("HD · Showcase"); otherwise the round leads so two rounds sharing a
 * label stay distinguishable ("Placement Finals — HD · Group Play" vs
 * "Consolation — HD · Group Play").
 */
export function stageSectionTitle(roundTitle, stageLabel) {
  const label = (stageLabel ?? '').trim();
  if (!label) return roundTitle;
  if (label.toLowerCase().includes(roundTitle.toLowerCase())) return label;
  return `${roundTitle} — ${label}`;
}

/**
 * Split matches of one stage round into sections, one per stage label, in
 * label order with unlabelled matches last. Returns [] when the round has no
 * matches. Match order within a section is the order given.
 */
export function buildStageSections(matches, { round, title }) {
  const byLabel = new Map();
  for (const m of matches || []) {
    if (m.tournament_round !== round) continue;
    const label = (m.tournament_group ?? '').trim();
    if (!byLabel.has(label)) byLabel.set(label, []);
    byLabel.get(label).push(m);
  }
  return [...byLabel.keys()]
    .sort((a, b) => {
      if (!a || !b) return a ? -1 : b ? 1 : 0;
      return a.localeCompare(b);
    })
    .map(label => ({
      key: `${round}:${label}`,
      title: stageSectionTitle(title, label),
      matches: byLabel.get(label),
    }));
}
