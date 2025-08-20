#!/bin/bash

echo "🧹 Cleaning up Missing Table Kubernetes deployment..."

# Delete all resources in the missing-table namespace
kubectl delete all --all -n missing-table

# Delete PVCs
kubectl delete pvc --all -n missing-table

# Delete the namespace (this will remove everything)
kubectl delete namespace missing-table

echo "✅ Cleanup complete!"