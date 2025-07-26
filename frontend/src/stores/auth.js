import { reactive, computed } from 'vue'
import { createClient } from '@supabase/supabase-js'
import { addCSRFHeader, clearCSRFToken } from '../utils/csrf'

// Supabase configuration
const supabaseUrl = process.env.VUE_APP_SUPABASE_URL
const supabaseAnonKey = process.env.VUE_APP_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing required environment variables: VUE_APP_SUPABASE_URL and VUE_APP_SUPABASE_ANON_KEY')
  throw new Error('Supabase configuration is missing. Please check your environment variables.')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Auth store
const state = reactive({
  user: null,
  session: null,
  profile: null,
  loading: false,
  error: null
})

export const useAuthStore = () => {
  // Computed properties
  const isAuthenticated = computed(() => !!state.session)
  const isAdmin = computed(() => state.profile?.role === 'admin')
  const isTeamManager = computed(() => state.profile?.role === 'team-manager')
  const canManageTeam = computed(() => isAdmin.value || isTeamManager.value)
  const userRole = computed(() => state.profile?.role || 'team-fan')
  const userTeamId = computed(() => state.profile?.team_id)

  // Actions
  const setLoading = (loading) => {
    state.loading = loading
  }

  const setError = (error) => {
    state.error = error
  }

  const clearError = () => {
    state.error = null
  }

  const setUser = (user) => {
    state.user = user
  }

  const setSession = (session) => {
    state.session = session
    if (session?.access_token) {
      localStorage.setItem('auth_token', session.access_token)
    } else {
      localStorage.removeItem('auth_token')
    }
  }

  const setProfile = (profile) => {
    state.profile = profile
  }

  const signup = async (email, password, displayName) => {
    try {
      setLoading(true)
      clearError()

      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            display_name: displayName || email.split('@')[0]
          }
        }
      })

      if (error) throw error

      return {
        success: true,
        message: 'Signup successful! Please check your email for verification.',
        user: data.user
      }
    } catch (error) {
      setError(error.message)
      return { success: false, error: error.message }
    } finally {
      setLoading(false)
    }
  }

  const login = async (email, password) => {
    try {
      setLoading(true)
      clearError()

      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password
      })

      if (error) throw error

      setUser(data.user)
      setSession(data.session)
      
      // Fetch user profile
      await fetchProfile()

      return { success: true, user: data.user }
    } catch (error) {
      setError(error.message)
      return { success: false, error: error.message }
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    try {
      setLoading(true)
      const { error } = await supabase.auth.signOut()
      if (error) throw error

      setUser(null)
      setSession(null)
      setProfile(null)
      localStorage.removeItem('auth_token')
      localStorage.removeItem('sb-localhost-auth-token')
      clearCSRFToken() // Clear CSRF token on logout
      
      return { success: true }
    } catch (error) {
      setError(error.message)
      return { success: false, error: error.message }
    } finally {
      setLoading(false)
    }
  }
  
  const forceLogout = () => {
    // Force clear all auth state without async calls
    state.user = null
    state.session = null
    state.profile = null
    state.loading = false
    state.error = null
    localStorage.clear()
    sessionStorage.clear()
  }

  const fetchProfile = async () => {
    try {
      if (!state.session) return

      const { data, error } = await supabase
        .from('user_profiles')
        .select(`
          *,
          team:teams(id, name, city)
        `)
        .eq('id', state.user.id)
        .single()

      if (error) throw error
      setProfile(data)
      return data
    } catch (error) {
      console.error('Error fetching profile:', error)
      setError(error.message)
    }
  }

  const updateProfile = async (updates) => {
    try {
      setLoading(true)
      clearError()

      const { data, error } = await supabase
        .from('user_profiles')
        .update({
          ...updates,
          updated_at: new Date().toISOString()
        })
        .eq('id', state.user.id)
        .select()

      if (error) throw error

      // Refresh profile
      await fetchProfile()

      return { success: true, data }
    } catch (error) {
      setError(error.message)
      return { success: false, error: error.message }
    } finally {
      setLoading(false)
    }
  }

  const initialize = async () => {
    try {
      setLoading(true)
      
      // Get initial session
      const { data: { session }, error } = await supabase.auth.getSession()
      
      if (error) throw error

      if (session) {
        setUser(session.user)
        setSession(session)
        await fetchProfile()
      }

      // Listen for auth changes
      supabase.auth.onAuthStateChange(async (event, session) => {
        if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
          setUser(session.user)
          setSession(session)
          await fetchProfile()
        } else if (event === 'SIGNED_OUT') {
          setUser(null)
          setSession(null)
          setProfile(null)
        }
      })

    } catch (error) {
      setError(error.message)
    } finally {
      setLoading(false)
    }
  }

  // API helpers with auth headers
  const getAuthHeaders = () => {
    return {
      'Authorization': `Bearer ${state.session?.access_token}`,
      'Content-Type': 'application/json'
    }
  }

  const isTokenExpiringSoon = () => {
    if (!state.session?.expires_at) return false
    const expiresAt = new Date(state.session.expires_at * 1000)
    const now = new Date()
    const timeUntilExpiry = expiresAt.getTime() - now.getTime()
    // Return true if token expires in less than 5 minutes
    return timeUntilExpiry < 5 * 60 * 1000
  }

  const refreshSession = async () => {
    try {
      console.log('Attempting to refresh session...')
      
      // Get current session first to check if we have a refresh token
      const { data: currentSession } = await supabase.auth.getSession()
      if (!currentSession.session) {
        console.log('No current session found for refresh')
        return false
      }
      
      const { data, error } = await supabase.auth.refreshSession()
      if (error) {
        console.error('Refresh session error:', error)
        // If refresh token is expired, we need to log out
        if (error.message && error.message.includes('refresh_token_not_found')) {
          console.log('Refresh token expired, logging out')
          await logout()
          return false
        }
        throw error
      }
      
      if (data.session && data.user) {
        console.log('Session refreshed successfully')
        setSession(data.session)
        setUser(data.user)
        return true
      }
      console.log('No session data returned from refresh')
      return false
    } catch (error) {
      console.error('Failed to refresh session:', error)
      // Don't call logout here as it might create a loop
      return false
    }
  }

  const apiRequest = async (url, options = {}, retryCount = 0) => {
    // Check if token is expiring soon and refresh proactively
    if (isTokenExpiringSoon() && retryCount === 0) {
      console.log('Token expiring soon, refreshing proactively...')
      await refreshSession()
    }

    // Add CSRF headers for state-changing methods
    let headers = {
      ...getAuthHeaders(),
      ...options.headers
    }
    
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method?.toUpperCase())) {
      headers = await addCSRFHeader(headers)
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers
      })

      // If unauthorized and we haven't retried yet, try refreshing the token
      if (response.status === 401 && retryCount === 0) {
        console.log('Got 401, attempting to refresh token...')
        const refreshed = await refreshSession()
        if (refreshed) {
          console.log('Token refreshed, retrying request...')
          // Get fresh headers with the new token
          const newHeaders = {
            ...getAuthHeaders(),
            ...options.headers
          }
          // Retry the request with the new token
          const retryResponse = await fetch(url, {
            ...options,
            headers: newHeaders
          })
          
          if (!retryResponse.ok) {
            const error = await retryResponse.json().catch(() => ({ message: 'Network error' }))
            throw new Error(error.detail || error.message || 'Request failed')
          }
          
          return retryResponse.json()
        } else {
          console.log('Token refresh failed, forcing logout')
          await logout()
          throw new Error('Session expired. Please log in again.')
        }
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ message: 'Network error' }))
        throw new Error(error.detail || error.message || 'Request failed')
      }

      return response.json()
    } catch (error) {
      if (error.message.includes('Session expired')) {
        throw error
      }
      console.error('API Request error:', error)
      throw new Error(error.message || 'Network error occurred')
    }
  }

  return {
    // State
    state,
    
    // Computed
    isAuthenticated,
    isAdmin,
    isTeamManager,
    canManageTeam,
    userRole,
    userTeamId,
    
    // Actions
    signup,
    login,
    logout,
    forceLogout,
    fetchProfile,
    updateProfile,
    initialize,
    setError,
    clearError,
    
    // Helpers
    getAuthHeaders,
    apiRequest,
    refreshSession,
    isTokenExpiringSoon
  }
}