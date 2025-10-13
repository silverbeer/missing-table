# Phase 1: Message Queue Fundamentals

**Status:** 🚀 In Progress
**Duration:** 3-4 days
**Learning Goals:** RabbitMQ basics, Celery task execution, message flow understanding

---

## Overview

In this phase, you'll get hands-on experience with RabbitMQ and Celery by deploying them to your local K3s cluster and creating your first distributed task. This is a foundational learning experience—take time to explore and understand each component.

**What You'll Build:**
- Standalone RabbitMQ server with Management UI
- Redis for Celery result storage
- A simple "Hello World" Celery application
- Your first distributed task that processes through RabbitMQ

**What You'll Learn:**
- How message queues work (publish/subscribe pattern)
- RabbitMQ concepts: queues, exchanges, routing keys, bindings
- Celery task lifecycle from submission to completion
- How to observe message flow in real-time

---

## Prerequisites

Before starting, ensure:

- [ ] Rancher Desktop is installed on your Mac
- [ ] You're on the `feature/rabbitmq-celery-integration` branch
- [ ] You have kubectl and helm installed
- [ ] You understand basic Kubernetes concepts (pods, services, deployments)

---

## Step 1: Start Local K3s Cluster

### 1.1 Launch Rancher Desktop

**Action Required:** You need to manually start Rancher Desktop

1. Open **Rancher Desktop** application from Applications folder
2. Wait for the status to show "Kubernetes is running" (2-3 minutes)
3. Verify it started by looking for the Rancher Desktop icon in your menu bar

### 1.2 Verify Cluster is Running

Once Rancher Desktop shows "Kubernetes is running":

```bash
# Switch to Rancher Desktop context
kubectl config use-context rancher-desktop

# Verify node is ready
kubectl get nodes
```

**Expected Output:**
```
NAME                   STATUS   ROLES                  AGE   VERSION
lima-rancher-desktop   Ready    control-plane,master   5d    v1.29.0+k3s1
```

**If you see "connection refused":** Rancher Desktop is not fully started yet. Wait another minute and try again.

### 1.3 Understanding Your K3s Cluster

**What is K3s?**
- Lightweight Kubernetes distribution (uses ~512MB RAM vs ~4GB for full k8s)
- Perfect for local development and edge computing
- All Kubernetes features with smaller footprint
- Single binary, easy to install and manage

**Rancher Desktop vs Docker Desktop:**
| Feature | Rancher Desktop | Docker Desktop |
|---------|----------------|----------------|
| Kubernetes | K3s (lightweight) | Full Kubernetes |
| Container Runtime | containerd or dockerd | dockerd only |
| Open Source | ✅ Yes | ⚠️ Freemium |
| Resource Usage | Lower | Higher |

**Why We're Using Local K3s:**
- ✅ **Cost:** $0 vs $72/month on GKE
- ✅ **Speed:** No cloud deployment delays
- ✅ **Learning:** Full control over Kubernetes environment
- ✅ **Offline:** Works without internet connection

---

## Step 2: Deploy RabbitMQ

### 2.1 Understanding RabbitMQ

**What is RabbitMQ?**
- Message broker that implements AMQP (Advanced Message Queuing Protocol)
- Accepts messages from publishers, routes them to queues, delivers to consumers
- Think of it like a post office: you drop off a letter (message), it sorts and delivers it

**Key Concepts:**
- **Producer:** Application that sends messages (match-scraper)
- **Queue:** Buffer that stores messages until consumed
- **Consumer:** Application that receives messages (Celery worker)
- **Exchange:** Routing logic that determines which queue(s) get the message
- **Binding:** Link between exchange and queue with routing rules

**Message Flow Diagram:**
```
Producer (match-scraper)
    |
    | publish message
    v
Exchange (determines routing)
    |
    | route based on key
    v
Queue (stores message)
    |
    | consume message
    v
Consumer (Celery worker)
```

### 2.2 Create Namespace

Organize resources in a dedicated namespace:

```bash
# Create namespace for messaging infrastructure
kubectl create namespace messaging

# Verify it was created
kubectl get namespaces | grep messaging
```

**Why Namespaces?**
- **Isolation:** Separate messaging components from other apps
- **Organization:** Easy to see all related resources
- **Resource Limits:** Can set quotas per namespace
- **Easy Cleanup:** Delete namespace = delete all resources inside

### 2.3 Deploy RabbitMQ using Bitnami Helm Chart

We'll use the Bitnami Helm chart for a production-ready RabbitMQ setup:

```bash
# Add Bitnami Helm repository (if not already added)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Deploy RabbitMQ
helm install rabbitmq bitnami/rabbitmq \
  --namespace messaging \
  --set auth.username=admin \
  --set auth.password=admin123 \
  --set persistence.enabled=false \
  --set replicaCount=1 \
  --set service.type=ClusterIP \
  --set metrics.enabled=true

# Watch the deployment
kubectl get pods -n messaging -w
```

**Press Ctrl+C** when you see the RabbitMQ pod status change to `Running` and `1/1` ready.

**Configuration Explained:**
- `auth.username/password`: Credentials for Management UI and clients (we'll use secure secrets in Phase 2)
- `persistence.enabled=false`: No persistent storage for Phase 1 (we'll add this in Phase 2 with StatefulSets)
- `replicaCount=1`: Single instance (we'll explore clustering later)
- `service.type=ClusterIP`: Internal-only access (we'll use port-forward)
- `metrics.enabled=true`: Prometheus metrics for observability (Phase 5)

### 2.4 Verify RabbitMQ is Running

```bash
# Check pod status
kubectl get pods -n messaging

# Check RabbitMQ logs
kubectl logs -f deployment/rabbitmq -n messaging
```

**Expected Log Output:**
```
2025-10-11 18:40:00 [info] <0.9.0> Server startup complete; 0 plugins started.
2025-10-11 18:40:00 [info] <0.9.0> Management plugin: HTTP (non-TLS) listener started on port 15672
```

**Look for:**
- ✅ "Server startup complete"
- ✅ "Management plugin: HTTP listener started on port 15672"
- ❌ Any ERROR or CRASH messages (these indicate problems)

---

## Step 3: Access RabbitMQ Management UI

### 3.1 Set Up Port Forwarding

The Management UI is running inside the cluster. We need to forward it to your local machine:

```bash
# Forward RabbitMQ Management UI to localhost:15672
kubectl port-forward svc/rabbitmq -n messaging 15672:15672
```

**Leave this terminal open!** Port-forward runs in the foreground. Open a new terminal for other commands.

### 3.2 Access Management UI

Open your browser and navigate to:
```
http://localhost:15672
```

**Login Credentials:**
- Username: `admin`
- Password: `admin123`

### 3.3 Explore the Management UI

Take 10-15 minutes to explore:

#### Overview Tab
- **Totals:** See message rates (publish/deliver)
- **Nodes:** Your RabbitMQ server instance
- **Ports and Contexts:** AMQP (5672) for client connections, HTTP (15672) for UI

#### Queues Tab
- Currently empty (we'll create queues in Step 5)
- This is where messages are stored before consumption

#### Exchanges Tab
- **Default exchanges already exist:**
  - `(AMQP default)`: Direct delivery to queues
  - `amq.direct`: Direct routing by routing key
  - `amq.fanout`: Broadcast to all bound queues
  - `amq.topic`: Pattern-based routing

#### Connections Tab
- Shows active client connections (none yet)

#### Channels Tab
- Channels are lightweight connections within a single TCP connection

**Learning Exercise:**
1. Click on the `amq.direct` exchange
2. Read the description and note the "Type: direct"
3. Click on the "Bindings" section—it's empty because no queues are bound yet

---

## Step 4: Deploy Redis

### 4.1 Understanding Redis in Our Stack

**What is Redis?**
- In-memory data store (think super-fast key-value database)
- Used by Celery to store task results and state

**Why Redis for Celery?**
- ✅ **Fast:** In-memory = microsecond response times
- ✅ **Simple:** Key-value store perfect for task results
- ✅ **Reliable:** Persistence options for durability
- ✅ **Lightweight:** Low resource usage

**Celery Result Flow:**
```
Celery Worker completes task
    |
    | store result
    v
Redis (result backend)
    |
    | query result
    v
Application (checks task status)
```

### 4.2 Deploy Redis

```bash
# Deploy Redis using Bitnami Helm chart
helm install redis bitnami/redis \
  --namespace messaging \
  --set auth.enabled=false \
  --set architecture=standalone \
  --set master.persistence.enabled=false

# Watch the deployment
kubectl get pods -n messaging -w
```

**Press Ctrl+C** when Redis pod is `Running` and `1/1` ready.

**Configuration Explained:**
- `auth.enabled=false`: No password (we'll add authentication in Phase 2)
- `architecture=standalone`: Single instance (vs master-replica)
- `persistence.enabled=false`: No persistent storage for Phase 1

### 4.3 Verify Redis is Running

```bash
# Check pod status
kubectl get pods -n messaging | grep redis

# Test Redis connectivity
kubectl run redis-client --rm -it --restart=Never \
  --namespace messaging \
  --image bitnami/redis:latest \
  -- redis-cli -h redis-master

# At the redis prompt, type:
# PING
# (should respond with PONG)
# exit
```

**Expected Output:**
```
redis-master:6379> PING
PONG
redis-master:6379> exit
pod "redis-client" deleted
```

---

## Step 5: Create Hello World Celery Application

### 5.1 Understanding Celery

**What is Celery?**
- Distributed task queue system for Python
- Allows you to run code asynchronously in separate worker processes
- Handles task distribution, execution, retries, and result storage

**Celery Components:**
- **Client:** Submits tasks (e.g., your web app)
- **Broker:** Message queue that holds tasks (RabbitMQ)
- **Worker:** Executes tasks (separate process)
- **Result Backend:** Stores task results (Redis)

**Task Lifecycle:**
```
1. Client calls task.delay()
2. Celery serializes task and publishes to RabbitMQ
3. Worker picks up task from queue
4. Worker executes task function
5. Worker stores result in Redis
6. Client can query result by task ID
```

### 5.2 Set Up Python Environment

Create a directory for our hello world app:

```bash
# Create directory
mkdir -p ~/rabbitmq-celery-learning
cd ~/rabbitmq-celery-learning

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Celery and dependencies
pip install celery[redis] redis
```

**Dependencies Explained:**
- `celery`: Core Celery library
- `celery[redis]`: Redis support for result backend
- `redis`: Python Redis client

### 5.3 Create Celery Application

Create `celery_app.py`:

```python
# celery_app.py
from celery import Celery
import time

# Configure Celery app
app = Celery(
    'hello_world',
    broker='amqp://admin:admin123@localhost:5672//',  # RabbitMQ connection
    backend='redis://localhost:6379/0'                # Redis connection
)

# Configure Celery settings
app.conf.update(
    task_serializer='json',           # Serialize tasks as JSON
    accept_content=['json'],          # Only accept JSON content
    result_serializer='json',         # Serialize results as JSON
    timezone='UTC',                   # Use UTC timezone
    enable_utc=True,                  # Enable UTC
    task_track_started=True,          # Track when tasks start
    result_expires=3600,              # Results expire after 1 hour
)

# Define our first task
@app.task(name='tasks.hello')
def hello_task(name: str):
    """
    A simple hello world task that takes a name and returns a greeting.

    This task demonstrates:
    - Basic task definition with @app.task decorator
    - Task naming for easy identification
    - Simple input/output
    - Simulated processing time
    """
    print(f"[Task Started] Processing hello for: {name}")

    # Simulate some work
    time.sleep(2)

    result = f"Hello, {name}! This message was processed by Celery."
    print(f"[Task Completed] Result: {result}")

    return result

# Define a more complex task
@app.task(name='tasks.add')
def add_task(x: int, y: int):
    """
    A simple addition task for demonstrating task chaining and error handling.
    """
    print(f"[Add Task] Computing {x} + {y}")
    result = x + y
    print(f"[Add Task] Result: {result}")
    return result

if __name__ == '__main__':
    # This allows running the worker directly
    print("To start the Celery worker, run:")
    print("celery -A celery_app worker --loglevel=info")
```

**Code Walkthrough:**

1. **Celery App Creation:**
   - `broker='amqp://admin:admin123@localhost:5672//'`: RabbitMQ connection string
     - `amqp`: Protocol (Advanced Message Queuing Protocol)
     - `admin:admin123`: Username and password
     - `localhost:5672`: RabbitMQ host and port (we'll port-forward this)
     - `//`: Default virtual host

2. **Configuration:**
   - `task_serializer='json'`: Convert Python objects to JSON for transmission
   - `task_track_started=True`: Update task state when it begins execution
   - `result_expires=3600`: Auto-delete results after 1 hour to save memory

3. **Task Definition:**
   - `@app.task`: Decorator that registers the function as a Celery task
   - `name='tasks.hello'`: Explicit name (useful for calling from other languages)
   - Function body: Regular Python code that runs in the worker

### 5.4 Create Task Submitter

Create `submit_task.py`:

```python
# submit_task.py
from celery_app import hello_task, add_task
import time

def main():
    """
    Submit tasks to the Celery queue and monitor their execution.
    """
    print("=" * 60)
    print("Celery Hello World - Task Submitter")
    print("=" * 60)
    print()

    # Submit hello task
    print("📤 Submitting 'hello' task...")
    result = hello_task.delay("World")
    print(f"✅ Task submitted! Task ID: {result.id}")
    print(f"🔍 Task state: {result.state}")
    print()

    # Wait for result
    print("⏳ Waiting for task to complete...")
    try:
        output = result.get(timeout=10)  # Wait up to 10 seconds
        print(f"✅ Task completed!")
        print(f"📊 Result: {output}")
    except Exception as e:
        print(f"❌ Task failed: {e}")
    print()

    # Submit addition task
    print("📤 Submitting 'add' task...")
    result2 = add_task.delay(42, 58)
    print(f"✅ Task submitted! Task ID: {result2.id}")
    print()

    print("⏳ Waiting for task to complete...")
    try:
        output2 = result2.get(timeout=10)
        print(f"✅ Task completed!")
        print(f"📊 Result: {output2}")
    except Exception as e:
        print(f"❌ Task failed: {e}")
    print()

    print("=" * 60)
    print("✨ All tasks completed!")
    print("=" * 60)

if __name__ == '__main__':
    main()
```

**Code Walkthrough:**

1. **Calling Tasks:**
   - `hello_task.delay("World")`: Asynchronous call (returns immediately)
   - `hello_task("World")`: Synchronous call (runs locally, no queue)
   - Always use `.delay()` or `.apply_async()` for distributed execution

2. **AsyncResult Object:**
   - `result.id`: Unique task ID (UUID)
   - `result.state`: Current state (PENDING, STARTED, SUCCESS, FAILURE)
   - `result.get(timeout=10)`: Block until result is ready (with timeout)

3. **Task States:**
   - `PENDING`: Task submitted but not started
   - `STARTED`: Worker has begun processing
   - `SUCCESS`: Task completed successfully
   - `FAILURE`: Task raised an exception
   - `RETRY`: Task will be retried

---

## Step 6: Run Your First Celery Task

### 6.1 Set Up Port Forwards

You need TWO port forwards running simultaneously. Open two new terminal windows:

**Terminal 1 - RabbitMQ AMQP:**
```bash
kubectl port-forward svc/rabbitmq -n messaging 5672:5672
```

**Terminal 2 - Redis:**
```bash
kubectl port-forward svc/redis-master -n messaging 6379:6379
```

**Leave both terminals open!**

### 6.2 Start Celery Worker

In a third terminal:

```bash
cd ~/rabbitmq-celery-learning
source venv/bin/activate

# Start Celery worker
celery -A celery_app worker --loglevel=info
```

**What You Should See:**
```
 -------------- celery@your-hostname v5.x.x
---- **** -----
--- * ***  * -- Darwin-XX.X.X-arm64
-- * - **** ---
- ** ---------- [config]
- ** ---------- .> app:         hello_world:0x...
- ** ---------- .> transport:   amqp://admin:**@localhost:5672//
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 8 (prefork)
-- ******* ---- .> task events: OFF
--- ***** -----
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery

[tasks]
  . tasks.add
  . tasks.hello

[2025-10-11 18:45:00,123: INFO/MainProcess] Connected to amqp://admin:**@localhost:5672//
[2025-10-11 18:45:00,456: INFO/MainProcess] mingle: searching for neighbors
[2025-10-11 18:45:01,789: INFO/MainProcess] mingle: all alone
[2025-10-11 18:45:01,890: INFO/MainProcess] celery@your-hostname ready.
```

**Important Lines:**
- ✅ `.> transport: amqp://...` - Connected to RabbitMQ
- ✅ `.> results: redis://...` - Connected to Redis
- ✅ `.> concurrency: 8` - 8 worker processes ready
- ✅ `[tasks]` section lists your tasks
- ✅ `celery@your-hostname ready` - Worker is waiting for tasks

**Leave this terminal open!** The worker must run to process tasks.

### 6.3 Submit Tasks

In a **fourth** terminal:

```bash
cd ~/rabbitmq-celery-learning
source venv/bin/activate

# Run the task submitter
python submit_task.py
```

**Expected Output:**
```
============================================================
Celery Hello World - Task Submitter
============================================================

📤 Submitting 'hello' task...
✅ Task submitted! Task ID: 12345678-1234-1234-1234-123456789abc
🔍 Task state: PENDING

⏳ Waiting for task to complete...
✅ Task completed!
📊 Result: Hello, World! This message was processed by Celery.

📤 Submitting 'add' task...
✅ Task submitted! Task ID: 87654321-4321-4321-4321-cba987654321

⏳ Waiting for task to complete...
✅ Task completed!
📊 Result: 100

============================================================
✨ All tasks completed!
============================================================
```

### 6.4 Observe in Worker Terminal

Switch back to the worker terminal. You should see:

```
[2025-10-11 18:50:00,123: INFO/MainProcess] Task tasks.hello[12345678-...] received
[Task Started] Processing hello for: World
[Task Completed] Result: Hello, World! This message was processed by Celery.
[2025-10-11 18:50:02,456: INFO/ForkPoolWorker-1] Task tasks.hello[12345678-...] succeeded in 2.01s: 'Hello, World! This message was processed by Celery.'

[2025-10-11 18:50:03,123: INFO/MainProcess] Task tasks.add[87654321-...] received
[Add Task] Computing 42 + 58
[Add Task] Result: 100
[2025-10-11 18:50:03,456: INFO/ForkPoolWorker-2] Task tasks.add[87654321-...] succeeded in 0.01s: 100
```

**What Happened:**
1. `submit_task.py` serialized the task and sent it to RabbitMQ
2. RabbitMQ stored the message in the `celery` queue
3. Celery worker pulled the message from RabbitMQ
4. Worker executed the `hello_task` function
5. Worker stored the result in Redis
6. `submit_task.py` retrieved the result from Redis

---

## Step 7: Observe Message Flow in RabbitMQ UI

### 7.1 View the Queue

Go back to your browser at `http://localhost:15672`:

1. Click **Queues** tab
2. You should see a queue named `celery`
3. Click on the `celery` queue name

**Queue Details:**
- **Messages:** Currently 0 (tasks were processed immediately)
- **Message rates:** Shows publish/deliver rates over time
- **Consumers:** Should show 1 consumer (your Celery worker)

### 7.2 Submit More Tasks and Watch

Keep the RabbitMQ UI open and submit tasks rapidly:

```bash
# In your submit terminal, run multiple times quickly
python submit_task.py &
python submit_task.py &
python submit_task.py &
```

Quickly switch to the RabbitMQ UI and watch the **Overview** tab:
- **Message rates** graph shows publish/deliver spikes
- **Queue** page shows messages briefly appear then disappear

**This is the power of message queues!** Even if you submit 100 tasks at once, they queue up and workers process them in order.

### 7.3 Test Worker Failure Recovery

Let's see what happens when workers go down:

1. **Stop the Celery worker** (Ctrl+C in worker terminal)
2. **Submit several tasks:** `python submit_task.py` (will hang waiting)
3. **Check RabbitMQ UI:** Queue depth increases! Messages are waiting
4. **Restart worker:** `celery -A celery_app worker --loglevel=info`
5. **Watch:** Worker immediately processes all queued messages
6. **Check submit_task.py:** Gets results and completes!

**This demonstrates:**
- ✅ Messages are **durable** (survived worker crash)
- ✅ No data loss when workers are unavailable
- ✅ Automatic recovery when workers return

---

## Step 8: Understanding What You Built

### 8.1 Architecture Diagram

```
┌─────────────────┐
│  submit_task.py │  (Client)
│  (Producer)     │
└────────┬────────┘
         │
         │ 1. Task submission via .delay()
         │    (serializes to JSON)
         ▼
┌─────────────────┐
│   RabbitMQ      │  (Message Broker)
│   Port: 5672    │
│   Queue: celery │
└────────┬────────┘
         │
         │ 2. Worker polls for messages
         │    (AMQP protocol)
         ▼
┌─────────────────┐
│  Celery Worker  │  (Consumer)
│  8 processes    │
└────────┬────────┘
         │
         │ 3. Task execution
         │    hello_task(name="World")
         ▼
┌─────────────────┐
│     Redis       │  (Result Backend)
│   Port: 6379    │
│   Results stored│
└────────┬────────┘
         │
         │ 4. Client retrieves result
         │    result.get()
         ▼
┌─────────────────┐
│  submit_task.py │  (Client)
│  Prints result  │
└─────────────────┘
```

### 8.2 Key Concepts Learned

#### Message Queue Pattern

**Problem:** Direct HTTP calls are:
- Synchronous (client waits for response)
- No automatic retries
- Single point of failure
- Hard to scale

**Solution:** Message queues provide:
- Asynchronous (client doesn't wait)
- Automatic retries (configurable)
- Durability (messages survive crashes)
- Easy to scale (add more workers)

#### Task Distribution

With 8 worker processes (`concurrency: 8`):
- Tasks are distributed round-robin across workers
- If one worker is busy, others pick up new tasks
- Vertical scaling: Increase `--concurrency=16`
- Horizontal scaling: Start workers on different machines

#### Result Backends

**Why separate result storage (Redis)?**
- RabbitMQ is optimized for **message delivery**, not storage
- Redis is optimized for **fast key-value lookups**
- Results can be large, don't want to clog message queue
- Results can be queried multiple times (messages consumed once)

#### Acknowledgments

When a worker receives a message:
1. RabbitMQ marks it as "unacknowledged"
2. Worker processes the task
3. Worker sends ACK (acknowledgment) to RabbitMQ
4. RabbitMQ deletes the message

**If worker crashes before ACK:**
- RabbitMQ re-queues the message
- Another worker picks it up
- Task gets retried automatically

---

## Step 9: Experiments and Learning

### 9.1 Experiment 1: Task Arguments

Modify `submit_task.py` to submit tasks with different arguments:

```python
# Try these:
hello_task.delay("Alice")
hello_task.delay("Bob")
hello_task.delay("Charlie")

add_task.delay(100, 200)
add_task.delay(999, 1)
```

**Observe:** Each task is independent and processes with its own arguments.

### 9.2 Experiment 2: Task Serialization

Add a print statement to see what's sent to RabbitMQ:

```python
# In submit_task.py, add before result.get():
import json
print("Task metadata:", json.dumps({
    'id': result.id,
    'state': result.state,
    'task_name': result.task_name,
}indent=2))
```

**Observe:** Tasks are identified by UUID, state tracked through lifecycle.

### 9.3 Experiment 3: Increasing Concurrency

Stop the worker and restart with more workers:

```bash
celery -A celery_app worker --loglevel=info --concurrency=16
```

Submit many tasks at once:

```bash
for i in {1..20}; do python submit_task.py & done
```

**Observe:** Tasks complete faster with more workers processing in parallel.

### 9.4 Experiment 4: Task Failures

Add a task that fails:

```python
# In celery_app.py, add:
@app.task(name='tasks.divide')
def divide_task(x: int, y: int):
    """Task that might fail with division by zero."""
    print(f"[Divide Task] Computing {x} / {y}")
    result = x / y  # Will raise ZeroDivisionError if y=0
    return result

# In submit_task.py, add:
result3 = divide_task.delay(10, 0)
try:
    output3 = result3.get(timeout=5)
except Exception as e:
    print(f"❌ Task failed as expected: {e}")
```

**Observe:**
- Worker logs show the exception
- Task state becomes `FAILURE`
- Exception is stored in Redis
- Client can handle the failure gracefully

---

## Step 10: Cleanup and Documentation

### 10.1 Stop All Services

When done experimenting:

1. **Stop Celery worker:** Ctrl+C in worker terminal
2. **Stop port forwards:** Ctrl+C in both port-forward terminals
3. **Keep RabbitMQ and Redis running** in K3s (we'll use in Phase 2)

### 10.2 Create Learning Summary

Create a file documenting what you learned:

```bash
cd ~/rabbitmq-celery-learning
cat > LEARNINGS.md << 'EOF'
# Phase 1 Learnings

## Key Concepts

### Message Queues
- **Purpose:** Decouple producers from consumers
- **Benefits:** Async processing, reliability, scalability
- **Pattern:** Producer → Queue → Consumer

### RabbitMQ
- **Role:** Message broker (the post office)
- **Key components:** Exchanges, queues, bindings
- **Protocol:** AMQP (port 5672)
- **Management UI:** HTTP interface (port 15672)

### Celery
- **Role:** Distributed task processing framework
- **Components:** Client, worker, broker, result backend
- **Task states:** PENDING → STARTED → SUCCESS/FAILURE
- **Concurrency:** Multiple worker processes handle tasks in parallel

### Redis
- **Role:** Result backend (fast key-value store)
- **Why separate:** Optimized for reads, not message routing
- **Task results:** Stored by task ID, expire after TTL

## Experiments Conducted

1. ✅ Deployed RabbitMQ and Redis to local K3s
2. ✅ Created Hello World Celery application
3. ✅ Submitted tasks and observed execution
4. ✅ Watched message flow in RabbitMQ UI
5. ✅ Tested worker failure recovery
6. ✅ Experimented with concurrency
7. ✅ Tested task failures and error handling

## Questions Answered

**Q: What happens if a worker crashes during task execution?**
A: RabbitMQ re-queues the message, another worker picks it up.

**Q: How do workers avoid processing the same task twice?**
A: Message acknowledgments (ACK). Worker ACKs after completion, RabbitMQ deletes message.

**Q: Can I have multiple worker machines?**
A: Yes! All workers connect to the same RabbitMQ, tasks distributed automatically.

**Q: What if RabbitMQ fills up with messages?**
A: Can set max queue depth, dead letter queues for failed messages, monitoring alerts.

## Next Steps

Phase 2 will cover:
- Creating a Helm chart for RabbitMQ/Redis/Celery
- Adding persistent storage (StatefulSets)
- Production-ready configuration
- Secure credentials with Kubernetes Secrets
EOF
```

### 10.3 Commit Your Learning Code

```bash
cd ~/rabbitmq-celery-learning

# Initialize git
git init
git add .
git commit -m "Phase 1: Hello World Celery application

Learning project demonstrating:
- Basic Celery task definition and execution
- RabbitMQ message queue integration
- Redis result backend
- Task submission and result retrieval
- Message flow observation

Files:
- celery_app.py: Celery application with hello/add tasks
- submit_task.py: Task submitter client
- LEARNINGS.md: Key concepts and experiments
"
```

---

## Step 11: Verification Checklist

Before moving to Phase 2, verify you can:

- [ ] Start Rancher Desktop and verify K3s cluster
- [ ] Deploy RabbitMQ and Redis using Helm charts
- [ ] Access RabbitMQ Management UI via port-forward
- [ ] Create a Celery application with custom tasks
- [ ] Submit tasks using `.delay()` method
- [ ] Start Celery worker and see it process tasks
- [ ] Retrieve task results using `.get()` method
- [ ] Observe message flow in RabbitMQ UI
- [ ] Explain the flow: Client → RabbitMQ → Worker → Redis → Client
- [ ] Handle task failures gracefully

**If you can do all of the above, you're ready for Phase 2!** ✅

---

## Troubleshooting

### Issue: "connection refused" to RabbitMQ/Redis

**Cause:** Port-forward not running or wrong port

**Solution:**
```bash
# Verify services exist
kubectl get svc -n messaging

# Ensure port-forwards are running
kubectl port-forward svc/rabbitmq -n messaging 5672:5672 &
kubectl port-forward svc/redis-master -n messaging 6379:6379 &
```

### Issue: Worker shows "No module named 'celery_app'"

**Cause:** Running from wrong directory or venv not activated

**Solution:**
```bash
cd ~/rabbitmq-celery-learning
source venv/bin/activate
celery -A celery_app worker --loglevel=info
```

### Issue: Tasks stay in PENDING state forever

**Cause:** Worker not running or not connected to broker

**Solution:**
1. Verify worker is running: Check for "celery@hostname ready" message
2. Verify connection: Check worker logs for "Connected to amqp://..."
3. Verify queue: RabbitMQ UI should show 1 consumer on `celery` queue

### Issue: Management UI shows "Login failed"

**Cause:** Wrong credentials or RabbitMQ not fully started

**Solution:**
1. Verify credentials: `admin` / `admin123`
2. Check RabbitMQ logs: `kubectl logs deployment/rabbitmq -n messaging`
3. Restart port-forward: Sometimes the connection gets stale

### Issue: Tasks execute but results never retrieved

**Cause:** Redis connection problem or result expired

**Solution:**
1. Check Redis port-forward is running
2. Test Redis: `redis-cli -h localhost PING` (should return PONG)
3. Check result expiration setting: `result_expires=3600` (1 hour)

---

## Learning Resources

### RabbitMQ
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html) - Official getting started guide
- [AMQP Concepts](https://www.rabbitmq.com/tutorials/amqp-concepts.html) - Understanding the protocol
- [Management UI Guide](https://www.rabbitmq.com/management.html) - UI features explained

### Celery
- [Celery Documentation](https://docs.celeryq.dev/) - Official docs
- [Task Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#tips-and-best-practices) - Production tips
- [Monitoring Guide](https://docs.celeryq.dev/en/stable/userguide/monitoring.html) - Observability

### Kubernetes
- [K3s Documentation](https://docs.k3s.io/) - Lightweight Kubernetes
- [Port Forwarding](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/) - Accessing cluster services

---

## What's Next?

**Phase 2: Helm Chart Development** (4-5 days)

In Phase 2, you'll:
- Package RabbitMQ, Redis, and Celery workers into a single Helm chart
- Add persistent storage with StatefulSets (data survives pod restarts)
- Implement production-ready configuration (resource limits, health checks)
- Manage secrets securely with Kubernetes Secrets
- Create values files for different environments

**Get ready to:**
- Learn Helm templating (Go templates)
- Understand StatefulSets vs Deployments
- Configure persistent volumes
- Set up liveness and readiness probes

---

**Last Updated:** 2025-10-11
**Phase Status:** 🚀 In Progress
**Next Phase:** Phase 2 - Helm Chart Development
