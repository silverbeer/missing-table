#!/bin/bash

# Shutdown script for Missing Table development environment
# This script stops all running services: Kubernetes deployments, Supabase, and Docker containers

set -e

echo "🛑 Shutting Down Missing Table Environment"
echo "=========================================="

# Stop Kubernetes deployments if cluster is available
echo ""
echo "📋 Checking Kubernetes cluster..."
if kubectl cluster-info >/dev/null 2>&1; then
    echo "✅ Kubernetes cluster is accessible"
    
    echo ""
    echo "🚫 Scaling down Kubernetes deployments..."
    kubectl scale deployment missing-table-backend --replicas=0 -n missing-table 2>/dev/null || echo "⚠️  Backend deployment not found or already scaled down"
    kubectl scale deployment missing-table-frontend --replicas=0 -n missing-table 2>/dev/null || echo "⚠️  Frontend deployment not found or already scaled down" 
    kubectl scale deployment missing-table-redis --replicas=0 -n missing-table 2>/dev/null || echo "⚠️  Redis deployment not found or already scaled down"
    
    echo "✅ Kubernetes deployments scaled down"
else
    echo "⚠️  Kubernetes cluster not accessible (may already be stopped)"
fi

# Kill any port-forward processes
echo ""
echo "🔌 Stopping port-forward processes..."
pkill -f "kubectl port-forward" || echo "⚠️  No port-forward processes found"

# Stop local development servers on common ports
echo ""
echo "🌐 Stopping local development servers..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "⚠️  Nothing running on port 8000"
lsof -ti:8080 | xargs kill -9 2>/dev/null || echo "⚠️  Nothing running on port 8080" 
lsof -ti:8081 | xargs kill -9 2>/dev/null || echo "⚠️  Nothing running on port 8081"
lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "⚠️  Nothing running on port 3000"

# Stop Supabase
echo ""
echo "🗄️  Stopping Supabase..."
if command -v npx >/dev/null 2>&1; then
    npx supabase stop || echo "⚠️  Supabase may already be stopped or not running"
else
    echo "⚠️  npx not found, cannot stop Supabase"
fi

# Stop any remaining Docker containers from the project
echo ""
echo "🐳 Stopping project Docker containers..."
docker ps --format "table {{.Names}}\t{{.Image}}" | grep missing-table | awk '{print $1}' | xargs -r docker stop 2>/dev/null || echo "⚠️  No missing-table containers running"

# Stop Docker Compose if docker-compose.yml exists
if [[ -f "docker-compose.yml" ]]; then
    echo ""
    echo "🐙 Stopping Docker Compose services..."
    docker-compose down 2>/dev/null || echo "⚠️  Docker Compose not running or failed to stop"
fi

echo ""
echo "🧹 Cleanup complete!"
echo ""
echo "📋 Summary of what was stopped:"
echo "   • Kubernetes deployments (scaled to 0 replicas)"
echo "   • Port-forward processes" 
echo "   • Local development servers (ports 8000, 8080, 8081, 3000)"
echo "   • Supabase local instance"
echo "   • Project Docker containers"
echo "   • Docker Compose services (if running)"
echo ""
echo "🎯 To completely shut down Kubernetes:"
echo "   • Close Rancher Desktop application"
echo "   • Or disable Kubernetes in Rancher Desktop settings"
echo ""
echo "♻️  To restart everything:"
echo "   • ./missing-table.sh start (for local development)"
echo "   • ./helm/deploy-helm.sh (for Kubernetes)"