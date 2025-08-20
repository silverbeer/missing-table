#!/bin/bash

echo "🚀 Installing ArgoCD in Rancher Desktop Kubernetes"
echo "=================================================="

# Create ArgoCD namespace
echo "📁 Creating ArgoCD namespace..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

# Install ArgoCD
echo "📦 Installing ArgoCD..."
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
echo "⏳ Waiting for ArgoCD to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd
kubectl wait --for=condition=available --timeout=300s deployment/argocd-repo-server -n argocd
kubectl wait --for=condition=available --timeout=300s deployment/argocd-application-controller -n argocd

# Get initial admin password
echo "🔑 Getting ArgoCD admin password..."
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

# Expose ArgoCD server via LoadBalancer (for Rancher Desktop)
echo "🌐 Exposing ArgoCD server..."
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'

# Wait for LoadBalancer to get external IP
echo "⏳ Waiting for LoadBalancer to get external IP..."
sleep 10

# Get service information
ARGOCD_SERVER_IP=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
ARGOCD_SERVER_PORT=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.spec.ports[?(@.name=="https")].port}')

if [ -z "$ARGOCD_SERVER_IP" ]; then
    ARGOCD_SERVER_IP="localhost"
fi

echo ""
echo "🎉 ArgoCD Installation Complete!"
echo "=================================="
echo ""
echo "🔗 ArgoCD Web UI: https://$ARGOCD_SERVER_IP:$ARGOCD_SERVER_PORT"
echo "👤 Username: admin"
echo "🔑 Password: $ARGOCD_PASSWORD"
echo ""
echo "📋 Useful commands:"
echo "kubectl get pods -n argocd"
echo "kubectl get svc -n argocd"
echo "kubectl logs -f deployment/argocd-server -n argocd"
echo ""
echo "🚀 Next steps:"
echo "1. Access the ArgoCD Web UI at the URL above"
echo "2. Login with admin credentials"
echo "3. Apply the application manifests:"
echo "   kubectl apply -f argocd/applications/missing-table-dev.yaml"
echo "   kubectl apply -f argocd/applications/missing-table-prod.yaml"
echo ""
echo "📖 ArgoCD CLI installation (optional):"
echo "brew install argocd"
echo "argocd login $ARGOCD_SERVER_IP:$ARGOCD_SERVER_PORT --username admin --password '$ARGOCD_PASSWORD' --insecure"