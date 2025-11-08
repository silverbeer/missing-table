# 🚀 Next Steps - Getting Started with MT Testing Crew

**Phase 1 Complete!** ✅ Now let's get you testing the crew.

---

## 📋 Quick Start - Testing the Crew

### Step 1: Get API Keys (Required)

You need at least one LLM provider API key to run the crew.

#### Option A: OpenAI Only (WORKS FOR PHASE 1!)

**What works:** Swagger agent (Phase 1) now uses GPT-4o-mini
**Cost:** ~$0.03 per scan (even cheaper than Anthropic!)

1. Go to https://platform.openai.com/api-keys
2. Create new secret key (or use your existing key)
3. Copy the key (starts with `sk-proj-...` or `sk-...`)

**Perfect if:** You already have an OpenAI API key and want to start testing now!

#### Option B: Anthropic Only

**What works:** All Haiku-based agents (5 agents in Phases 2-3)
**Cost:** ~$0.05 per agent run

1. Go to https://console.anthropic.com/
2. Sign up or login (free trial available)
3. Navigate to API Keys
4. Create new API key
5. Copy the key (starts with `sk-ant-api03-...`)

#### Option C: Both Providers (Full Flexibility - RECOMMENDED)

**What works:** All future agents (Phases 2-4)
**Cost:** ~$0.85 per full crew run

1. **Anthropic:** Follow Option A above
2. **OpenAI:**
   - Go to https://platform.openai.com/api-keys
   - Create new secret key
   - Copy the key (starts with `sk-proj-...`)

---

### Step 2: Configure API Keys

Add your API keys to the backend `.env.local` file:

```bash
# Edit the file
cd /Users/silverbeer/gitrepos/missing-table
vim backend/.env.local

# Add your keys (replace with real keys)
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-ACTUAL-KEY-HERE
OPENAI_API_KEY=sk-proj-YOUR-ACTUAL-KEY-HERE  # Optional for Phase 1

# Optional: Set default provider
CREW_LLM_PROVIDER=anthropic

# Optional: Enable verbose mode
CREW_VERBOSE=false
```

**Security Note:** Never commit real API keys to git! The `.env.local` file is gitignored.

---

### Step 3: Start the MT Backend

The crew needs the Missing Table backend running to scan the API:

```bash
# Start backend and frontend
./missing-table.sh dev

# OR just backend
cd backend && uv run python app.py

# Verify it's running
curl http://localhost:8000/openapi.json
```

**Expected:** You should see JSON output (the OpenAPI spec).

---

### Step 4: Run Your First Scan!

```bash
# Basic scan (scans local backend)
./crew_testing/run.sh scan

# Verbose mode (see agent thinking)
./crew_testing/run.sh scan --verbose

# Scan dev environment
./crew_testing/run.sh scan --url https://dev.missingtable.com
```

**What happens:**
1. Swagger agent reads the OpenAPI spec
2. Catalogs all endpoints (47+ endpoints)
3. Detects gaps in api_client coverage
4. Reports missing methods
5. Shows statistics

**Expected output:**
```
🤖 MT Testing Crew
📚 Swagger - API Documentation Expert

Scanning: http://localhost:8000

✅ Scan Results:
- Endpoints cataloged: 47
- Coverage gaps detected: X
- Missing methods: Y
...
```

---

### Step 5: Explore the Crew

```bash
# Show version info
./crew_testing/run.sh version

# List all agents (8 total, 1 active)
./crew_testing/run.sh agents

# Show LLM configuration
./crew_testing/run.sh llm-config

# Check system status
./crew_testing/status.sh

# Run verification tests
./crew_testing/verify.sh
```

---

## 🧪 Testing Scenarios

Follow the comprehensive testing guide:

```bash
# Read the testing guide
cat crew_testing/TESTING_GUIDE.md

# Or open in your editor
vim crew_testing/TESTING_GUIDE.md
```

**Testing scenarios covered:**
1. ✅ No API keys (error handling)
2. ✅ Anthropic only (Swagger works)
3. ✅ OpenAI only (future agents)
4. ✅ Both providers (full crew)

---

## 📊 Understanding the Output

### Scan Results

**What Swagger reports:**
- **Endpoints cataloged**: All API endpoints found
- **Coverage gaps**: Endpoints missing from api_client
- **Missing methods**: Specific methods to add
- **Statistics**: Coverage percentage, etc.

### Example Output

```
📚 SWAGGER SCAN RESULTS

Endpoints Found: 47
├── GET /api/auth/me
├── POST /api/auth/login
├── GET /api/standings
├── POST /api/matches
└── ... (43 more)

Coverage Gaps Detected:
❌ Missing: get_auth_me()
❌ Missing: create_match()
✅ Exists: get_standings()

Coverage: 85% (40/47 endpoints)
```

---

## 💰 Cost Tracking

### Phase 1 Costs

**Per scan:** ~$0.05 (Anthropic Haiku)

**Monthly estimates:**
- 10 scans: $0.50
- 50 scans: $2.50
- 100 scans: $5.00

Still **99% cheaper than manual testing!** 🎯

### Check Your Usage

**Anthropic:**
- Console: https://console.anthropic.com/
- Navigate to "Usage" tab

**OpenAI:**
- Dashboard: https://platform.openai.com/usage
- View API usage

---

## 🐛 Troubleshooting

### "No LLM provider configured"

**Fix:** Add at least one API key to `.env.local`

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." >> backend/.env.local
```

### "Agent 'swagger' requires Anthropic but key not set"

**Fix:** You're using OpenAI only. Add Anthropic key or wait for Phase 2.

### "Backend not responding"

**Fix:** Start the Missing Table backend

```bash
./missing-table.sh start
curl http://localhost:8000/openapi.json
```

### "ModuleNotFoundError: No module named 'crewai'"

**Fix:** Install dependencies

```bash
cd backend && uv sync
```

### "Permission denied: ./crew_testing/run.sh"

**Fix:** Make script executable

```bash
chmod +x crew_testing/run.sh
```

---

## 📖 Documentation

### Essential Reading

1. **Testing Guide** - `crew_testing/TESTING_GUIDE.md`
   - Complete testing scenarios
   - Provider configurations
   - Expected outputs

2. **Multi-LLM Feature** - `crew_testing/MULTI_LLM_FEATURE.md`
   - How multi-LLM works
   - Cost optimization strategy
   - Per-agent assignments

3. **Implementation Summary** - `crew_testing/IMPLEMENTATION_SUMMARY.md`
   - Technical architecture
   - File structure
   - Agent details

4. **Phase 1 Complete** - `crew_testing/PHASE1_COMPLETE.md`
   - What was built
   - Success metrics
   - Next phases

5. **Press Release** - `crew_testing/PRESS_RELEASE.md`
   - Sports-themed announcement
   - Full roster details
   - Competitive advantages

---

## 🎯 What's Next After Testing?

### Phase 2: Core Squad Activation

**Coming Next:**
- 🎯 Architect - Test scenario designer (OpenAI GPT-4o)
- 🎨 Mocker - Test data generator (Anthropic Haiku)
- ⚡ Flash - Test executor (Anthropic Haiku)
- 🔧 Forge - Code generator (OpenAI GPT-4o)

**Timeline:** Week 2 of 4-week plan

**Goal:** End-to-end test generation for `/api/matches`

### Phase 3: Intelligence Layer

**Agents:**
- 🔬 Inspector - Quality analyst (Anthropic Haiku)
- 📊 Herald - Test reporter (Anthropic Haiku)
- 🐛 Sherlock - Debug specialist (OpenAI GPT-4o)

**Timeline:** Week 3 of 4-week plan

**Goal:** Complete autonomous testing with beautiful reports

### Phase 4: Production Deployment

**Deliverables:**
- GitHub Actions integration
- PR automation
- Demo video (5 minutes)
- Interview presentation

**Timeline:** Week 4 of 4-week plan

---

## 🏆 Success Criteria

### You're Ready for Phase 2 When:

- ✅ Swagger agent runs successfully
- ✅ Scans complete in 5-10 seconds
- ✅ Coverage gaps detected accurately
- ✅ Both LLM providers configured (optional but recommended)
- ✅ Cost tracking understood
- ✅ Comfortable with CLI commands

---

## 💡 Pro Tips

### Tip 1: Use Verbose Mode for Learning

```bash
./crew_testing/run.sh scan --verbose
```

See exactly what Swagger is thinking and doing!

### Tip 2: Test Different Environments

```bash
# Local backend
./crew_testing/run.sh scan

# Dev environment
./crew_testing/run.sh scan --url https://dev.missingtable.com

# Production (read-only scan)
./crew_testing/run.sh scan --url https://missingtable.com
```

### Tip 3: Check Configuration First

```bash
# Before every scan session
./crew_testing/run.sh llm-config

# Verify:
# ✅ API keys configured
# ✅ Models assigned correctly
# ✅ Cost estimates accurate
```

### Tip 4: Keep Notes

Create a test log (see template in TESTING_GUIDE.md):

```markdown
## Test Session: 2025-01-07

### Configuration
- Anthropic: YES
- OpenAI: NO
- Backend: local

### Results
- Success: YES
- Cost: $0.05
- Time: 7 seconds
- Coverage: 85%
```

---

## 🚀 Ready to Start?

### Quick Start Checklist

- [ ] Get Anthropic API key
- [ ] Add to `.env.local`
- [ ] Start MT backend (`./missing-table.sh dev`)
- [ ] Run first scan (`./crew_testing/run.sh scan`)
- [ ] Check results
- [ ] Try verbose mode (`./crew_testing/run.sh scan --verbose`)
- [ ] Review documentation
- [ ] Track costs

### First Commands to Run

```bash
# 1. Check system status
./crew_testing/status.sh

# 2. Verify installation
./crew_testing/verify.sh

# 3. Check LLM config
./crew_testing/run.sh llm-config

# 4. Run first scan!
./crew_testing/run.sh scan --verbose
```

---

## 📞 Need Help?

### Documentation
- **Main README**: `crew_testing/README.md`
- **Testing Guide**: `crew_testing/TESTING_GUIDE.md`
- **Implementation**: `crew_testing/IMPLEMENTATION_SUMMARY.md`

### Community
- **GitHub Issues**: https://github.com/silverbeer/missing-table/issues
- **Pull Requests**: https://github.com/silverbeer/missing-table/pulls

### Contact
- **Quality Playbook**: https://qualityplaybook.dev
- **LinkedIn**: https://www.linkedin.com/in/tomdrake-qe

---

**Good luck with your testing!** 🎯

Remember: Phase 1 is just the foundation. The real magic happens when all 8 agents work together in Phases 2-4!

---

*Last Updated: 2025-01-07*
*Phase: 1 of 4*
*Status: Production Ready ✅*
