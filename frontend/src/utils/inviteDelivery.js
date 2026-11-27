// Invitation email delivery chip (SB-1814). The chip itself is shared with
// Support Inbox replies and lives in emailDelivery.js (SB-1821).

import { emailDeliveryChip } from './emailDelivery';

export const inviteDeliveryChip = emailDeliveryChip;

/** A bounced address is the one thing the admin should act on. */
export const inviteDeliveryHint = invite =>
  invite?.email_status === 'bounced'
    ? 'Check the address before resending'
    : null;
