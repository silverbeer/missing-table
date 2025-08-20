#!/usr/bin/env python3
"""
Infrastructure Drift Detection and Alerting System

This module monitors GCP infrastructure for configuration drift from the
Terraform-defined state and sends alerts when deviations are detected.
"""

import os
import json
import logging
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

import requests
from google.cloud import monitoring_v3
from google.cloud import secretmanager
from google.cloud import logging as cloud_logging


class DriftSeverity(Enum):
    """Drift severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftEvent:
    """Infrastructure drift event."""
    resource_type: str
    resource_name: str
    drift_type: str
    severity: DriftSeverity
    current_config: Dict[str, Any]
    expected_config: Dict[str, Any]
    differences: List[Dict[str, Any]]
    timestamp: datetime
    project_id: str
    environment: str


class DriftDetector:
    """Main drift detection engine."""
    
    def __init__(self, project_id: str, terraform_dir: str, environment: str = "production"):
        self.project_id = project_id
        self.terraform_dir = terraform_dir
        self.environment = environment
        self.logger = self._setup_logging()
        
        # Initialize GCP clients
        self.monitoring_client = monitoring_v3.MetricServiceClient()
        self.secret_client = secretmanager.SecretManagerServiceClient()
        
        # Configuration
        self.check_interval = int(os.getenv('DRIFT_CHECK_INTERVAL', '3600'))  # 1 hour default
        self.critical_resources = [
            'google_container_cluster',
            'google_secret_manager_secret',
            'google_kms_crypto_key',
            'google_project_iam_policy',
            'google_binary_authorization_policy'
        ]
        
        # Notification configuration
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.alert_emails = os.getenv('ALERT_EMAILS', '').split(',')
        
    def _setup_logging(self) -> logging.Logger:
        """Set up logging with Cloud Logging integration."""
        logger = logging.getLogger('drift-detector')
        logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Cloud Logging handler
        try:
            cloud_logging_client = cloud_logging.Client(project=self.project_id)
            cloud_handler = cloud_logging_client.get_default_handler()
            logger.addHandler(cloud_handler)
        except Exception as e:
            logger.warning(f"Could not initialize Cloud Logging: {e}")
        
        return logger
    
    def detect_drift(self) -> List[DriftEvent]:
        """Main drift detection method."""
        self.logger.info("Starting infrastructure drift detection")
        
        try:
            # Get current Terraform state
            terraform_state = self._get_terraform_state()
            
            # Get current GCP resource configurations
            current_resources = self._get_current_gcp_resources()
            
            # Compare and identify drift
            drift_events = self._compare_configurations(terraform_state, current_resources)
            
            # Process and prioritize drift events
            processed_events = self._process_drift_events(drift_events)
            
            self.logger.info(f"Drift detection completed. Found {len(processed_events)} drift events")
            
            return processed_events
            
        except Exception as e:
            self.logger.error(f"Drift detection failed: {e}")
            raise
    
    def _get_terraform_state(self) -> Dict[str, Any]:
        """Get current Terraform state."""
        self.logger.info("Fetching Terraform state")
        
        try:
            # Change to terraform directory
            original_dir = os.getcwd()
            os.chdir(self.terraform_dir)
            
            # Run terraform show to get current state
            result = subprocess.run(
                ['terraform', 'show', '-json'],
                capture_output=True,
                text=True,
                check=True,
                timeout=300
            )
            
            state = json.loads(result.stdout)
            
            # Return to original directory
            os.chdir(original_dir)
            
            return state
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Terraform command failed: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Terraform state JSON: {e}")
            raise
        finally:
            os.chdir(original_dir)
    
    def _get_current_gcp_resources(self) -> Dict[str, Any]:
        """Get current GCP resource configurations using gcloud commands."""
        self.logger.info("Fetching current GCP resource configurations")
        
        resources = {}
        
        try:
            # GKE Clusters
            resources['gke_clusters'] = self._get_gke_clusters()
            
            # Secret Manager secrets
            resources['secrets'] = self._get_secret_manager_secrets()
            
            # KMS keys
            resources['kms_keys'] = self._get_kms_keys()
            
            # IAM policies
            resources['iam_policies'] = self._get_iam_policies()
            
            # Binary Authorization policies
            resources['binauthz_policies'] = self._get_binary_authorization_policies()
            
            # VPC networks and subnets
            resources['networks'] = self._get_vpc_networks()
            
            # Storage buckets
            resources['storage_buckets'] = self._get_storage_buckets()
            
            return resources
            
        except Exception as e:
            self.logger.error(f"Failed to fetch GCP resources: {e}")
            raise
    
    def _get_gke_clusters(self) -> List[Dict[str, Any]]:
        """Get GKE cluster configurations."""
        try:
            result = subprocess.run(
                ['gcloud', 'container', 'clusters', 'list', '--format=json', f'--project={self.project_id}'],
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            return json.loads(result.stdout)
        except Exception as e:
            self.logger.warning(f"Failed to get GKE clusters: {e}")
            return []
    
    def _get_secret_manager_secrets(self) -> List[Dict[str, Any]]:
        """Get Secret Manager configurations."""
        try:
            result = subprocess.run(
                ['gcloud', 'secrets', 'list', '--format=json', f'--project={self.project_id}'],
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            return json.loads(result.stdout)
        except Exception as e:
            self.logger.warning(f"Failed to get Secret Manager secrets: {e}")
            return []
    
    def _get_kms_keys(self) -> List[Dict[str, Any]]:
        """Get KMS key configurations."""
        try:
            result = subprocess.run([
                'gcloud', 'kms', 'keys', 'list', 
                '--format=json', 
                f'--project={self.project_id}',
                '--location=global'
            ], capture_output=True, text=True, check=True, timeout=60)
            return json.loads(result.stdout)
        except Exception as e:
            self.logger.warning(f"Failed to get KMS keys: {e}")
            return []
    
    def _get_iam_policies(self) -> List[Dict[str, Any]]:
        """Get IAM policy configurations."""
        try:
            result = subprocess.run([
                'gcloud', 'projects', 'get-iam-policy', self.project_id,
                '--format=json'
            ], capture_output=True, text=True, check=True, timeout=60)
            return [json.loads(result.stdout)]
        except Exception as e:
            self.logger.warning(f"Failed to get IAM policies: {e}")
            return []
    
    def _get_binary_authorization_policies(self) -> List[Dict[str, Any]]:
        """Get Binary Authorization policy configurations."""
        try:
            result = subprocess.run([
                'gcloud', 'container', 'binauthz', 'policy', 'export',
                '--format=json',
                f'--project={self.project_id}'
            ], capture_output=True, text=True, check=True, timeout=60)
            return [json.loads(result.stdout)]
        except Exception as e:
            self.logger.warning(f"Failed to get Binary Authorization policies: {e}")
            return []
    
    def _get_vpc_networks(self) -> List[Dict[str, Any]]:
        """Get VPC network configurations."""
        try:
            result = subprocess.run([
                'gcloud', 'compute', 'networks', 'list',
                '--format=json',
                f'--project={self.project_id}'
            ], capture_output=True, text=True, check=True, timeout=60)
            return json.loads(result.stdout)
        except Exception as e:
            self.logger.warning(f"Failed to get VPC networks: {e}")
            return []
    
    def _get_storage_buckets(self) -> List[Dict[str, Any]]:
        """Get Cloud Storage bucket configurations."""
        try:
            result = subprocess.run([
                'gsutil', 'ls', '-b', '-p', self.project_id, '-L'
            ], capture_output=True, text=True, check=True, timeout=60)
            
            # Parse gsutil output (simplified)
            buckets = []
            current_bucket = {}
            for line in result.stdout.split('\n'):
                if line.startswith('gs://'):
                    if current_bucket:
                        buckets.append(current_bucket)
                    current_bucket = {'name': line.strip()}
                elif ':' in line and current_bucket:
                    key, value = line.split(':', 1)
                    current_bucket[key.strip()] = value.strip()
            
            if current_bucket:
                buckets.append(current_bucket)
                
            return buckets
        except Exception as e:
            self.logger.warning(f"Failed to get storage buckets: {e}")
            return []
    
    def _compare_configurations(self, terraform_state: Dict[str, Any], current_resources: Dict[str, Any]) -> List[DriftEvent]:
        """Compare Terraform state with current GCP configurations."""
        self.logger.info("Comparing configurations to detect drift")
        
        drift_events = []
        
        try:
            # Get Terraform resources
            tf_resources = terraform_state.get('values', {}).get('root_module', {}).get('resources', [])
            
            # Compare each resource type
            for tf_resource in tf_resources:
                resource_type = tf_resource.get('type')
                resource_name = tf_resource.get('name')
                tf_values = tf_resource.get('values', {})
                
                # Find corresponding current resource
                current_resource = self._find_current_resource(
                    resource_type, resource_name, tf_values, current_resources
                )
                
                if current_resource is None:
                    # Resource not found - deleted drift
                    drift_events.append(DriftEvent(
                        resource_type=resource_type,
                        resource_name=resource_name,
                        drift_type="resource_deleted",
                        severity=self._get_drift_severity(resource_type, "resource_deleted"),
                        current_config={},
                        expected_config=tf_values,
                        differences=[{"type": "resource_deleted", "message": "Resource not found in current state"}],
                        timestamp=datetime.utcnow(),
                        project_id=self.project_id,
                        environment=self.environment
                    ))
                else:
                    # Compare configurations
                    differences = self._compare_resource_configs(tf_values, current_resource)
                    if differences:
                        drift_events.append(DriftEvent(
                            resource_type=resource_type,
                            resource_name=resource_name,
                            drift_type="configuration_drift",
                            severity=self._get_drift_severity(resource_type, "configuration_drift"),
                            current_config=current_resource,
                            expected_config=tf_values,
                            differences=differences,
                            timestamp=datetime.utcnow(),
                            project_id=self.project_id,
                            environment=self.environment
                        ))
            
            return drift_events
            
        except Exception as e:
            self.logger.error(f"Configuration comparison failed: {e}")
            raise
    
    def _find_current_resource(self, resource_type: str, resource_name: str, tf_values: Dict[str, Any], current_resources: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the current resource matching the Terraform resource."""
        
        # Mapping of Terraform resource types to GCP resource collections
        resource_mapping = {
            'google_container_cluster': 'gke_clusters',
            'google_secret_manager_secret': 'secrets',
            'google_kms_crypto_key': 'kms_keys',
            'google_project_iam_policy': 'iam_policies',
            'google_binary_authorization_policy': 'binauthz_policies',
            'google_compute_network': 'networks',
            'google_storage_bucket': 'storage_buckets'
        }
        
        collection_name = resource_mapping.get(resource_type)
        if not collection_name:
            return None
        
        resources = current_resources.get(collection_name, [])
        
        # Find resource by name or identifier
        for resource in resources:
            if self._resource_matches(resource_type, resource_name, tf_values, resource):
                return resource
        
        return None
    
    def _resource_matches(self, resource_type: str, resource_name: str, tf_values: Dict[str, Any], current_resource: Dict[str, Any]) -> bool:
        """Check if current resource matches Terraform resource."""
        
        # GKE clusters
        if resource_type == 'google_container_cluster':
            tf_name = tf_values.get('name', '')
            current_name = current_resource.get('name', '')
            return tf_name in current_name or current_name in tf_name
        
        # Secret Manager
        elif resource_type == 'google_secret_manager_secret':
            tf_secret_id = tf_values.get('secret_id', '')
            current_name = current_resource.get('name', '')
            return tf_secret_id in current_name
        
        # KMS keys
        elif resource_type == 'google_kms_crypto_key':
            tf_name = tf_values.get('name', '')
            current_name = current_resource.get('name', '')
            return tf_name in current_name
        
        # Storage buckets
        elif resource_type == 'google_storage_bucket':
            tf_name = tf_values.get('name', '')
            current_name = current_resource.get('name', '')
            return tf_name in current_name
        
        return False
    
    def _compare_resource_configs(self, tf_config: Dict[str, Any], current_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Compare Terraform and current resource configurations."""
        differences = []
        
        # Define important fields to check for each resource type
        important_fields = {
            'google_container_cluster': [
                'private_cluster_config.enable_private_nodes',
                'network_policy.enabled',
                'binary_authorization.evaluation_mode',
                'master_authorized_networks_config'
            ],
            'google_secret_manager_secret': [
                'replication',
                'secret_id'
            ],
            'google_kms_crypto_key': [
                'rotation_period',
                'purpose'
            ]
        }
        
        # Compare specific fields based on resource type
        # This is a simplified comparison - in production, you'd want more sophisticated logic
        
        for field_path in important_fields.get(tf_config.get('resource_type', ''), []):
            tf_value = self._get_nested_value(tf_config, field_path)
            current_value = self._get_nested_value(current_config, field_path)
            
            if tf_value != current_value:
                differences.append({
                    "field": field_path,
                    "expected": tf_value,
                    "current": current_value,
                    "type": "field_mismatch"
                })
        
        return differences
    
    def _get_nested_value(self, config: Dict[str, Any], field_path: str) -> Any:
        """Get nested value from config using dot notation."""
        try:
            value = config
            for key in field_path.split('.'):
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and value:
                    value = value[0].get(key) if isinstance(value[0], dict) else None
                else:
                    return None
            return value
        except (KeyError, AttributeError, IndexError):
            return None
    
    def _get_drift_severity(self, resource_type: str, drift_type: str) -> DriftSeverity:
        """Determine drift severity based on resource type and drift type."""
        
        if resource_type in self.critical_resources:
            if drift_type == "resource_deleted":
                return DriftSeverity.CRITICAL
            else:
                return DriftSeverity.HIGH
        
        if drift_type == "resource_deleted":
            return DriftSeverity.HIGH
        
        return DriftSeverity.MEDIUM
    
    def _process_drift_events(self, drift_events: List[DriftEvent]) -> List[DriftEvent]:
        """Process and enrich drift events."""
        processed_events = []
        
        for event in drift_events:
            # Add additional context and validation
            if self._is_valid_drift_event(event):
                processed_events.append(event)
        
        # Sort by severity
        severity_order = {
            DriftSeverity.CRITICAL: 0,
            DriftSeverity.HIGH: 1,
            DriftSeverity.MEDIUM: 2,
            DriftSeverity.LOW: 3
        }
        
        processed_events.sort(key=lambda x: severity_order[x.severity])
        
        return processed_events
    
    def _is_valid_drift_event(self, event: DriftEvent) -> bool:
        """Validate if drift event is actionable."""
        
        # Filter out known false positives
        false_positive_patterns = [
            # Add patterns for known false positives
            "metadata.generation",
            "status.",
            "self_link"
        ]
        
        for difference in event.differences:
            field = difference.get("field", "")
            for pattern in false_positive_patterns:
                if pattern in field:
                    return False
        
        return True
    
    def send_drift_alerts(self, drift_events: List[DriftEvent]) -> None:
        """Send drift alerts via various channels."""
        if not drift_events:
            return
        
        self.logger.info(f"Sending alerts for {len(drift_events)} drift events")
        
        # Send Slack notification
        if self.slack_webhook:
            self._send_slack_alert(drift_events)
        
        # Send email notifications
        if self.alert_emails:
            self._send_email_alert(drift_events)
        
        # Create GCP monitoring alert
        self._create_monitoring_alert(drift_events)
    
    def _send_slack_alert(self, drift_events: List[DriftEvent]) -> None:
        """Send Slack notification for drift events."""
        try:
            message = self._format_slack_message(drift_events)
            
            response = requests.post(
                self.slack_webhook,
                json={"text": message},
                timeout=30
            )
            response.raise_for_status()
            
            self.logger.info("Slack alert sent successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
    
    def _format_slack_message(self, drift_events: List[DriftEvent]) -> str:
        """Format drift events for Slack."""
        critical_count = sum(1 for e in drift_events if e.severity == DriftSeverity.CRITICAL)
        high_count = sum(1 for e in drift_events if e.severity == DriftSeverity.HIGH)
        
        message = f"🚨 Infrastructure Drift Detected - {self.environment.upper()}\n\n"
        message += f"Critical: {critical_count}, High: {high_count}, Total: {len(drift_events)}\n\n"
        
        for event in drift_events[:5]:  # Show first 5 events
            severity_emoji = {
                DriftSeverity.CRITICAL: "🔴",
                DriftSeverity.HIGH: "🟠",
                DriftSeverity.MEDIUM: "🟡",
                DriftSeverity.LOW: "🟢"
            }
            
            message += f"{severity_emoji[event.severity]} {event.resource_type}/{event.resource_name}\n"
            message += f"  Type: {event.drift_type}\n"
            message += f"  Differences: {len(event.differences)}\n\n"
        
        if len(drift_events) > 5:
            message += f"... and {len(drift_events) - 5} more events\n"
        
        return message
    
    def _send_email_alert(self, drift_events: List[DriftEvent]) -> None:
        """Send email notification for drift events."""
        # Implementation depends on your email service
        # This is a placeholder for email notification logic
        self.logger.info("Email alert functionality not implemented")
    
    def _create_monitoring_alert(self, drift_events: List[DriftEvent]) -> None:
        """Create GCP monitoring metric for drift events."""
        try:
            # Create custom metric for drift events
            project_name = f"projects/{self.project_id}"
            
            # This would create a custom metric in Cloud Monitoring
            # Implementation depends on specific monitoring setup
            
            self.logger.info("Monitoring alert created for drift events")
            
        except Exception as e:
            self.logger.error(f"Failed to create monitoring alert: {e}")
    
    def run_continuous_monitoring(self) -> None:
        """Run continuous drift monitoring."""
        self.logger.info(f"Starting continuous drift monitoring (interval: {self.check_interval}s)")
        
        while True:
            try:
                drift_events = self.detect_drift()
                
                if drift_events:
                    self.send_drift_alerts(drift_events)
                    
                    # Log summary
                    self.logger.info(f"Detected {len(drift_events)} drift events")
                    for event in drift_events:
                        self.logger.warning(
                            f"Drift: {event.resource_type}/{event.resource_name} "
                            f"- {event.drift_type} ({event.severity.value})"
                        )
                else:
                    self.logger.info("No infrastructure drift detected")
                
                # Wait for next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Drift monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Drift monitoring error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying


def main():
    """Main entry point for drift detection."""
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    terraform_dir = os.getenv('TERRAFORM_DIR', '/app/terraform')
    environment = os.getenv('ENVIRONMENT', 'production')
    
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set")
    
    detector = DriftDetector(project_id, terraform_dir, environment)
    
    # Run once or continuously based on environment variable
    if os.getenv('CONTINUOUS_MONITORING', 'false').lower() == 'true':
        detector.run_continuous_monitoring()
    else:
        drift_events = detector.detect_drift()
        if drift_events:
            detector.send_drift_alerts(drift_events)
            print(f"Detected {len(drift_events)} drift events")
            exit(1)  # Exit with error code if drift detected
        else:
            print("No drift detected")
            exit(0)


if __name__ == "__main__":
    main()