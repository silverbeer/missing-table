# Queue CLI - RabbitMQ/Celery Testing Tool

**Status:** ✅ Phase 1 Complete

A comprehensive CLI tool for testing and learning about RabbitMQ/Celery distributed messaging systems.

## 🎯 Purpose

The Queue CLI tool helps developers:

1. **Test queue functionality** - Send messages to RabbitMQ queues easily
2. **Learn distributed systems** - Understand message flow with rich debug output
3. **Validate messages** - Ensure messages match the canonical schema
4. **Rapid development** - Test worker behavior without running full application

## 📋 Features (Phase 1)

### ✅ Implemented

- **Message Sending** - Send messages via Celery tasks or direct RabbitMQ publish
- **Template Management** - Built-in templates for common scenarios
- **Schema Validation** - Validates against canonical match-message-schema.json
- **Schema Translation** - Auto-translates between external and internal schemas
- **Rich Output** - Beautiful, educational CLI output using rich
- **Debug Mode** - Detailed visibility into message flow

### 🔜 Coming Soon (Phase 2+)

- **Task Status** - Monitor Celery task execution
- **Queue Statistics** - View queue depth, consumers, etc.
- **Worker Monitoring** - Check worker health and activity
- **Real-time Watching** - Live updates of queue activity
- **Load Testing** - Send batches of messages

## 🚀 Quick Start

### Prerequisites

```bash
# Ensure dependencies are installed (already done if you're in the backend directory)
cd backend
uv sync
```

### Infrastructure Requirements

The CLI requires RabbitMQ and Redis to be running. You have two options:

**Option 1: Local Docker (Recommended for testing)**
```bash
# Start local RabbitMQ
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin123 \  # pragma: allowlist secret
  rabbitmq:3-management

# Start local Redis
docker run -d --name redis -p 6379:6379 redis:latest

# Verify services are running
docker ps | grep -E "(rabbitmq|redis)"
```

**Option 2: K3s Cluster (When messaging platform is deployed)**
```bash
# Port-forward RabbitMQ from k3s
kubectl port-forward -n messaging svc/messaging-rabbitmq 5672:5672 &

# Port-forward Redis from k3s
kubectl port-forward -n messaging svc/messaging-redis 6379:6379 &
```

### Start a Celery Worker

```bash
# In a separate terminal
cd backend
celery -A celery_app worker --loglevel=info --queues=matches
```

## 📖 Usage

### List Available Templates

```bash
uv run python queue_cli.py templates
```

**Output:**
```
╭─────────────────────╮
│ Available Templates │
╰─────────────────────╯

┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Template Name   ┃ Description                   ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ completed-match │ Match with final scores       │
│ minimal         │ Required fields only          │
│ scheduled-match │ Upcoming match without scores │
│ tbd-match       │ Played match, awaiting scores │
└─────────────────┴───────────────────────────────┘
```

### Show a Specific Template

```bash
uv run python queue_cli.py templates --show completed-match
```

**Output:**
```json
{
  "home_team": "IFA 2012 Red",
  "away_team": "Inter Miami CF Academy 2012",
  "match_date": "2025-10-15T14:00:00Z",
  "season": "2024-25",
  "age_group": "U14",
  "division": "Northeast",
  "home_score": 3,
  "away_score": 1,
  "match_status": "completed",
  "match_type": "League",
  "external_match_id": "test-match-001",
  "location": "Home Field"
}
```

### Send a Message (via Celery Task)

```bash
uv run python queue_cli.py send --template completed-match
```

**Expected Output:**
```
╭───────────────────────────────╮
│ Sending Message to Queue      │
╰───────────────────────────────╯

📋 Message Validation
  ✓ Schema validation passed

🔌 RabbitMQ Connection
  • Broker: localhost:5672
  • Status: Established

⚙️ Celery Task
  • Task ID: 4f7e8c9d-1a2b-3c4d-5e6f-7g8h9i0j1k2l
  • Task Name: celery_tasks.match_tasks.process_match_data
  • State: PENDING

🔍 Next Steps:
  • Check task status: uv run python queue_cli.py status 4f7e8c9d...
  • View queue: uv run python queue_cli.py queues --name matches
  • View workers: uv run python queue_cli.py workers
```

### Send a Message (Direct RabbitMQ)

For educational purposes, you can publish directly to RabbitMQ to see the low-level mechanics:

```bash
uv run python queue_cli.py send --template tbd-match --rabbitmq
```

### Send with Debug Output

```bash
uv run python queue_cli.py send --template minimal --debug
```

**Debug output shows:**
- Broker and backend URLs
- Schema validation details
- Internal vs external schema translation
- Message routing information
- Queue statistics

### Send from a File

```bash
# Create a custom message file
cat > my-match.json << EOF
{
  "home_team": "Custom Team A",
  "away_team": "Custom Team B",
  "match_date": "2025-11-01T14:00:00Z",
  "season": "2024-25"
}
EOF

# Send it
uv run python queue_cli.py send --file my-match.json
```

### Send JSON String

```bash
uv run python queue_cli.py send --json '{
  "home_team": "Quick Test A",
  "away_team": "Quick Test B",
  "match_date": "2025-11-01T14:00:00Z",
  "season": "2024-25"
}'
```

## 🏗️ Architecture

### Directory Structure

```
backend/
├── queue_cli.py                      # Main CLI entry point
├── queue_cli/
│   ├── commands/
│   │   ├── send.py                   # Send command implementation
│   │   └── templates.py              # Templates command
│   ├── core/
│   │   ├── config.py                 # Configuration management
│   │   ├── rabbitmq.py               # RabbitMQ & Celery clients
│   │   ├── schema.py                 # Schema validation/translation
│   │   └── templates.py              # Template management
│   ├── templates/                    # Built-in message templates
│   │   ├── completed-match.json
│   │   ├── scheduled-match.json
│   │   ├── tbd-match.json
│   │   └── minimal.json
│   └── utils/
│       └── display.py                # Rich output formatting
└── docs/
    └── queue-cli/
        └── README.md                 # This file
```

### Schema Translation

The CLI handles translation between two schemas:

**Canonical Schema** (match-scraper → RabbitMQ):
- `date` → `match_date`
- `score_home` → `home_score`
- `score_away` → `away_score`
- `status` → `match_status`
- `match_id` → `external_match_id`

**Internal Schema** (Celery workers):
- Uses `match_date`, `home_score`, `away_score`, etc.
- Expected by `celery_tasks.match_tasks.process_match_data`

### Message Flow

```
CLI Tool
   │
   ├─→ Validate against canonical schema
   │
   ├─→ Translate to internal schema
   │
   ├─→ [Option 1] Celery Task Submit
   │        │
   │        └─→ RabbitMQ Queue (via kombu)
   │               │
   │               └─→ Celery Worker
   │                      │
   │                      └─→ Database (via DAO)
   │
   └─→ [Option 2] Direct RabbitMQ Publish (educational)
            │
            └─→ RabbitMQ Queue (via kombu)
                   │
                   └─→ Celery Worker
                          │
                          └─→ Database (via DAO)
```

## 🧪 Testing

### Test the CLI Without Infrastructure

You can test the CLI without RabbitMQ/Redis running:

```bash
# These work without infrastructure
uv run python queue_cli.py --help
uv run python queue_cli.py templates
uv run python queue_cli.py templates --show completed-match
uv run python queue_cli.py send --help
```

### Test with Infrastructure

Once you have RabbitMQ, Redis, and a Celery worker running:

```bash
# Test message sending
uv run python queue_cli.py send --template completed-match

# Watch the Celery worker logs in the other terminal
# You should see the task being processed
```

### Verify Message Processing

```bash
# Check worker logs
# You should see:
# [INFO] Processing match data: IFA 2012 Red vs Inter Miami CF Academy 2012
# [INFO] Successfully processed match
```

## 🎓 Learning Guide

### Understanding Message Queues

1. **Producer → Queue → Consumer Pattern**
   - CLI = Producer (sends messages)
   - RabbitMQ = Queue (stores messages)
   - Celery Worker = Consumer (processes messages)

2. **Asynchronous Processing**
   - CLI sends and returns immediately
   - Worker processes in the background
   - Decouples producers from consumers

3. **Reliability**
   - Messages persist in RabbitMQ
   - Automatic retries on failure
   - Dead letter queue for failed messages

### Try These Learning Exercises

1. **Send a message and watch the worker**
   ```bash
   # Terminal 1: Start worker with debug output
   celery -A celery_app worker --loglevel=debug --queues=matches

   # Terminal 2: Send a message
   uv run python queue_cli.py send --template completed-match --debug
   ```

2. **Compare Celery vs Direct RabbitMQ**
   ```bash
   # Via Celery (production method)
   uv run python queue_cli.py send --template tbd-match --celery

   # Direct RabbitMQ (educational)
   uv run python queue_cli.py send --template tbd-match --rabbitmq
   ```

3. **Experiment with schema translation**
   ```bash
   # Create a message with canonical schema fields
   uv run python queue_cli.py send --json '{
     "home_team": "Team A",
     "away_team": "Team B",
     "date": "2025-11-01",
     "season": "2024-25"
   }'

   # Watch how it gets translated to internal schema
   ```

## 🔧 Configuration

### Environment Variables

The CLI respects these environment variables:

```bash
# RabbitMQ connection
export CELERY_BROKER_URL="amqp://admin:admin123@localhost:5672//"  # pragma: allowlist secret
# Or
export RABBITMQ_URL="amqp://admin:admin123@localhost:5672//"  # pragma: allowlist secret

# Redis connection
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"
# Or
export REDIS_URL="redis://localhost:6379/0"
```

### Defaults

If no environment variables are set, the CLI uses:
- Broker: `amqp://admin:admin123@localhost:5672//` <!-- pragma: allowlist secret -->
- Backend: `redis://localhost:6379/0`
- Queue: `matches`
- Exchange: `matches`
- Routing Key: `matches.process`

## 🐛 Troubleshooting

### "Connection refused" Error

**Problem:** RabbitMQ is not running or not accessible

**Solutions:**
```bash
# Check if RabbitMQ is running
docker ps | grep rabbitmq

# Start RabbitMQ if not running
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin123 \  # pragma: allowlist secret
  rabbitmq:3-management

# Or port-forward from k3s
kubectl port-forward -n messaging svc/messaging-rabbitmq 5672:5672
```

### "Schema validation failed"

**Problem:** Message doesn't match the canonical schema

**Solutions:**
```bash
# Use a built-in template (guaranteed valid)
uv run python queue_cli.py send --template minimal

# Check the canonical schema
cat docs/08-integrations/match-message-schema.json

# Required fields: home_team, away_team, match_date, season
```

### "Template not found"

**Problem:** Template doesn't exist

**Solutions:**
```bash
# List available templates
uv run python queue_cli.py templates

# Use exact template name (case-sensitive)
uv run python queue_cli.py send --template completed-match
```

### Worker Not Processing Messages

**Problem:** Messages sent but not processed

**Solutions:**
```bash
# Check if worker is running
ps aux | grep celery

# Start a worker
celery -A celery_app worker --loglevel=info --queues=matches

# Check RabbitMQ queue has consumers
# Visit http://localhost:15672 (admin/admin123)  # pragma: allowlist secret
# Go to Queues → matches → check "Consumers" count
```

## 📚 Related Documentation

- [RabbitMQ/Celery Implementation Guide](../../docs/rabbitmq-celery/README.md)
- [Match Message Schema](../../docs/08-integrations/match-message-schema.json)
- [Celery Tasks](../celery_tasks/match_tasks.py)
- [Phase 1 Documentation](../../docs/rabbitmq-celery/01-PHASE-1-MESSAGE-QUEUE-BASICS.md)

## 🚀 Next Steps

With Phase 1 complete, you can now:

1. **Deploy RabbitMQ/Redis to k3s** (Phase 2)
2. **Add status command** to monitor tasks
3. **Add queues command** to view queue stats
4. **Add workers command** to monitor workers
5. **Add load testing** capabilities

## 🤝 Contributing

When adding new features:

1. Add the command in `queue_cli/commands/`
2. Add display functions in `queue_cli/utils/display.py`
3. Update the main CLI in `queue_cli.py`
4. Add templates if needed in `queue_cli/templates/`
5. Update this README
6. Add tests in `tests/test_queue_cli.py`

## 📝 Version History

- **v0.1.0** (Phase 1) - Initial release
  - Send command (Celery + RabbitMQ)
  - Templates command
  - Schema validation and translation
  - Rich debug output

---

**Last Updated:** 2025-10-22
**Phase:** Phase 1 Complete ✅
**Next Phase:** Phase 2 - Monitoring Commands
