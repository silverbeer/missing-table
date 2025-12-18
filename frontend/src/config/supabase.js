// Supabase Client Configuration
// Used ONLY for OAuth flows - regular API calls go through the backend

import { createClient } from '@supabase/supabase-js';

const getSupabaseConfig = () => {
  // Runtime detection for Supabase URL
  if (typeof window !== 'undefined') {
    const { hostname } = window.location;

    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return {
        url: 'http://localhost:54321',
        // Local Supabase demo anon key (not a secret - same for all local instances)
        anonKey:
          'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0', // pragma: allowlist secret
      };
    }

    // Cloud environments - use environment variables set at build time
    // Check both VITE_ (Vite standard) and VUE_APP_ (legacy) prefixes
    return {
      url:
        import.meta.env.VITE_SUPABASE_URL ||
        import.meta.env.VUE_APP_SUPABASE_URL,
      anonKey:
        import.meta.env.VITE_SUPABASE_ANON_KEY ||
        import.meta.env.VUE_APP_SUPABASE_ANON_KEY,
    };
  }

  // Fallback for SSR/build time
  return {
    url:
      import.meta.env.VITE_SUPABASE_URL ||
      import.meta.env.VUE_APP_SUPABASE_URL ||
      'http://localhost:54321',
    anonKey:
      import.meta.env.VITE_SUPABASE_ANON_KEY ||
      import.meta.env.VUE_APP_SUPABASE_ANON_KEY ||
      '',
  };
};

const config = getSupabaseConfig();

// Create Supabase client for OAuth only
// This client is NOT used for data operations - those go through the backend API
export const supabase = createClient(config.url, config.anonKey, {
  auth: {
    autoRefreshToken: false, // Backend handles token refresh
    persistSession: false, // We manage our own session storage
    detectSessionInUrl: true, // Required for OAuth callback handling
  },
});

// Get the OAuth callback URL based on current environment
export const getOAuthRedirectUrl = () => {
  if (typeof window !== 'undefined') {
    const { protocol, hostname, port } = window.location;
    const portSuffix =
      port && port !== '80' && port !== '443' ? `:${port}` : '';
    return `${protocol}//${hostname}${portSuffix}/auth/callback`;
  }
  return 'http://localhost:8080/auth/callback';
};

export default supabase;
