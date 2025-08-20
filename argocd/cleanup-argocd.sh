#!/bin/bash

echo "🧹 Cleaning up ArgoCD installation..."

# Delete ArgoCD applications first
echo "📦 Deleting ArgoCD applications..."
kubectl delete -f argocd/applications/ --ignore-not-found=true

# Wait for applications to be cleaned up
echo "⏳ Waiting for applications to be cleaned up..."
sleep 10

# Delete ArgoCD installation
echo "🗑️  Deleting ArgoCD installation..."
kubectl delete -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml --ignore-not-found=true

# Delete ArgoCD namespace
echo "📁 Deleting ArgoCD namespace..."
kubectl delete namespace argocd --ignore-not-found=true

echo "✅ ArgoCD cleanup complete!"

echo ""
echo "📋 Verify cleanup:"
echo "kubectl get namespaces | grep argocd"
echo "kubectl get applications -A"