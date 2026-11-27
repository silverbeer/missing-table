// Invitation email delivery chip (SB-1814).
//
// email_status comes from Resend's delivery webhooks. null means no tracked
// email (no address, or sent before tracking existed) and renders nothing:
// "not tracked" must never read as "not delivered".

const RED = 'bg-red-100 text-red-800';

const DELIVERY_CHIPS = {
  sent: { label: 'Sending…', classes: 'bg-gray-100 text-gray-800' },
  delayed: { label: 'Delayed', classes: 'bg-amber-100 text-amber-800' },
  delivered: { label: 'Delivered', classes: 'bg-green-100 text-green-800' },
  bounced: { label: 'Bounced', classes: RED },
  failed: { label: 'Failed', classes: RED },
  suppressed: { label: 'Suppressed', classes: RED },
  complained: { label: 'Spam complaint', classes: RED },
};

/**
 * The delivery chip for an invite, or null when there is nothing to show.
 * The title carries the bounce reason when Resend gave one.
 */
export const inviteDeliveryChip = invite => {
  const chip = DELIVERY_CHIPS[invite?.email_status];
  if (!chip) return null;
  const title = invite.email_status_detail
    ? `Email ${chip.label.toLowerCase()}: ${invite.email_status_detail}`
    : `Email ${chip.label.toLowerCase()}`;
  return { ...chip, title };
};

/** A bounced address is the one thing the admin should act on. */
export const inviteDeliveryHint = invite =>
  invite?.email_status === 'bounced'
    ? 'Check the address before resending'
    : null;
