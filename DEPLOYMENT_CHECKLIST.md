# 🚀 Missing Table Deployment Checklist

## ✅ Pre-Deployment Checklist

### 📋 Requirements
- [ ] GitHub repository access
- [ ] Railway account (free signup at railway.app)
- [ ] Supabase account (free signup at supabase.com)
- [ ] Railway CLI installed (`npm install -g @railway/cli`)

### 🔧 Code Preparation
- [ ] All changes committed to v1.4 branch
- [ ] Backend CORS configured for Railway domains
- [ ] Frontend package.json has Railway-compatible scripts
- [ ] Environment variables documented

## 🎯 Deployment Steps

### Step 1: Supabase Setup
- [ ] Create new Supabase project
- [ ] Note down project URL, anon key, service key, JWT secret
- [ ] Run database migrations from `supabase/migrations/` folder
- [ ] Verify tables are created (teams, games, age_groups, etc.)
- [ ] Test database connection from Supabase dashboard

### Step 2: Railway Backend Deployment
- [ ] Login to Railway: `railway login`
- [ ] Run: `./deploy-railway.sh setup`
- [ ] Configure environment variables: `./deploy-railway.sh configure`
- [ ] Backend deploys successfully
- [ ] Health check passes: `/health` endpoint responds
- [ ] API docs accessible: `/docs` endpoint works

### Step 3: Railway Frontend Deployment  
- [ ] Frontend service created automatically
- [ ] Environment variables set (VUE_APP_SUPABASE_URL, VUE_APP_SUPABASE_ANON_KEY, VUE_APP_API_URL)
- [ ] Frontend builds successfully
- [ ] Frontend serves on Railway domain

### Step 4: Integration Testing
- [ ] Frontend can reach backend API
- [ ] Authentication flow works
- [ ] Database operations work (create/read/update/delete)
- [ ] Admin panel accessible
- [ ] CORS properly configured

## 🔍 Post-Deployment Verification

### Functional Tests
- [ ] Home page loads
- [ ] User registration works
- [ ] User login works
- [ ] League standings display
- [ ] Games/schedule display
- [ ] Admin panel accessible (for admin users)
- [ ] Team management works
- [ ] Game creation works

### Technical Tests  
- [ ] Health check: `./deploy-railway.sh health`
- [ ] API endpoints respond correctly
- [ ] Database queries execute
- [ ] Rate limiting works (if enabled)
- [ ] CSRF protection active
- [ ] Error handling works

## 🚨 Troubleshooting Guide

### Build Failures
**Symptoms**: Deployment fails during build
- [ ] Check logs: `./deploy-railway.sh logs`
- [ ] Verify all dependencies in pyproject.toml/package.json
- [ ] Check Python/Node version compatibility
- [ ] Ensure environment variables are set

### Database Connection Issues
**Symptoms**: 500 errors, database timeouts
- [ ] Verify Supabase credentials: `railway variables | grep SUPABASE`
- [ ] Test connection from Railway shell
- [ ] Check Supabase project is active
- [ ] Verify JWT secret matches

### CORS Errors
**Symptoms**: Frontend can't reach backend
- [ ] Check CORS origins in backend/app.py
- [ ] Verify frontend URL is in allowed origins
- [ ] Check VUE_APP_API_URL points to correct backend
- [ ] Test API directly with curl

### Frontend Loading Issues
**Symptoms**: Blank page, JavaScript errors
- [ ] Check browser console for errors
- [ ] Verify environment variables are set
- [ ] Check if API URL is reachable
- [ ] Test with network tab open

## 🔧 Environment Variables Reference

### Backend Variables (Required)
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_JWT_SECRET=your-jwt-secret
ENVIRONMENT=production
CSRF_SECRET_KEY=generated-secret
USE_REDIS_RATE_LIMIT=true
```

### Frontend Variables (Required)
```
VUE_APP_SUPABASE_URL=https://your-project.supabase.co
VUE_APP_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
VUE_APP_API_URL=https://your-backend.up.railway.app
```

## 📊 Monitoring & Maintenance

### Daily Monitoring
- [ ] Check application health: `./deploy-railway.sh health`
- [ ] Monitor error rates in Railway dashboard
- [ ] Check Supabase usage dashboard
- [ ] Verify backups are running

### Weekly Maintenance
- [ ] Review application logs for errors
- [ ] Check database performance metrics
- [ ] Monitor resource usage and costs
- [ ] Update dependencies if needed

### Monthly Reviews
- [ ] Performance optimization review
- [ ] Security updates
- [ ] Cost analysis and optimization
- [ ] User feedback implementation

## 🎉 Success Criteria

Your Missing Table deployment is successful when:

- ✅ **Frontend**: Loads at Railway URL
- ✅ **Backend**: API responds at `/health` and `/docs`
- ✅ **Database**: Supabase connected and operational
- ✅ **Authentication**: Users can register/login
- ✅ **Admin Panel**: Admin users can manage data
- ✅ **Core Features**: Teams, games, standings work
- ✅ **Performance**: Pages load in <3 seconds
- ✅ **Mobile**: Works on mobile devices

## 🔗 Important URLs

After deployment, bookmark these:

- **Live App**: `https://missing-table-frontend-production.up.railway.app`
- **API Docs**: `https://missing-table-backend-production.up.railway.app/docs`
- **Railway Dashboard**: `https://railway.app/dashboard`
- **Supabase Dashboard**: `https://supabase.com/dashboard`

## 🆘 Emergency Contacts

- **Railway Support**: https://railway.app/discord
- **Supabase Support**: https://supabase.com/discord
- **Repository Issues**: Create issue in GitHub repo

---

**🏈 Ready to track your U13 & U14 MLS Next season!**