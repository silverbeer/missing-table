#!/usr/bin/env python3
"""
Create admin invite for tdrake13@gmail.com
This script creates an invite directly in the database bypassing RLS
"""

import os
import psycopg2
from datetime import datetime, timedelta
import secrets

def create_admin_invite():
    """Create admin invite directly via PostgreSQL connection"""
    
    # Generate invite code
    code_chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    invite_code = ''.join(secrets.choice(code_chars) for _ in range(12))
    
    # Database connection details (from Supabase local)
    conn_params = {
        'host': 'localhost',
        'port': 54322,
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }
    
    try:
        # Connect to PostgreSQL directly
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Insert admin invite
        sql = """
        INSERT INTO public.invitations (
            invite_code, 
            invite_type, 
            team_id, 
            age_group_id, 
            email, 
            status,
            expires_at,
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING invite_code, email;
        """
        
        # Calculate expiration (30 days from now)
        expires_at = datetime.now() + timedelta(days=30)
        created_at = datetime.now()
        
        cursor.execute(sql, (
            invite_code,
            'team_manager',
            1,  # First team
            1,  # First age group  
            'tdrake13@gmail.com',
            'pending',
            expires_at,
            created_at
        ))
        
        result = cursor.fetchone()
        conn.commit()
        
        print("✅ Admin invite created successfully!")
        print(f"📧 Email: {result[1]}")
        print(f"🔑 Invite Code: {result[0]}")
        print(f"📅 Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Registration URL: http://localhost:8080?code={result[0]}")
        print()
        print("⚠️  Important:")
        print("   1. Use this code to register at the URL above")
        print("   2. After registration, the user will have 'manager' role")
        print("   3. Manually change role to 'admin' in user_profiles table")
        
        cursor.close()
        conn.close()
        
        return result[0]
        
    except Exception as e:
        print(f"❌ Error creating admin invite: {e}")
        return None

if __name__ == "__main__":
    create_admin_invite()