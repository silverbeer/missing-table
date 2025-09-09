#!/bin/bash

echo "🧹 Cleaning up Missing Table Kubernetes deployment using Helm..."

# Uninstall the Helm release
echo "📦 Uninstalling Helm release..."
helm uninstall missing-table -n missing-table

# Wait a moment for resources to be cleaned up
echo "⏳ Waiting for resources to be cleaned up..."
sleep 5

# Check if namespace still has resources
REMAINING_RESOURCES=$(kubectl get all -n missing-table 2>/dev/null | wc -l)
if [ "$REMAINING_RESOURCES" -gt 1 ]; then
    echo "⚠️  Some resources remain, force cleaning..."
    kubectl delete all --all -n missing-table
    kubectl delete pvc --all -n missing-table
fi

# Delete the namespace
echo "🗑️  Deleting namespace..."
kubectl delete namespace missing-table --timeout=60s

echo "✅ Cleanup complete!"

echo ""
echo "📋 Verify cleanup:"
echo "helm list -A | grep missing-table"
echo "kubectl get namespaces | grep missing-table"