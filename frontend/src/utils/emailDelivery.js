// Email delivery chip: invitations (SB-1814) and Support Inbox replies (SB-1821).
//
// email_status comes from Resend's delivery webhooks. null means no tracked
// email (no address, an inbound message, or sent before tracking existed) and
// renders nothing: "not tracked" must never read as "not delivered".
//
// The chip colours are fixed (not theme tokens), so the dark-on-light pairs
// stay readable on dark backgrounds too.

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
 * The delivery chip for a row carrying email_status (an invite, or an
 * outbound message), or null when there is nothing to show. The title
 * carries the bounce reason when Resend gave one.
 */
export const emailDeliveryChip = row => {
  const chip = DELIVERY_CHIPS[row?.email_status];
  if (!chip) return null;
  const title = row.email_status_detail
    ? `Email ${chip.label.toLowerCase()}: ${row.email_status_detail}`
    : `Email ${chip.label.toLowerCase()}`;
  return { ...chip, title };
};
