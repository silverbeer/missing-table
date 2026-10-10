// Invite request -> invitation (SB-1312).

const INVITE_TYPE_LABELS = {
  club_manager: 'Club Manager',
  club_fan: 'Club Fan',
  team_manager: 'Team Manager',
  team_player: 'Team Player',
  team_fan: 'Team Fan',
};

/**
 * What AdminInvites needs to open its form pre-filled from a request.
 * The invite form has no name field, so the name goes in the note.
 * Invite type and club/team are left for the admin to pick.
 */
export const invitePrefillFromRequest = request => ({
  request: { id: request.id, name: request.name, email: request.email },
  form: {
    email: request.email || '',
    note: request.name || '',
    iosBeta: Boolean(request.wants_ios_beta),
  },
});

/** One-line summary of the invitation linked to a request. */
export const linkedInviteSummary = invitation =>
  [
    invitation.invite_code,
    INVITE_TYPE_LABELS[invitation.invite_type] || invitation.invite_type,
    invitation.status,
  ].join(' · ');
