# 🧪 Testing Guide - MT Testing Crew

**Multi-LLM Provider Testing**
**Version:** 1.5.0
**Last Updated:** 2025-01-07

---

## 🎯 Testing Strategy

Test the CrewAI Testing System with:
1. ✅ No API keys (config validation)
2. ✅ Only Anthropic key (Anthropic-only mode)
3. ✅ Only OpenAI key (OpenAI-only mode)
4. ✅ Both keys (full multi-LLM mode)

---

## 📋 Pre-Testing Checklist

```bash
# 1. Ensure MT backend is running
./missing-table.sh status
./missing-table.sh start  # If not running

# 2. Check system status
./crew_testing/status.sh

# 3. Verify installation
./crew_testing/verify.sh
```

---

## Test 1: No API Keys (Validation)

**Purpose:** Verify graceful degradation and error messages

### Setup
```bash
# Ensure no API keys in .env.local
cd backend
grep "ANTHROPIC_API_KEY=your_anthropic_api_key_here" .env.local  # pragma: allowlist secret
grep "OPENAI_API_KEY=your_openai_api_key_here" .env.local  # pragma: allowlist secret
```

### Test Commands
```bash
./crew_testing/run.sh llm-config
```

### Expected Output
```
❌ Configuration Error: No LLM provider configured! Set either:
  - ANTHROPIC_API_KEY for Claude models
  - OPENAI_API_KEY for GPT models
  - Both for maximum flexibility
```

### Verify
- ✅ Clear error message
- ✅ Helpful instructions
- ✅ Shows which providers are missing

---

## Test 2: Anthropic Only

**Purpose:** Test with only Claude models

### Setup
```bash
# Edit backend/.env.local
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE
OPENAI_API_KEY=your_openai_api_key_here  # Leave as placeholder
```

### Get API Key
1. Go to https://console.anthropic.com/
2. Sign up or login
3. Create API key
4. Add to `.env.local`

### Test Commands
```bash
# Show configuration
./crew_testing/run.sh llm-config

# Run a scan
./crew_testing/run.sh scan

# Test verbose mode
./crew_testing/run.sh scan --verbose
```

### Expected Output
```
Providers Available:
  Anthropic: ✅ Configured
  OpenAI:    ❌ Not configured

⚠️  Agent 'architect' requires OpenAI but key not set
⚠️  Agent 'forge' requires OpenAI but key not set
⚠️  Agent 'sherlock' requires OpenAI but key not set
```

### Verify
- ✅ Swagger agent works (uses Anthropic)
- ⚠️ Warnings for agents needing OpenAI
- ✅ Scan completes successfully
- ✅ Cost shown: ~$0.05

### What Works
- 📚 Swagger (Anthropic Haiku)
- 🎨 Mocker (future)
- ⚡ Flash (future)
- 🔬 Inspector (future)
- 📊 Herald (future)

### What Doesn't
- 🎯 Architect (needs OpenAI)
- 🔧 Forge (needs OpenAI)
- 🐛 Sherlock (needs OpenAI)

---

## Test 3: OpenAI Only

**Purpose:** Test with only GPT models

### Setup
```bash
# Edit backend/.env.local
ANTHROPIC_API_KEY=your_anthropic_api_key_here  # Leave as placeholder
OPENAI_API_KEY=sk-proj-YOUR-KEY-HERE
```

### Get API Key
1. Go to https://platform.openai.com/api-keys
2. Create new secret key
3. Add to `.env.local`

### Test Commands
```bash
# Show configuration
./crew_testing/run.sh llm-config

# Agents command (shows which need Anthropic)
./crew_testing/run.sh agents
```

### Expected Output
```
Providers Available:
  Anthropic: ❌ Not configured
  OpenAI:    ✅ Configured

⚠️  Agent 'swagger' requires Anthropic but key not set
⚠️  Agent 'mocker' requires Anthropic but key not set
...
```

### Verify
- ⚠️ Warnings for agents needing Anthropic
- ✅ Future agents (Architect, Forge, Sherlock) would work
- ✅ Configuration shows correctly

### What Works (Future)
- 🎯 Architect (OpenAI GPT-4o)
- 🔧 Forge (OpenAI GPT-4o)
- 🐛 Sherlock (OpenAI GPT-4o)

### What Doesn't (Current)
- 📚 Swagger (needs Anthropic) - Currently implemented!

---

## Test 4: Both Providers (Recommended)

**Purpose:** Full multi-LLM experience

### Setup
```bash
# Edit backend/.env.local - Add BOTH keys
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE
OPENAI_API_KEY=sk-proj-YOUR-KEY-HERE
CREW_LLM_PROVIDER=anthropic  # Default provider
```

### Test Commands
```bash
# Show full configuration
./crew_testing/run.sh llm-config

# Show agents with their LLMs
./crew_testing/run.sh agents

# Run a scan
./crew_testing/run.sh scan

# Verbose mode
./crew_testing/run.sh scan --verbose
```

### Expected Output
```
🤖 MT Testing Crew - LLM Configuration
======================================================================

Default Provider: anthropic

Providers Available:
  Anthropic: ✅ Configured
  OpenAI:    ✅ Configured

Per-Agent Configuration:
----------------------------------------------------------------------

📚 Swagger
   Provider: anthropic
   Model: claude-3-haiku-20240307
   Cost/run: $0.05
   Why: Simple API parsing, Haiku is perfect

🎯 Architect
   Provider: openai
   Model: gpt-4o
   Cost/run: $0.20
   Why: Test design requires deep reasoning, GPT-4o excels

... (6 more agents)

======================================================================
Estimated Total Cost per Full Run: $0.85
```

### Verify
- ✅ All providers configured
- ✅ No warnings
- ✅ Full crew operational
- ✅ Scan works perfectly
- ✅ Cost estimate shown

---

## 🔬 Advanced Testing

### Test Different Default Providers

```bash
# Try OpenAI as default
echo "CREW_LLM_PROVIDER=openai" >> backend/.env.local
./crew_testing/run.sh llm-config
```

### Test Verbose Mode

```bash
# See agent thinking
./crew_testing/run.sh scan --verbose
```

### Test Different Backends

```bash
# Test with dev backend
./crew_testing/run.sh scan --url https://dev.missingtable.com
```

---

## 📊 Performance Testing

### Measure Scan Time

```bash
time ./crew_testing/run.sh scan
```

### Expected Times
- **Swagger only:** 5-10 seconds
- **Full crew (future):** 30-60 seconds

### Cost Tracking

```bash
# Anthropic only: ~$0.05 per scan
# Full crew: ~$0.85 per scan
#
# Monthly (100 scans): ~$85
# Still cheaper than manual testing! 💰
```

---

## 🐛 Troubleshooting

### Problem: "No LLM provider configured"

**Solution:**
```bash
# Add at least one API key to .env.local
echo "ANTHROPIC_API_KEY=sk-ant-..." >> backend/.env.local
```

### Problem: "Agent 'X' requires Anthropic but key not set"

**Solution:**
- Either add Anthropic key
- Or wait for that agent (not implemented yet)

### Problem: "ImportError: langchain_openai"

**Solution:**
```bash
cd backend && uv sync
```

### Problem: Backend not responding

**Solution:**
```bash
./missing-table.sh restart
curl http://localhost:8000/openapi.json
```

---

## ✅ Test Checklist

Use this for each testing session:

### Basic Tests
- [ ] `./crew_testing/status.sh` - System status
- [ ] `./crew_testing/verify.sh` - Verification tests
- [ ] `./crew_testing/run.sh version` - Version info
- [ ] `./crew_testing/run.sh agents` - Agent list
- [ ] `./crew_testing/run.sh llm-config` - LLM configuration

### Provider Tests
- [ ] No API keys - Error handling
- [ ] Anthropic only - Works with warnings
- [ ] OpenAI only - Shows configuration
- [ ] Both providers - Full functionality

### Functional Tests
- [ ] `./crew_testing/run.sh scan` - Basic scan
- [ ] `./crew_testing/run.sh scan --verbose` - Verbose scan
- [ ] Backend integration - Scans actual API
- [ ] Error handling - Graceful failures

### Cost Tests
- [ ] LLM config shows costs
- [ ] Agents show per-run cost
- [ ] Total cost calculated correctly

---

## 📈 Success Criteria

### Must Pass
- ✅ Verification script passes
- ✅ No API keys → Clear error
- ✅ One provider → Works with warnings
- ✅ Both providers → Full functionality
- ✅ Scan completes successfully
- ✅ Cost information accurate

### Nice to Have
- ✅ Fast response times
- ✅ Clear error messages
- ✅ Helpful warnings
- ✅ Beautiful output

---

## 🎓 Testing Notes

### Cost Expectations

**Anthropic Only (Current):**
- Swagger: $0.05 per scan
- Future agents: 4 × $0.05 = $0.20
- Subtotal: $0.25 per full run

**Mixed (Recommended):**
- Anthropic (5 agents): $0.25
- OpenAI (3 agents): $0.60
- Total: $0.85 per full run

**All Premium:**
- All Sonnet: $2.40 per run
- All GPT-4o: $1.60 per run

### Testing Budget

- **Initial testing:** 10 scans × $0.05 = $0.50
- **Development:** 50 scans × $0.85 = $42.50 (full crew)
- **Production:** ~100 scans/month × $0.85 = $85/month

Still cheaper than 1 hour of manual testing! 🎯

---

## 🚀 Next Steps After Testing

1. **Document results** - Keep notes on what works
2. **Compare providers** - Which is better for each task?
3. **Optimize costs** - Adjust agent LLM assignments
4. **Expand testing** - Try different endpoints
5. **Build Phase 2** - Implement remaining agents

---

## 📝 Test Log Template

```markdown
## Test Session: [DATE]

### Configuration
- Anthropic: [YES/NO]
- OpenAI: [YES/NO]
- Backend: [local/dev/prod]

### Tests Run
- [ ] llm-config
- [ ] agents
- [ ] scan
- [ ] scan --verbose

### Results
- Success: [YES/NO]
- Cost: $X.XX
- Time: XX seconds
- Issues: [NONE/LIST]

### Notes
[Your observations here]
```

---

**Happy Testing!** 🧪
**Questions?** Check the main README.md or MULTI_LLM_FEATURE.md

---

_Last Updated: 2025-01-07_
_Status: Ready for testing ✅_
