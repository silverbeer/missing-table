# 🏈 Deploy Missing Table to Railway + Supabase

**Quick deployment guide for Missing Table - U13 & U14 MLS Next Season Tracking**

## 🚀 Quick Start (5 minutes)

### Prerequisites
- ✅ GitHub account with this repository
- ✅ Railway account ([sign up free](https://railway.app))
- ✅ Supabase account ([sign up free](https://supabase.com))

### Step 1: Set Up Supabase (2 minutes)
1. **Create Project**: Go to [Supabase Dashboard](https://supabase.com/dashboard) → "New Project"
2. **Run Migrations**: 
   - Go to SQL Editor in your Supabase project
   - Copy and run each file from `supabase/migrations/` in order
3. **Get Credentials**: Settings → API → Copy these values:
   ```
   Project URL: https://your-project.supabase.co
   Anon Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   Service Role Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   JWT Secret: (from Settings → Database)
   ```

### Step 2: Deploy to Railway (3 minutes)
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login to Railway
railway login

# 3. Run automated setup
./deploy-railway.sh setup

# 4. Configure with your Supabase credentials
./deploy-railway.sh configure

# 5. Deploy Missing Table
./deploy-railway.sh deploy

# 6. Check deployment status
./deploy-railway.sh health
```

**That's it! 🎉 Your Missing Table app is now live.**

## 📋 What Gets Deployed

### Backend Service
- **FastAPI API** - All endpoints for teams, games, standings
- **Authentication** - JWT-based auth with role management
- **Admin Panel APIs** - Team/game/division management
- **Rate Limiting** - Redis-powered rate limiting
- **CORS** - Configured for Railway domains

### Frontend Service  
- **Vue.js App** - Complete Missing Table interface
- **Admin Dashboard** - Full admin functionality
- **Responsive Design** - Works on mobile/desktop
- **Real-time Updates** - Connected to your Supabase database

### Database (Supabase)
- **PostgreSQL** - Production-ready database
- **Real-time** - Live updates across clients
- **Row Level Security** - Built-in security
- **Backups** - Automatic daily backups

## 🌐 Your Live App

After deployment, you'll have:

- **🏠 Frontend**: `https://missing-table-frontend-production.up.railway.app`
- **🔧 Backend API**: `https://missing-table-backend-production.up.railway.app`
- **📚 API Docs**: `https://missing-table-backend-production.up.railway.app/docs`
- **💾 Database**: Your Supabase dashboard

## ⚙️ Post-Deployment Setup

### 1. Create Admin User
```bash
# SSH into your backend
cd backend && railway shell

# Run admin creation script
python make_admin.py your-email@domain.com
```

### 2. Import Game Data
- Use the Admin Panel → Games → Import CSV
- Or run import scripts through Railway shell

### 3. Set Up Teams
- Admin Panel → Teams → Add teams
- Assign age groups (U13, U14)
- Set up divisions

## 🔧 Management Commands

```bash
# View app status
./deploy-railway.sh status

# Check health
./deploy-railway.sh health

# View logs
./deploy-railway.sh logs

# Scale up for more traffic
./deploy-railway.sh scale 2

# Redeploy after changes
./deploy-railway.sh deploy
```

## 💰 Cost Breakdown

### Hobby Tier (Perfect for teams/clubs)
- **Railway**: $5/month per service = $10/month
- **Supabase**: Free tier (500MB database)
- **Total**: ~$10/month

### Production Tier (Multiple leagues)
- **Railway Pro**: $20/month per service = $40/month  
- **Supabase Pro**: $25/month (8GB database)
- **Redis**: $3/month
- **Total**: ~$68/month

## 🚨 Troubleshooting

### ❌ Build Failures
```bash
# Check logs
./deploy-railway.sh logs backend

# Common fixes:
# - Verify all environment variables are set
# - Check Supabase credentials
# - Ensure migrations ran successfully
```

### ❌ CORS Errors
```bash
# Check if frontend domain is allowed in backend CORS
# Update CORS origins in backend/app.py if needed
```

### ❌ Database Connection Issues
```bash
# Verify Supabase credentials
railway variables | grep SUPABASE

# Test connection
cd backend && railway shell
python -c "from supabase import create_client; import os; print('✅ Connected!' if create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY')) else '❌ Failed')"
```

## 🔒 Security Features

✅ **JWT Authentication** - Secure user sessions  
✅ **Role-Based Access** - Admin, team manager, player, fan roles  
✅ **CSRF Protection** - Cross-site request forgery protection  
✅ **Rate Limiting** - Prevent API abuse  
✅ **HTTPS Only** - All traffic encrypted  
✅ **Environment Variables** - Secrets stored securely  

## 📱 Features Live on Your Site

- **📊 League Standings** - Real-time standings calculation
- **📅 Game Schedules** - Schedule and score games  
- **👥 Team Management** - Multi-age group teams
- **🏆 Admin Dashboard** - Complete management interface
- **📈 Statistics** - Team and player statistics
- **🔐 User Accounts** - Secure user registration/login
- **📱 Mobile Friendly** - Works great on phones

## 🎯 Next Steps

1. **Custom Domain**: Add your own domain in Railway settings
2. **Email Setup**: Configure transactional emails in Supabase
3. **Analytics**: Add Google Analytics or Railway Analytics
4. **Monitoring**: Set up uptime monitoring
5. **Backups**: Configure automated database backups

## 🆘 Support

- **Railway Docs**: https://docs.railway.app
- **Supabase Docs**: https://supabase.com/docs  
- **Repository Issues**: Create an issue in this repository

---

**🏈 Missing Table is now live and tracking your U13 & U14 MLS Next season!**