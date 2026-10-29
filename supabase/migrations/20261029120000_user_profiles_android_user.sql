-- SB-1460: an admin marks which users get the Android app.
--
-- The web footer's "Install the Android app" link showed to anyone logged in
-- on an Android browser. The app is going to team parents one family at a
-- time, so who gets it is an admin's decision, not the browser's: the link
-- now shows to admins and to accounts with this flag set, on any browser.
--
-- false for everyone who exists today: nobody has been given the app this
-- way yet.
ALTER TABLE public.user_profiles
    ADD COLUMN IF NOT EXISTS android_user boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.user_profiles.android_user IS
    'Admin-set: this user gets the Android app download link on the web (SB-1460).';
