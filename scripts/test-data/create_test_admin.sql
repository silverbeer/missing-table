-- Create test data for local development
-- Insert test age groups
INSERT INTO age_groups (id, name) VALUES 
(1, 'U12'),
(2, 'U14') 
ON CONFLICT (id) DO NOTHING;

-- Insert test teams  
INSERT INTO teams (id, name) VALUES
(1, 'Test Team Alpha'),
(2, 'Test Team Beta')
ON CONFLICT (id) DO NOTHING;

-- Insert test admin user (you'll need to sign up first to get the real UUID)
-- This is just a placeholder - replace with your actual user ID after signing up
-- INSERT INTO user_profiles (id, role, display_name) VALUES 
-- ('YOUR_ACTUAL_USER_ID_HERE', 'admin', 'Test Admin');