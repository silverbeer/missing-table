-- Migration: Add invite-only system to Missing Table
-- Description: Implements invite codes, team manager assignments, and user scoping

-- Create invitations table
CREATE TABLE IF NOT EXISTS public.invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invite_code VARCHAR(12) UNIQUE NOT NULL,
    invited_by_user_id UUID REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    invite_type VARCHAR(20) NOT NULL CHECK (invite_type IN ('team_manager', 'team_player', 'team_fan')),
    team_id INTEGER REFERENCES public.teams(id) ON DELETE CASCADE,
    age_group_id INTEGER REFERENCES public.age_groups(id) ON DELETE CASCADE,
    email VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'used', 'expired')),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '7 days'),
    used_at TIMESTAMP WITH TIME ZONE,
    used_by_user_id UUID REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create team manager assignments table
CREATE TABLE IF NOT EXISTS public.team_manager_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES public.teams(id) ON DELETE CASCADE,
    age_group_id INTEGER REFERENCES public.age_groups(id) ON DELETE CASCADE,
    assigned_by_user_id UUID REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, team_id, age_group_id)
);

-- Add columns to user_profiles for age group scoping and invite tracking
-- Note: team_id column already exists, so we'll use that instead of assigned_team_id
ALTER TABLE public.user_profiles 
ADD COLUMN IF NOT EXISTS assigned_age_group_id INTEGER REFERENCES public.age_groups(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS invited_via_code VARCHAR(12) REFERENCES public.invitations(invite_code) ON DELETE SET NULL;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_invitations_code ON public.invitations(invite_code);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON public.invitations(status);
CREATE INDEX IF NOT EXISTS idx_invitations_expires_at ON public.invitations(expires_at);
CREATE INDEX IF NOT EXISTS idx_invitations_invited_by ON public.invitations(invited_by_user_id);
CREATE INDEX IF NOT EXISTS idx_team_manager_assignments_user ON public.team_manager_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_team_manager_assignments_team_age ON public.team_manager_assignments(team_id, age_group_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_team_age ON public.user_profiles(team_id, assigned_age_group_id);

-- Enable Row Level Security
ALTER TABLE public.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.team_manager_assignments ENABLE ROW LEVEL SECURITY;

-- RLS Policies for invitations table
-- Anyone can validate an invite code (for registration)
CREATE POLICY "Anyone can validate invite codes" ON public.invitations
    FOR SELECT USING (true);

-- Admins can do everything
CREATE POLICY "Admins can manage all invitations" ON public.invitations
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE user_profiles.id = auth.uid()
            AND user_profiles.role = 'admin'
        )
    );

-- Team managers can create invites for their assigned teams
CREATE POLICY "Team managers can create team invites" ON public.invitations
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.team_manager_assignments tma
            JOIN public.user_profiles up ON up.id = auth.uid()
            WHERE tma.user_id = auth.uid()
            AND tma.team_id = invitations.team_id
            AND tma.age_group_id = invitations.age_group_id
            AND invitations.invite_type IN ('team_player', 'team_fan')
        )
    );

-- Team managers can view their own invites
CREATE POLICY "Team managers can view their invites" ON public.invitations
    FOR SELECT USING (
        invited_by_user_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE user_profiles.id = auth.uid()
            AND user_profiles.role = 'team_manager'
        )
    );

-- RLS Policies for team_manager_assignments table
-- Admins can manage all assignments
CREATE POLICY "Admins can manage team manager assignments" ON public.team_manager_assignments
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE user_profiles.id = auth.uid()
            AND user_profiles.role = 'admin'
        )
    );

-- Team managers can view their own assignments
CREATE POLICY "Team managers can view their assignments" ON public.team_manager_assignments
    FOR SELECT USING (user_id = auth.uid());

-- Update function for updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for invitations updated_at
CREATE TRIGGER update_invitations_updated_at 
    BEFORE UPDATE ON public.invitations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to generate unique invite codes
CREATE OR REPLACE FUNCTION generate_invite_code()
RETURNS VARCHAR(12) AS $$
DECLARE
    chars TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    result VARCHAR(12) := '';
    i INTEGER;
    max_attempts INTEGER := 100;
    attempt INTEGER := 0;
BEGIN
    -- Try to generate a unique code
    WHILE attempt < max_attempts LOOP
        result := '';
        -- Generate 12 character code
        FOR i IN 1..12 LOOP
            result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
        END LOOP;
        
        -- Check if code already exists
        IF NOT EXISTS (SELECT 1 FROM public.invitations WHERE invite_code = result) THEN
            RETURN result;
        END IF;
        
        attempt := attempt + 1;
    END LOOP;
    
    -- If we couldn't generate a unique code, raise an error
    RAISE EXCEPTION 'Could not generate unique invite code after % attempts', max_attempts;
END;
$$ LANGUAGE plpgsql;

-- Function to expire old invitations (can be run periodically)
CREATE OR REPLACE FUNCTION expire_old_invitations()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE public.invitations
    SET status = 'expired'
    WHERE status = 'pending'
    AND expires_at < NOW();
    
    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

-- Add comment explaining the invite system
COMMENT ON TABLE public.invitations IS 'Stores invite codes for the invite-only registration system';
COMMENT ON TABLE public.team_manager_assignments IS 'Maps team managers to their assigned teams and age groups';
COMMENT ON COLUMN public.user_profiles.team_id IS 'For non-admin users, the team they are assigned to';
COMMENT ON COLUMN public.user_profiles.assigned_age_group_id IS 'For non-admin users, the age group they are assigned to';
COMMENT ON COLUMN public.user_profiles.invited_via_code IS 'The invite code used to register this user';