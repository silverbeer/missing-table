-- Add authentication and user role management
-- This migration adds user profiles and role-based access control

-- User Profiles Table
CREATE TABLE user_profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('admin', 'team-manager', 'team-fan', 'team-player')),
    team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS on user_profiles
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- User Profiles Policies
CREATE POLICY "Users can view own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON user_profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Admins can view all profiles" ON user_profiles
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

CREATE POLICY "Admins can manage all profiles" ON user_profiles
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

-- Enable RLS on existing tables
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE age_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE divisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_mappings ENABLE ROW LEVEL SECURITY;

-- Teams Policies
CREATE POLICY "Everyone can view teams" ON teams
    FOR SELECT USING (true);

CREATE POLICY "Admins can manage teams" ON teams
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

CREATE POLICY "Team managers can update their team" ON teams
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() 
            AND role = 'team-manager' 
            AND team_id = teams.id
        )
    );

-- Games Policies
CREATE POLICY "Everyone can view games" ON games
    FOR SELECT USING (true);

CREATE POLICY "Admins can manage all games" ON games
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

CREATE POLICY "Team managers can add games for their team" ON games
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() 
            AND role = 'team-manager' 
            AND (team_id = games.home_team_id OR team_id = games.away_team_id)
        )
    );

CREATE POLICY "Team managers can edit games for their team" ON games
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() 
            AND role = 'team-manager' 
            AND (team_id = games.home_team_id OR team_id = games.away_team_id)
        )
    );

-- Reference tables (seasons, age_groups, game_types, divisions) - read-only for most users
CREATE POLICY "Everyone can view seasons" ON seasons FOR SELECT USING (true);
CREATE POLICY "Admins can manage seasons" ON seasons FOR ALL USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
);

CREATE POLICY "Everyone can view age_groups" ON age_groups FOR SELECT USING (true);
CREATE POLICY "Admins can manage age_groups" ON age_groups FOR ALL USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
);

CREATE POLICY "Everyone can view game_types" ON game_types FOR SELECT USING (true);
CREATE POLICY "Admins can manage game_types" ON game_types FOR ALL USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
);

CREATE POLICY "Everyone can view divisions" ON divisions FOR SELECT USING (true);
CREATE POLICY "Admins can manage divisions" ON divisions FOR ALL USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
);

-- Team mappings policies
CREATE POLICY "Everyone can view team_mappings" ON team_mappings FOR SELECT USING (true);
CREATE POLICY "Admins can manage team_mappings" ON team_mappings FOR ALL USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
);

-- Function to automatically create user profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, role, display_name)
    VALUES (
        NEW.id, 
        'team-fan', -- Default role
        COALESCE(NEW.raw_user_meta_data->>'display_name', NEW.email)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create profile on user signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Function to get current user's role
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT AS $$
BEGIN
    RETURN (
        SELECT role FROM user_profiles 
        WHERE id = auth.uid()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user has role
CREATE OR REPLACE FUNCTION public.user_has_role(required_role TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM user_profiles 
        WHERE id = auth.uid() AND role = required_role
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create admin user function (for initial setup)
CREATE OR REPLACE FUNCTION public.promote_to_admin(user_email TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    user_id UUID;
BEGIN
    -- Get user ID from email
    SELECT id INTO user_id 
    FROM auth.users 
    WHERE email = user_email;
    
    IF user_id IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Update role to admin
    UPDATE user_profiles 
    SET role = 'admin', updated_at = NOW()
    WHERE id = user_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;