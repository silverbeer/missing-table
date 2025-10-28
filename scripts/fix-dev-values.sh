#!/bin/bash
# Fix values-dev.yaml for GKE deployment
# This script updates the frontend configuration to use the Ingress URL

set -e

VALUES_FILE="./helm/missing-table/values-dev.yaml"
BACKUP_FILE="./helm/missing-table/values-dev.yaml.backup.$(date +%Y%m%d_%H%M%S)"

# Check if values-dev.yaml exists
if [ ! -f "$VALUES_FILE" ]; then
    echo "❌ Error: $VALUES_FILE not found"
    echo ""
    echo "Please copy the example file first:"
    echo "  cp helm/missing-table/values-dev.yaml.example helm/missing-table/values-dev.yaml"
    echo ""
    echo "Then fill in your actual secrets and run this script again."
    exit 1
fi

# Create backup
echo "📦 Creating backup: $BACKUP_FILE"
cp "$VALUES_FILE" "$BACKUP_FILE"

echo "🔧 Applying configuration fixes..."

# Create a temporary Python script to update the YAML
cat > /tmp/fix_values.py << 'PYEOF'
import sys
import re

# Read the file
with open('./helm/missing-table/values-dev.yaml', 'r') as f:
    content = f.read()

# Track what we need to add
needs_frontend = 'frontend:' not in content
needs_celery_disabled = 'celeryWorker:' not in content

# Build the frontend section to add/replace
frontend_config = """
# Frontend configuration
frontend:
  replicaCount: 1

  image:
    repository: us-central1-docker.pkg.dev/missing-table/missing-table/frontend
    tag: dev
    pullPolicy: Always

  env:
    nodeEnv: "production"  # Use production mode for pre-built app
    apiUrl: "https://dev.missingtable.com"  # Use Ingress URL
    vueAppDisableSecurity: "true"
    extra: {}

  # Use Dockerfile CMD (serve -s dist) instead of npm run serve
  command: []

  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi

  livenessProbe:
    initialDelaySeconds: 10
    periodSeconds: 10

  readinessProbe:
    initialDelaySeconds: 5
    periodSeconds: 5
"""

celery_config = """
# Celery Worker configuration
# Disabled for GKE - Celery runs on local K3s only
celeryWorker:
  enabled: false
  replicaCount: 1

  image:
    repository: us-central1-docker.pkg.dev/missing-table/missing-table/backend
    tag: dev

  rabbitmq:
    username: "admin"
    password: "admin123"  # pragma: allowlist secret - template value, not a real secret
    host: "messaging-rabbitmq.messaging.svc.cluster.local"
    port: 5672

  resources:
    requests:
      cpu: 250m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi
"""

# If frontend section exists, replace it
if not needs_frontend:
    # Find and replace the entire frontend section
    # This regex finds "frontend:" and everything indented under it until the next top-level key
    pattern = r'(^# Frontend configuration\s+)?^frontend:.*?(?=\n[a-zA-Z]|\Z)'
    content = re.sub(pattern, frontend_config.strip(), content, flags=re.MULTILINE | re.DOTALL)
else:
    # Add frontend section before celeryWorker or redis or at the end
    if 'celeryWorker:' in content:
        content = content.replace('celeryWorker:', frontend_config + '\nceleryWorker:')
    elif 'redis:' in content:
        content = content.replace('redis:', frontend_config + '\nredis:')
    else:
        content += '\n' + frontend_config

# Handle celeryWorker section
if not needs_celery_disabled:
    # Find and replace the entire celeryWorker section
    pattern = r'(^# Celery Worker configuration.*?\s+)?^celeryWorker:.*?(?=\n[a-zA-Z]|\Z)'
    content = re.sub(pattern, celery_config.strip(), content, flags=re.MULTILINE | re.DOTALL)
else:
    # Add celeryWorker section
    if 'redis:' in content:
        content = content.replace('redis:', celery_config + '\nredis:')
    else:
        content += '\n' + celery_config

# Write back
with open('./helm/missing-table/values-dev.yaml', 'w') as f:
    f.write(content)

print("✅ Updated values-dev.yaml successfully")
PYEOF

# Run the Python script
python3 /tmp/fix_values.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Configuration updated successfully!"
    echo ""
    echo "📝 Changes made:"
    echo "  - frontend.env.nodeEnv: 'production' (for pre-built app)"
    echo "  - frontend.env.apiUrl: 'https://dev.missingtable.com' (use Ingress URL)"
    echo "  - frontend.command: [] (use Dockerfile CMD)"
    echo "  - celeryWorker.enabled: false (disable for GKE)"
    echo ""
    echo "🔄 Next steps:"
    echo "  1. Review changes:"
    echo "     diff $BACKUP_FILE $VALUES_FILE | head -50"
    echo ""
    echo "  2. Deploy to GKE:"
    echo "     helm upgrade missing-table ./helm/missing-table -n missing-table-dev \\"
    echo "       --values ./helm/missing-table/values-dev.yaml --wait"
    echo ""
    echo "  3. Verify deployment:"
    echo "     kubectl get pods -n missing-table-dev"
    echo "     kubectl logs -l app.kubernetes.io/component=frontend -n missing-table-dev --tail=20"
    echo ""
    echo "💾 Backup saved at: $BACKUP_FILE"

    # Cleanup
    rm -f /tmp/fix_values.py
else
    echo ""
    echo "❌ Error updating configuration"
    echo "Restoring backup..."
    cp "$BACKUP_FILE" "$VALUES_FILE"
    rm -f /tmp/fix_values.py
    exit 1
fi
