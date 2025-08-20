-- Create RLS policies for invitations table
CREATE POLICY IF NOT EXISTS allow_authenticated_insert_invitations 
ON invitations FOR INSERT 
TO authenticated 
WITH CHECK (true);

-- Allow authenticated users to read their own invitations  
CREATE POLICY IF NOT EXISTS allow_user_select_own_invitations 
ON invitations FOR SELECT 
TO authenticated 
USING (invited_by_user_id = auth.uid()::text);

-- Allow service role full access for invite service operations
CREATE POLICY IF NOT EXISTS allow_service_role_all_invitations 
ON invitations FOR ALL 
TO service_role 
USING (true) 
WITH CHECK (true);

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON invitations TO authenticated;
GRANT ALL ON invitations TO service_role;