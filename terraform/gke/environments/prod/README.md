# GKE Autopilot - Production Environment

**Status**: 🚧 Placeholder - Not yet configured

This directory will contain Terraform configuration for the **production** GKE Autopilot cluster.

## Setup Instructions

When you're ready to create the production environment:

1. **Copy dev configuration:**
   ```bash
   cp ../dev/*.tf .
   cp ../dev/terraform.tfvars.example .
   ```

2. **Update for production:**
   - Change `cluster_name` to `missing-table-prod`
   - Update `pods_range_name` to `gke-pods-prod`
   - Update `services_range_name` to `gke-services-prod`
   - Update labels `environment = "prod"`
   - Consider using `release_channel = "STABLE"` for production

3. **Configure terraform.tfvars:**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   vim terraform.tfvars
   ```

4. **Setup network ranges:**
   ```bash
   gcloud compute networks subnets update default \
     --region=us-central1 \
     --add-secondary-ranges=gke-pods-prod=10.8.0.0/14,gke-services-prod=10.0.64.0/20
   ```

5. **Deploy:**
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

## Production Considerations

Before deploying production:

- [ ] Set up remote state in GCS bucket
- [ ] Configure production Supabase instance
- [ ] Set up Cloud SQL (if replacing Supabase)
- [ ] Configure Load Balancer / Ingress
- [ ] Set up Cloud DNS for custom domain
- [ ] Enable Cloud Monitoring and Logging
- [ ] Configure backups and disaster recovery
- [ ] Set up CI/CD pipeline
- [ ] Document runbooks and incident response
- [ ] Review security settings and compliance

## Cost Considerations

Production costs will be higher than dev:
- Consider using Committed Use Discounts for predictable workloads
- Monitor resource usage and right-size pods
- Set up budget alerts in GCP Console
- Review GKE Autopilot pricing vs Standard for your workload

## Resources

- [GKE Production Best Practices](https://cloud.google.com/kubernetes-engine/docs/best-practices)
- [GKE Security Hardening](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster)
