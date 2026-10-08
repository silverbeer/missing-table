-- The iOS app's bundle ID changed from io.silverbeer.mt to com.missingtable
-- (the App ID registered in the Apple Developer portal). The app does not send
-- bundle_id when it registers, so the column default is the apns-topic used for
-- every device; a stale default makes APNs reject sends with DeviceTokenNotForTopic.

ALTER TABLE public.apns_devices
    ALTER COLUMN bundle_id SET DEFAULT 'com.missingtable';

UPDATE public.apns_devices
SET bundle_id = 'com.missingtable'
WHERE bundle_id = 'io.silverbeer.mt';
