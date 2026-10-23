-- SB-1407: repair invite requests approved under the old flow.
--
-- Before SB-1392, Approve only flipped the status, so some requests are
-- 'approved' with no invitation_id. The rule is now that an approved request
-- always has one. For each such row, in order:
--
--   1. An invitation exists for the same email -> link the newest one.
--      (The admin created it by hand from the Invites tab.)
--   2. Otherwise, another pending request has the same email -> the requester
--      asked again; delete this stale duplicate and keep the pending one.
--   3. Otherwise -> reset to pending so the admin can Approve it properly.
--
-- Data only, sends no email, and is a no-op once every approved row is linked.

-- 1. Link hand-made invitations.
UPDATE public.invite_requests r
SET invitation_id = (
    SELECT i.id
    FROM public.invitations i
    WHERE lower(i.email) = lower(r.email)
    ORDER BY i.created_at DESC
    LIMIT 1
)
WHERE r.status = 'approved'
  AND r.invitation_id IS NULL
  AND EXISTS (
      SELECT 1 FROM public.invitations i WHERE lower(i.email) = lower(r.email)
  );

-- 2. Drop approved-without-invite rows superseded by a newer pending request.
DELETE FROM public.invite_requests r
WHERE r.status = 'approved'
  AND r.invitation_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM public.invite_requests p
      WHERE p.status = 'pending'
        AND p.id <> r.id
        AND lower(p.email) = lower(r.email)
  );

-- 3. Everything left was never answered: back to pending, review cleared.
UPDATE public.invite_requests
SET status = 'pending',
    reviewed_by = NULL,
    reviewed_at = NULL
WHERE status = 'approved'
  AND invitation_id IS NULL;
