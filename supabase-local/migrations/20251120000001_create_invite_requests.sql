-- Migration: Create invite_requests table
-- Purpose: Store invite requests from potential users

-- Create enum for invite request status
DO $$ BEGIN
    CREATE TYPE invite_request_status AS ENUM ('pending', 'approved', 'rejected');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create invite_requests table
CREATE TABLE IF NOT EXISTS invite_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    team VARCHAR(255),
    reason TEXT,
    status invite_request_status DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    reviewed_by UUID REFERENCES auth.users(id),
    reviewed_at TIMESTAMPTZ,
    admin_notes TEXT
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_invite_requests_email ON invite_requests(email);
CREATE INDEX IF NOT EXISTS idx_invite_requests_status ON invite_requests(status);
CREATE INDEX IF NOT EXISTS idx_invite_requests_created_at ON invite_requests(created_at DESC);

-- Enable RLS
ALTER TABLE invite_requests ENABLE ROW LEVEL SECURITY;

-- Policy: Anyone can insert (public endpoint for submissions)
CREATE POLICY "Anyone can submit invite requests"
    ON invite_requests
    FOR INSERT
    WITH CHECK (true);

-- Policy: Only admins can view invite requests
CREATE POLICY "Admins can view all invite requests"
    ON invite_requests
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE user_profiles.id = auth.uid()
            AND user_profiles.role = 'admin'
        )
    );

-- Policy: Only admins can update invite requests
CREATE POLICY "Admins can update invite requests"
    ON invite_requests
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE user_profiles.id = auth.uid()
            AND user_profiles.role = 'admin'
        )
    );

-- Create trigger to update updated_at
CREATE OR REPLACE FUNCTION update_invite_requests_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_invite_requests_updated_at
    BEFORE UPDATE ON invite_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_invite_requests_updated_at();

-- Add schema version
SELECT add_schema_version('1.2.0', 'create_invite_requests', 'Add invite_requests table for managing user invite requests');

COMMENT ON TABLE invite_requests IS 'Stores invite requests from potential users wanting to join the platform';
COMMENT ON COLUMN invite_requests.status IS 'Request status: pending, approved, or rejected';
COMMENT ON COLUMN invite_requests.reviewed_by IS 'Admin user who reviewed the request';
COMMENT ON COLUMN invite_requests.admin_notes IS 'Internal notes from admin about the request';
