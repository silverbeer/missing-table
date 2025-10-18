# Understanding HTTPS and Load Balancer Architecture

> **Audience**: Students, junior developers, anyone new to production web infrastructure
> **Prerequisites**: Basic understanding of HTTP, web browsers, and servers
> **Learning Objectives**: Understand how HTTPS works, why internal traffic uses HTTP, and how load balancers protect user data

---

## Table of Contents

1. [The Big Picture](#the-big-picture)
2. [Why HTTPS Matters](#why-https-matters)
3. [Traffic Flows Explained](#traffic-flows-explained)
4. [How Load Balancers Work](#how-load-balancers-work)
5. [Internal vs External Traffic](#internal-vs-external-traffic)
6. [Common Questions](#common-questions)
7. [Advanced Topics](#advanced-topics)

---

## The Big Picture

When you access `https://missingtable.com` in your browser, your data travels through **multiple layers** before reaching the application. Understanding these layers is key to understanding modern web security.

### Quick Visual Overview

```
┌─────────────────┐
│  Your Browser   │ ← You type https://missingtable.com
│  (Chrome/Edge)  │
└────────┬────────┘
         │ ✅ HTTPS (encrypted - data is scrambled)
         ▼
┌─────────────────┐
│ Public Internet │ ← Your data crosses the internet
│  (Scary Place)  │    but it's encrypted, so safe!
└────────┬────────┘
         │ ✅ HTTPS (still encrypted)
         ▼
┌─────────────────┐
│ GCP Load        │ ← Google's servers receive your request
│ Balancer        │    Decrypts HTTPS → HTTP
└────────┬────────┘
         │ HTTP (NOT encrypted, but...)
         ▼
┌─────────────────┐
│ Private         │ ← This network is INSIDE Google's datacenter
│ Kubernetes      │    No one from the internet can see it
│ Network         │    Like a private room in a secure building
└────────┬────────┘
         │ HTTP (unencrypted but safe)
         ▼
┌─────────────────┐
│ Application     │ ← Your Flask/FastAPI backend
│ Backend Pod     │    Processes the request
└─────────────────┘
```

**Key Insight**: HTTPS encryption protects data crossing the **public internet**. Once inside a **secure private network**, encryption is optional.

---

## Why HTTPS Matters

### What is HTTPS?

**HTTP** = HyperText Transfer Protocol (how browsers talk to servers)
**HTTPS** = HTTP **Secure** (HTTP wrapped in encryption)

Think of it like:
- **HTTP**: Sending a postcard through the mail (anyone can read it)
- **HTTPS**: Sending a letter in a locked box (only the recipient can open it)

### What HTTPS Protects Against

#### ❌ Without HTTPS (HTTP only):

1. **Eavesdropping**: Anyone on the network can read your data
   ```
   User → [username: tom, password: secret123] → Server
            ↑ This is visible to anyone between you and the server!
   ```

2. **Man-in-the-Middle Attacks**: Attackers can intercept and modify requests
   ```
   User → [transfer $100 to account X] → Attacker → [transfer $10,000 to attacker!] → Server
   ```

3. **Identity Theft**: Can't verify you're talking to the real website
   ```
   User → "Is this really missingtable.com?" → ??? (Could be a fake site!)
   ```

#### ✅ With HTTPS:

1. **Encryption**: Data is scrambled, unreadable to eavesdroppers
2. **Integrity**: Data can't be modified without detection
3. **Authentication**: Proves the server is who they say they are (SSL certificate)

### Real-World Example

Imagine logging into Missing Table:

**Without HTTPS:**
```http
POST http://missingtable.com/api/auth/login
Content: {"username": "tom", "password": "mypassword"}

^ Anyone on the coffee shop WiFi can see this! 😱
```

**With HTTPS:**
```http
POST https://missingtable.com/api/auth/login
Content: [encrypted gibberish: xK$9mP#qR...]

^ Encrypted! Coffee shop snooper sees nothing useful ✅
```

---

## Traffic Flows Explained

### Flow 1: User Browser → Application (HTTPS)

This is the **most important** flow to secure because data crosses the **public internet**.

```
Step 1: User types https://missingtable.com/api/standings
        │
        ▼
Step 2: Browser establishes secure connection (TLS handshake)
        - Browser: "Show me your certificate"
        - Server: "Here's my certificate (proves I'm missingtable.com)"
        - Browser: "Certificate valid! Let's use encryption"
        - Both agree on encryption keys
        │
        ▼
Step 3: Browser sends encrypted request
        GET /api/standings
        Encrypted as: 8f3n2k9x0q... (unreadable gibberish)
        │
        ▼
Step 4: Travels across public internet (WiFi, ISP, routers, cables)
        ⚠️  Attackers can see traffic, but it's encrypted
        ✅  Can't read it, can't modify it
        │
        ▼
Step 5: Reaches Google Cloud Load Balancer
        - Decrypts the request (has the private key)
        - Now it's plain HTTP inside Google's secure network
```

**Why decryption happens at the load balancer:**
- Load balancer has the SSL certificate (the "keys to decrypt")
- Once inside Google's datacenter, traffic is on a **private network**
- No need for encryption anymore (it's already physically secure)

---

### Flow 2: Load Balancer → Kubernetes Pods (HTTP)

Once decrypted, traffic moves through Google's **private network**.

```
┌──────────────────────────────────────────────────────────┐
│         Google Cloud Private Network                     │
│         (Isolated, no internet access)                   │
│                                                           │
│   ┌─────────────┐         ┌─────────────┐               │
│   │ Load        │  HTTP   │ Kubernetes  │               │
│   │ Balancer    │────────>│ Ingress     │               │
│   └─────────────┘         └──────┬──────┘               │
│                                   │ HTTP                  │
│                                   ▼                       │
│                          ┌─────────────┐                 │
│                          │ Backend     │                 │
│                          │ Service     │                 │
│                          └──────┬──────┘                 │
│                                 │ HTTP                    │
│                                 ▼                        │
│                          ┌─────────────┐                 │
│                          │ Backend Pod │                 │
│                          │ (Your App)  │                 │
│                          └─────────────┘                 │
└──────────────────────────────────────────────────────────┘
          ↑
          This entire network is PRIVATE and SECURE
          No one from the internet can access it
```

**Why HTTP is safe here:**

1. **Physical Security**: Traffic never leaves Google's datacenter
2. **Network Isolation**: Kubernetes network is separate from the internet
3. **Access Control**: Only authorized pods can communicate
4. **No Threat Surface**: Attackers can't access this network

**Analogy**:
- Public internet = talking on the street (use encryption/HTTPS)
- Private network = talking in your home (safe without encryption)

---

### Flow 3: Frontend Pod → Backend Pod (HTTP)

If you had server-side rendering (SSR), the frontend pod might call the backend. But in **Missing Table**, the frontend is a **Single Page Application (SPA)**:

```
User's Browser
    │
    │ HTTPS (Downloads HTML/CSS/JS)
    ▼
Frontend Pod (serves static files)
    │
    │ Files sent to browser
    ▼
User's Browser (runs JavaScript)
    │
    │ JavaScript makes API calls
    │ HTTPS (https://missingtable.com/api/...)
    ▼
Backend Pod
```

**The frontend pod never talks to the backend pod!**
The user's browser talks to both (via HTTPS).

---

## How Load Balancers Work

### What is a Load Balancer?

A load balancer is like a **traffic cop** for web requests. It:

1. **Receives** all incoming requests
2. **Distributes** them across multiple backend servers
3. **Terminates** HTTPS (decrypts traffic)
4. **Health checks** servers (removes broken ones from rotation)
5. **Handles** SSL certificates

### Load Balancer in Action

```
100 users visit https://missingtable.com

                    ┌──────────────┐
                    │ Load Balancer│
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    20 requests      50 requests      30 requests
          │                │                │
          ▼                ▼                ▼
    ┌─────────┐      ┌─────────┐      ┌─────────┐
    │Backend  │      │Backend  │      │Backend  │
    │Pod 1    │      │Pod 2    │      │Pod 3    │
    └─────────┘      └─────────┘      └─────────┘
```

**Benefits:**
- **Scalability**: Handle more traffic by adding pods
- **Reliability**: If one pod dies, others handle requests
- **Security**: Single point to manage SSL certificates
- **Performance**: Can cache responses, compress data

---

## Internal vs External Traffic

### External Traffic (Public Internet) - MUST be HTTPS

**Who sees it**: Your ISP, coffee shop WiFi, anyone on the network path
**Threat level**: ⚠️ HIGH - Public networks can be monitored
**Protection**: HTTPS encryption (mandatory)

```
Your Home WiFi → Your ISP → Internet Backbone → GCP → Load Balancer
     ↑              ↑              ↑
   Anyone on    Your ISP      Backbone
   your WiFi    can see       providers
   can see      traffic       can see
   traffic                    traffic

That's why we encrypt! 🔒
```

### Internal Traffic (Kubernetes Network) - HTTP is OK

**Who sees it**: Only other pods in the same cluster
**Threat level**: ✅ LOW - Trusted, isolated network
**Protection**: Network isolation, access controls

```
┌─────────────────────────────────────────┐
│  Kubernetes Cluster                     │
│  (Like a private room)                  │
│                                         │
│  Pod A ←→ Pod B                         │
│           HTTP                          │
│  No one else can see this traffic!      │
│                                         │
└─────────────────────────────────────────┘
```

---

## Common Questions

### Q: "Why don't we use HTTPS everywhere, even internally?"

**A**: You can, but it's usually unnecessary:

**Pros of internal HTTPS:**
- ✅ Defense in depth (extra security layer)
- ✅ Required for compliance (HIPAA, PCI-DSS)
- ✅ Protects against compromised pods

**Cons of internal HTTPS:**
- ❌ Performance overhead (encryption/decryption costs CPU)
- ❌ Complexity (managing internal certificates)
- ❌ Operational burden (certificate rotation, debugging)
- ❌ Overkill for most applications

**When to use internal HTTPS:**
- Multi-tenant clusters (untrusted neighbors)
- Regulatory compliance requirements
- Zero-trust security model
- Very high security requirements

**For Missing Table**: HTTP internally is **perfectly fine** and follows **industry best practices**.

---

### Q: "How does the load balancer know to redirect HTTP → HTTPS?"

**A**: The **FrontendConfig** resource tells it!

```yaml
# helm/missing-table/templates/frontendconfig.yaml
apiVersion: networking.gke.io/v1beta1
kind: FrontendConfig
spec:
  redirectToHttps:
    enabled: true
    responseCodeName: "MOVED_PERMANENTLY_DEFAULT"  # HTTP 301
```

When a user visits `http://missingtable.com`:

1. Request reaches load balancer
2. Load balancer sees it's HTTP (not HTTPS)
3. FrontendConfig says "redirect to HTTPS"
4. Load balancer responds: `HTTP/1.1 301 Moved Permanently`
5. `Location: https://missingtable.com`
6. Browser automatically follows redirect to HTTPS

---

### Q: "What's the difference between HTTP and HTTPS in the URL?"

**A**: The protocol scheme tells the browser what to use:

- `http://example.com` → HTTP (port 80, no encryption)
- `https://example.com` → HTTPS (port 443, encrypted)

**Browser behavior:**
```
http://missingtable.com
  ↓
Browser: "Use HTTP on port 80"
Browser: "Don't encrypt anything"
Browser: "Show 'Not Secure' warning"

https://missingtable.com
  ↓
Browser: "Use HTTPS on port 443"
Browser: "Establish encrypted connection"
Browser: "Show padlock 🔒 icon"
```

---

### Q: "What's an SSL certificate? Why do we need it?"

**A**: An SSL certificate is like a **driver's license for websites**.

**What it proves:**
1. **Identity**: "This is really missingtable.com" (not a fake site)
2. **Ownership**: Google verified we own the domain
3. **Public Key**: Used to establish encryption

**How it works:**

```
Step 1: Browser visits https://missingtable.com

Step 2: Server sends SSL certificate
        ┌─────────────────────────────┐
        │ SSL Certificate             │
        │ Domain: missingtable.com    │
        │ Issued to: Tom Drake        │
        │ Issued by: Google Trust CA  │ ← Trusted authority
        │ Valid: Oct 2025 - Jan 2026  │
        │ Public Key: [long string]   │
        └─────────────────────────────┘

Step 3: Browser verifies certificate
        - Is it issued by a trusted authority? ✅
        - Does the domain match? ✅
        - Is it still valid (not expired)? ✅

Step 4: Browser shows padlock 🔒
        User sees: "Connection is secure"
```

**Missing Table uses Google-managed certificates:**
- Automatic provisioning (no manual setup)
- Automatic renewal (never expires)
- Managed via `ManagedCertificate` Kubernetes resource

---

### Q: "Can someone intercept traffic between the load balancer and my pods?"

**A**: Technically possible, but **highly unlikely**:

**Why it's hard:**

1. **Physical Access Required**: Attacker needs access to Google's datacenter
   - Armed guards, biometric locks, surveillance
   - Probably easier to rob a bank 🏦

2. **Network Isolation**: Kubernetes network is logically separated
   - Software-defined networking (SDN)
   - Network policies control pod-to-pod communication
   - Can't just "plug in" to the network

3. **Encryption Available**: If needed, you can add service mesh
   - Istio, Linkerd provide automatic mTLS
   - Encrypts all pod-to-pod traffic
   - Performance cost for extra security

**For most applications**: The physical and logical security of Google's infrastructure is **more than sufficient**.

---

### Q: "What happens if my SSL certificate expires?"

**A**: With Google-managed certificates, **you don't need to worry**!

**Traditional SSL (manual):**
```
Day 0: Certificate issued (valid for 90 days)
Day 60: You get renewal reminder
Day 89: You manually renew certificate
Day 90: Old certificate expires
Day 91: If you forgot, site shows "Not Secure" ⚠️
```

**Google-managed SSL:**
```
Day 0: Certificate auto-provisioned
Day 60: Google automatically starts renewal
Day 85: New certificate issued
Day 90: Old certificate expires, new one active
You: 😴 (didn't even notice)
```

**Our setup:**
```yaml
# helm/missing-table/templates/managedcertificate.yaml
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: missing-table-prod-cert
spec:
  domains:
  - missingtable.com
  - www.missingtable.com
```

Google handles everything automatically! 🎉

---

## Advanced Topics

### Service Mesh (Optional Reading)

If you want **HTTPS everywhere** (including internal traffic), use a **service mesh**:

**What is a Service Mesh?**

A service mesh is like adding a **security guard to every conversation** between pods.

```
Without Service Mesh:
Pod A ───HTTP───> Pod B

With Service Mesh (Istio):
Pod A ───mTLS───> Sidecar Proxy ───mTLS───> Sidecar Proxy ───mTLS───> Pod B
         🔒                          🔒                          🔒
```

**Features:**
- **Automatic mTLS**: Mutual TLS between all pods (both sides verify identity)
- **Traffic Management**: Canary deployments, circuit breakers
- **Observability**: Trace every request across services
- **Security Policies**: Fine-grained access controls

**Popular Service Meshes:**
- **Istio** (feature-rich, complex)
- **Linkerd** (lightweight, easier)
- **Consul** (HashiCorp ecosystem)

**When you need it:**
- Microservices with many inter-service calls
- Compliance requirements (end-to-end encryption)
- Advanced traffic management needs
- Large teams with security concerns

**For Missing Table**: Overkill! You have ~2-3 services. Service meshes shine with 10+ microservices.

---

### TLS Termination Explained

**TLS Termination** = where HTTPS is decrypted to HTTP

```
Option 1: TLS Termination at Load Balancer (what we use)
Browser ─HTTPS─> LB ─HTTP─> Pod
         🔒      ▼ Decrypt
                 here

Option 2: TLS Termination at Pod (more complex)
Browser ─HTTPS─> LB ─HTTPS─> Pod
         🔒           🔒      ▼ Decrypt
                              here

Option 3: End-to-End TLS (service mesh)
Browser ─HTTPS─> LB ─HTTPS─> Sidecar ─HTTPS─> Pod
         🔒           🔒       🔒               ▼ Decrypt
                                               here
```

**Why terminate at load balancer?**
- ✅ **Simple**: One place to manage certificates
- ✅ **Fast**: No encryption overhead in pods
- ✅ **Standard**: Industry best practice
- ✅ **Sufficient**: Protects data over public internet

---

### HTTP/2 vs HTTP/1.1

Modern browsers use **HTTP/2** over HTTPS:

**HTTP/1.1** (old way):
```
Browser makes 10 requests for different resources
Each request opens a NEW TCP connection
Slow! 🐌
```

**HTTP/2** (modern):
```
Browser makes 10 requests
All use the SAME connection (multiplexing)
Fast! 🚀
```

**Your app automatically uses HTTP/2** when accessed via HTTPS!

Check in browser DevTools → Network → Protocol column → `h2`

---

## Testing Your HTTPS Setup

### Browser Testing

1. **Visit your site**: `https://missingtable.com`
2. **Click the padlock** 🔒 in the address bar
3. **Check certificate details**:
   - Issued by: Google Trust Services
   - Valid dates: Should show future expiration
   - Domain names: missingtable.com, www.missingtable.com

### Command Line Testing

```bash
# Test HTTPS (should work)
curl -I https://missingtable.com
# Expected: HTTP/2 200

# Test HTTP redirect (should redirect to HTTPS)
curl -I http://missingtable.com
# Expected: HTTP/1.1 301 Moved Permanently
# Expected: Location: https://missingtable.com

# Follow redirects automatically
curl -L -I http://missingtable.com
# Expected: Final response is HTTP/2 200

# Check SSL certificate details
curl -vI https://missingtable.com 2>&1 | grep -A 10 "Server certificate"
# Should show certificate info, expiration date
```

### Kubernetes Testing

```bash
# Check ManagedCertificate status
kubectl get managedcertificate -n missing-table-prod
# STATUS should be "Active"

# Check FrontendConfig
kubectl get frontendconfig -n missing-table-prod
# Should exist

# Check Ingress
kubectl describe ingress missing-table-ingress -n missing-table-prod
# Look for FrontendConfig annotation
```

---

## Key Takeaways

1. **HTTPS encrypts traffic** over the public internet (browser → load balancer)
2. **Load balancer decrypts** traffic and forwards HTTP to Kubernetes
3. **Internal traffic** (pod → pod) uses HTTP on a **private, secure network**
4. **This is standard** and follows industry best practices
5. **Your users' data is protected** with HTTPS encryption
6. **Google manages** your SSL certificates automatically

---

## Further Reading

- **Mozilla Web Security**: https://developer.mozilla.org/en-US/docs/Web/Security
- **How HTTPS Works**: https://howhttps.works/ (comic book style!)
- **Google Cloud Load Balancing**: https://cloud.google.com/load-balancing/docs
- **Kubernetes Ingress**: https://kubernetes.io/docs/concepts/services-networking/ingress/
- **GKE ManagedCertificate**: https://cloud.google.com/kubernetes-engine/docs/how-to/managed-certs

---

**Last Updated**: 2025-10-18
**Maintained By**: Tom Drake
**Feedback**: Questions? Create an issue or ask in discussions!

---

<div align="center">

[⬆ Back to Deployment Docs](README.md) | [🏠 Documentation Hub](../README.md)

</div>
