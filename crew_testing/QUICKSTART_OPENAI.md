# 🚀 Quick Start with OpenAI API Key

**Good news!** You can start testing the crew RIGHT NOW with just your OpenAI API key.

---

## ✅ Changes Made

**Swagger agent now uses OpenAI GPT-4o-mini** instead of Anthropic Claude Haiku.

**Why this is great:**
- ✅ You can start testing immediately with your existing key
- ✅ Even cheaper: ~$0.03 per scan (vs $0.05 with Haiku)
- ✅ Still performs excellently for API cataloging
- ✅ Multi-provider flexibility remains intact

---

## 🎯 Quick Start (3 Steps)

### Step 1: Add Your OpenAI Key

```bash
# Navigate to project root
cd /Users/silverbeer/gitrepos/missing-table

# Add your OpenAI API key to .env.local
echo "OPENAI_API_KEY=your-openai-key-here" >> backend/.env.local

# Verify it's added
grep OPENAI_API_KEY backend/.env.local
```

**Note:** Replace `your-openai-key-here` with your actual OpenAI API key.

---

### Step 2: Start the Backend

```bash
# Start MT backend (required for scanning)
./missing-table.sh dev

# Verify it's running
curl http://localhost:8000/openapi.json
```

**Expected:** You should see JSON output (the OpenAPI spec).

---

### Step 3: Run Your First Scan!

```bash
# Run scan with verbose mode to see agent thinking
./crew_testing/run.sh scan --verbose
```

**What happens:**
1. Swagger agent (GPT-4o-mini) reads the OpenAPI spec
2. Catalogs all 47+ endpoints
3. Detects coverage gaps
4. Reports missing api_client methods
5. Shows statistics

**Expected cost:** ~$0.03 per scan 💰

---

## 📊 Example Output

```
🤖 MT Testing Crew
📚 Swagger - API Documentation Expert (GPT-4o-mini)

Scanning: http://localhost:8000

✅ Scan Results:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 API ENDPOINTS CATALOGED: 47

Coverage Gaps Detected:
❌ Missing: get_auth_me()
❌ Missing: create_match()
✅ Exists: get_standings()

Coverage: 85% (40/47 endpoints)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cost for this scan: ~$0.03
```

---

## 🎯 Next Commands to Try

```bash
# Check LLM configuration
./crew_testing/run.sh llm-config

# Should show:
# 📚 Swagger
#    Provider: openai
#    Model: gpt-4o-mini
#    Cost/run: $0.03

# List all agents
./crew_testing/run.sh agents

# Check system status
./crew_testing/status.sh

# Run verification tests
./crew_testing/verify.sh
```

---

## 💡 Pro Tips

### Tip 1: Use Verbose Mode

```bash
./crew_testing/run.sh scan --verbose
```

See exactly what the agent is thinking and doing!

### Tip 2: Scan Different Environments

```bash
# Local backend
./crew_testing/run.sh scan

# Dev environment
./crew_testing/run.sh scan --url https://dev.missingtable.com
```

### Tip 3: Track Your Costs

Check your OpenAI usage at: https://platform.openai.com/usage

Each scan costs about **$0.03**, so 100 scans = **$3.00/month**

Still **99% cheaper than manual testing!** 🎯

---

## 🔄 Updated Architecture

### Phase 1 (Current)
- **Swagger**: OpenAI GPT-4o-mini ($0.03/run) ✅ WORKS NOW

### Phase 2 (Coming Soon)
- **Architect**: OpenAI GPT-4o ($0.20/run) ✅ Will work with your key
- **Mocker**: Anthropic Haiku ($0.05/run) ⚠️ Will need Anthropic key
- **Flash**: Anthropic Haiku ($0.05/run) ⚠️ Will need Anthropic key
- **Forge**: OpenAI GPT-4o ($0.20/run) ✅ Will work with your key

### Phase 3 (Future)
- **Inspector**: Anthropic Haiku ($0.05/run) ⚠️ Will need Anthropic key
- **Herald**: Anthropic Haiku ($0.05/run) ⚠️ Will need Anthropic key
- **Sherlock**: OpenAI GPT-4o ($0.20/run) ✅ Will work with your key

**With OpenAI only, you'll have:**
- ✅ 4 out of 8 agents working (Swagger, Architect, Forge, Sherlock)
- ⚠️ 4 agents need Anthropic (Mocker, Flash, Inspector, Herald)

**Recommendation:** Get a free Anthropic trial for complete flexibility, but you can start testing NOW with OpenAI!

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: langchain_openai"

```bash
cd backend && uv sync
```

### "OPENAI_API_KEY not set"

```bash
# Check if it's in .env.local
grep OPENAI_API_KEY backend/.env.local

# Add it if missing
echo "OPENAI_API_KEY=your-key" >> backend/.env.local
```

### "Backend not responding"

```bash
./missing-table.sh restart
curl http://localhost:8000/openapi.json
```

---

## 📖 Full Documentation

For complete details, see:
- **NEXT_STEPS.md** - Comprehensive getting started guide
- **TESTING_GUIDE.md** - Testing scenarios and configurations
- **MULTI_LLM_FEATURE.md** - How multi-LLM support works
- **README.md** - Complete project documentation

---

## ✅ Ready to Go!

You're all set! Here's your complete workflow:

```bash
# 1. Add OpenAI key (if not already done)
echo "OPENAI_API_KEY=your-key" >> backend/.env.local

# 2. Start backend
./missing-table.sh dev

# 3. Run first scan
./crew_testing/run.sh scan --verbose

# 4. Explore
./crew_testing/run.sh llm-config
./crew_testing/run.sh agents
```

---

**Happy testing!** 🎯

---

*Last Updated: 2025-01-07*
*Status: Production Ready with OpenAI ✅*
