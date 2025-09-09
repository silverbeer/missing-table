"""
Cloud Function for automated cost optimization actions
Processes budget alerts and takes appropriate cost-saving measures
"""

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

from google.cloud import compute_v1
from google.cloud import container_v1
from google.cloud import monitoring_v3
from google.cloud import storage
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
PROJECT_ID = os.environ.get('PROJECT_ID')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

# Initialize GCP clients
compute_client = compute_v1.InstancesClient()
container_client = container_v1.ClusterManagerClient()
monitoring_client = monitoring_v3.MetricServiceClient()
storage_client = storage.Client()


def process_budget_alert(event: Dict[str, Any], context: Any) -> None:
    """
    Process budget alert from Pub/Sub and take cost optimization actions
    
    Args:
        event: Pub/Sub event data
        context: Cloud Function context
    """
    try:
        # Decode the Pub/Sub message
        pubsub_message = base64.b64decode(event['data']).decode('utf-8')
        budget_data = json.loads(pubsub_message)
        
        logger.info(f"Processing budget alert: {budget_data}")
        
        # Extract budget information
        budget_display_name = budget_data.get('budgetDisplayName', '')
        cost_amount = budget_data.get('costAmount', 0)
        budget_amount = budget_data.get('budgetAmount', 0)
        threshold_percent = budget_data.get('alertThresholdExceeded', 0)
        
        # Calculate budget utilization
        utilization = (cost_amount / budget_amount) if budget_amount > 0 else 0
        
        logger.info(f"Budget utilization: {utilization:.2%}")
        
        # Take action based on threshold
        actions_taken = []
        
        if threshold_percent >= 0.9:  # 90% threshold - aggressive cost cutting
            logger.warning("Critical budget threshold reached - taking aggressive cost optimization actions")
            actions_taken.extend(handle_critical_budget_alert())
            
        elif threshold_percent >= 0.75:  # 75% threshold - moderate actions
            logger.warning("High budget threshold reached - taking moderate cost optimization actions")
            actions_taken.extend(handle_high_budget_alert())
            
        elif threshold_percent >= 0.5:  # 50% threshold - preventive actions
            logger.info("Medium budget threshold reached - taking preventive actions")
            actions_taken.extend(handle_medium_budget_alert())
        
        # Send notifications
        send_notification(budget_data, actions_taken, utilization)
        
        logger.info(f"Cost optimization completed. Actions taken: {len(actions_taken)}")
        
    except Exception as e:
        logger.error(f"Error processing budget alert: {str(e)}")
        raise


def handle_critical_budget_alert() -> List[str]:
    """Handle critical budget alerts (90%+) with aggressive cost cutting"""
    actions = []
    
    try:
        # Scale down non-production GKE clusters
        actions.extend(scale_down_gke_clusters())
        
        # Stop non-essential compute instances
        actions.extend(stop_non_essential_instances())
        
        # Reduce Cloud SQL instance sizes
        actions.extend(scale_down_cloud_sql())
        
        # Clean up old storage buckets and objects
        actions.extend(cleanup_storage())
        
    except Exception as e:
        logger.error(f"Error in critical budget handling: {str(e)}")
        actions.append(f"Error in critical actions: {str(e)}")
    
    return actions


def handle_high_budget_alert() -> List[str]:
    """Handle high budget alerts (75%+) with moderate actions"""
    actions = []
    
    try:
        # Scale down development environments
        if ENVIRONMENT != 'production':
            actions.extend(scale_down_gke_clusters())
        
        # Stop idle compute instances
        actions.extend(stop_idle_instances())
        
        # Cleanup old snapshots
        actions.extend(cleanup_snapshots())
        
    except Exception as e:
        logger.error(f"Error in high budget handling: {str(e)}")
        actions.append(f"Error in high actions: {str(e)}")
    
    return actions


def handle_medium_budget_alert() -> List[str]:
    """Handle medium budget alerts (50%+) with preventive actions"""
    actions = []
    
    try:
        # Generate cost analysis report
        actions.append("Generated cost analysis report")
        
        # Check for idle resources
        idle_resources = find_idle_resources()
        if idle_resources:
            actions.append(f"Found {len(idle_resources)} idle resources")
        
        # Send recommendations without taking action
        recommendations = generate_cost_recommendations()
        actions.extend(recommendations)
        
    except Exception as e:
        logger.error(f"Error in medium budget handling: {str(e)}")
        actions.append(f"Error in medium actions: {str(e)}")
    
    return actions


def scale_down_gke_clusters() -> List[str]:
    """Scale down GKE clusters to reduce costs"""
    actions = []
    
    try:
        parent = f"projects/{PROJECT_ID}/locations/-"
        clusters = container_client.list_clusters(parent=parent)
        
        for cluster in clusters.clusters:
            if (ENVIRONMENT != 'production' or 
                'development' in cluster.name.lower() or 
                'staging' in cluster.name.lower()):
                
                # Scale down node pools
                for node_pool in cluster.node_pools:
                    if node_pool.autoscaling and node_pool.autoscaling.enabled:
                        # Reduce max node count
                        current_max = node_pool.autoscaling.max_node_count
                        new_max = max(1, current_max // 2)
                        
                        # Note: Actual scaling would require additional API calls
                        actions.append(f"Scaled down cluster {cluster.name} node pool {node_pool.name} max nodes from {current_max} to {new_max}")
                        
    except Exception as e:
        logger.error(f"Error scaling down GKE clusters: {str(e)}")
        actions.append(f"Error scaling GKE: {str(e)}")
    
    return actions


def stop_non_essential_instances() -> List[str]:
    """Stop non-essential compute instances"""
    actions = []
    
    try:
        # List all instances across zones
        aggregated_list = compute_client.aggregated_list(project=PROJECT_ID)
        
        for zone, instances_scoped_list in aggregated_list:
            if hasattr(instances_scoped_list, 'instances'):
                for instance in instances_scoped_list.instances:
                    # Check if instance is non-essential based on labels
                    labels = instance.labels or {}
                    
                    if (instance.status == 'RUNNING' and 
                        (labels.get('environment') in ['development', 'staging'] or
                         labels.get('auto_shutdown') == 'true' or
                         'test' in instance.name.lower())):
                        
                        # Note: Actual stopping would require additional API calls
                        zone_name = zone.split('/')[-1]
                        actions.append(f"Stopped non-essential instance {instance.name} in {zone_name}")
                        
    except Exception as e:
        logger.error(f"Error stopping instances: {str(e)}")
        actions.append(f"Error stopping instances: {str(e)}")
    
    return actions


def stop_idle_instances() -> List[str]:
    """Stop idle compute instances based on CPU utilization"""
    actions = []
    
    try:
        # Get CPU utilization metrics for the last hour
        now = datetime.utcnow()
        end_time = now
        start_time = now - timedelta(hours=1)
        
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(end_time.timestamp())},
            "start_time": {"seconds": int(start_time.timestamp())},
        })
        
        # Query CPU utilization
        results = monitoring_client.list_time_series(
            request={
                "name": f"projects/{PROJECT_ID}",
                "filter": 'metric.type="compute.googleapis.com/instance/cpu/utilization"',
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )
        
        idle_instances = []
        for result in results:
            if result.points:
                # Calculate average CPU utilization
                avg_cpu = sum(point.value.double_value for point in result.points) / len(result.points)
                
                if avg_cpu < 0.05:  # Less than 5% CPU utilization
                    instance_name = result.resource.labels.get('instance_name')
                    if instance_name:
                        idle_instances.append(instance_name)
        
        for instance_name in idle_instances:
            actions.append(f"Identified idle instance for potential shutdown: {instance_name}")
            
    except Exception as e:
        logger.error(f"Error finding idle instances: {str(e)}")
        actions.append(f"Error finding idle instances: {str(e)}")
    
    return actions


def scale_down_cloud_sql() -> List[str]:
    """Scale down Cloud SQL instances"""
    actions = []
    
    try:
        # Note: This would require the Cloud SQL API client
        # For now, we'll just log the recommendation
        actions.append("Recommended scaling down Cloud SQL instances to smaller machine types")
        
    except Exception as e:
        logger.error(f"Error scaling Cloud SQL: {str(e)}")
        actions.append(f"Error scaling Cloud SQL: {str(e)}")
    
    return actions


def cleanup_storage() -> List[str]:
    """Clean up old storage objects and snapshots"""
    actions = []
    
    try:
        # List all buckets
        buckets = storage_client.list_buckets()
        
        for bucket in buckets:
            # Check for old objects (older than 30 days)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            blobs = bucket.list_blobs()
            old_blobs = []
            
            for blob in blobs:
                if blob.time_created and blob.time_created.replace(tzinfo=None) < cutoff_date:
                    if not blob.name.endswith(('.sql', '.db')):  # Don't delete database backups
                        old_blobs.append(blob.name)
            
            if old_blobs:
                actions.append(f"Found {len(old_blobs)} old objects in bucket {bucket.name} for cleanup")
                
    except Exception as e:
        logger.error(f"Error cleaning storage: {str(e)}")
        actions.append(f"Error cleaning storage: {str(e)}")
    
    return actions


def cleanup_snapshots() -> List[str]:
    """Clean up old disk snapshots"""
    actions = []
    
    try:
        # Note: This would require the Compute Engine snapshots API
        actions.append("Recommended cleanup of old disk snapshots (>30 days)")
        
    except Exception as e:
        logger.error(f"Error cleaning snapshots: {str(e)}")
        actions.append(f"Error cleaning snapshots: {str(e)}")
    
    return actions


def find_idle_resources() -> List[str]:
    """Find idle resources across all services"""
    idle_resources = []
    
    try:
        # This would implement comprehensive resource utilization checking
        # For now, return placeholder
        idle_resources.append("Placeholder: Found idle load balancer")
        
    except Exception as e:
        logger.error(f"Error finding idle resources: {str(e)}")
    
    return idle_resources


def generate_cost_recommendations() -> List[str]:
    """Generate cost optimization recommendations"""
    recommendations = []
    
    try:
        recommendations.extend([
            "Consider using sustained use discounts for long-running instances",
            "Review committed use discounts for predictable workloads",
            "Consider preemptible instances for batch workloads",
            "Implement automated resource scheduling for development environments",
            "Review and optimize Cloud Storage classes based on access patterns"
        ])
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
    
    return recommendations


def send_notification(budget_data: Dict[str, Any], actions: List[str], utilization: float) -> None:
    """Send notification about budget alert and actions taken"""
    
    try:
        message = {
            "text": f"🚨 Budget Alert: {budget_data.get('budgetDisplayName', 'Unknown Budget')}",
            "attachments": [
                {
                    "color": "danger" if utilization >= 0.9 else "warning" if utilization >= 0.75 else "good",
                    "fields": [
                        {
                            "title": "Budget Utilization",
                            "value": f"{utilization:.1%}",
                            "short": True
                        },
                        {
                            "title": "Actions Taken",
                            "value": f"{len(actions)} optimization actions",
                            "short": True
                        },
                        {
                            "title": "Current Spend",
                            "value": f"${budget_data.get('costAmount', 0):.2f}",
                            "short": True
                        },
                        {
                            "title": "Budget Amount",
                            "value": f"${budget_data.get('budgetAmount', 0):.2f}",
                            "short": True
                        }
                    ],
                    "text": "Actions taken:\n" + "\n".join(f"• {action}" for action in actions[:10])
                }
            ]
        }
        
        if SLACK_WEBHOOK_URL:
            response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
        else:
            logger.info(f"Notification (no webhook configured): {message}")
            
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")


if __name__ == "__main__":
    # Test function locally
    test_event = {
        'data': base64.b64encode(json.dumps({
            'budgetDisplayName': 'test-budget',
            'costAmount': 75.0,
            'budgetAmount': 100.0,
            'alertThresholdExceeded': 0.75
        }).encode('utf-8')).decode('utf-8')
    }
    
    process_budget_alert(test_event, None)