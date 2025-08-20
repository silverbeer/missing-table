"""
Custom Checkov Security Policies for Missing Table GCP Infrastructure

This module defines organization-specific security policies that extend
the default Checkov security checks for GCP resources.
"""

from checkov.common.models.enums import TRUE_VALUES
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck
from checkov.common.models.consts import ANY_VALUE
from checkov.common.output.report import CheckResult
from typing import Any, List, Dict


class GKEClusterMustHavePrivateNodes(BaseResourceCheck):
    """Ensure GKE clusters have private nodes enabled for security."""
    
    def __init__(self) -> None:
        name = "Ensure GKE cluster has private nodes enabled"
        id = "CKV_GCP_MISSING_TABLE_001"
        supported_resources = ["google_container_cluster"]
        categories = ["NETWORKING"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan GKE cluster configuration for private nodes."""
        private_cluster_config = conf.get("private_cluster_config")
        if not private_cluster_config:
            return CheckResult.FAILED
            
        if isinstance(private_cluster_config, list):
            private_cluster_config = private_cluster_config[0]
            
        enable_private_nodes = private_cluster_config.get("enable_private_nodes")
        if enable_private_nodes and enable_private_nodes[0] in TRUE_VALUES:
            return CheckResult.PASSED
            
        return CheckResult.FAILED


class GKEClusterMustHaveNetworkPolicy(BaseResourceCheck):
    """Ensure GKE clusters have network policy enabled."""
    
    def __init__(self) -> None:
        name = "Ensure GKE cluster has network policy enabled"
        id = "CKV_GCP_MISSING_TABLE_002"
        supported_resources = ["google_container_cluster"]
        categories = ["NETWORKING"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan GKE cluster configuration for network policy."""
        network_policy = conf.get("network_policy")
        if not network_policy:
            return CheckResult.FAILED
            
        if isinstance(network_policy, list):
            network_policy = network_policy[0]
            
        enabled = network_policy.get("enabled")
        if enabled and enabled[0] in TRUE_VALUES:
            return CheckResult.PASSED
            
        return CheckResult.FAILED


class GKEClusterMustHaveBinaryAuthorization(BaseResourceCheck):
    """Ensure GKE clusters have Binary Authorization enabled."""
    
    def __init__(self) -> None:
        name = "Ensure GKE cluster has Binary Authorization enabled"
        id = "CKV_GCP_MISSING_TABLE_003"
        supported_resources = ["google_container_cluster"]
        categories = ["IAM"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan GKE cluster configuration for Binary Authorization."""
        binary_authorization = conf.get("binary_authorization")
        if not binary_authorization:
            return CheckResult.FAILED
            
        if isinstance(binary_authorization, list):
            binary_authorization = binary_authorization[0]
            
        evaluation_mode = binary_authorization.get("evaluation_mode")
        if evaluation_mode and "ENFORCE" in evaluation_mode[0]:
            return CheckResult.PASSED
            
        return CheckResult.FAILED


class SecretManagerMustUseCustomerManagedEncryption(BaseResourceCheck):
    """Ensure Secret Manager secrets use customer-managed encryption."""
    
    def __init__(self) -> None:
        name = "Ensure Secret Manager secrets use customer-managed encryption"
        id = "CKV_GCP_MISSING_TABLE_004"
        supported_resources = ["google_secret_manager_secret"]
        categories = ["ENCRYPTION"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan Secret Manager configuration for CMEK."""
        replication = conf.get("replication")
        if not replication:
            return CheckResult.FAILED
            
        if isinstance(replication, list):
            replication = replication[0]
            
        user_managed = replication.get("user_managed")
        if not user_managed:
            return CheckResult.FAILED
            
        if isinstance(user_managed, list):
            user_managed = user_managed[0]
            
        replicas = user_managed.get("replicas")
        if not replicas:
            return CheckResult.FAILED
            
        # Check if any replica uses customer-managed encryption
        for replica in replicas:
            if isinstance(replica, dict):
                cmek = replica.get("customer_managed_encryption")
                if cmek:
                    return CheckResult.PASSED
                    
        return CheckResult.FAILED


class CloudStorageMustHaveUniformBucketLevelAccess(BaseResourceCheck):
    """Ensure Cloud Storage buckets have uniform bucket-level access enabled."""
    
    def __init__(self) -> None:
        name = "Ensure Cloud Storage buckets have uniform bucket-level access"
        id = "CKV_GCP_MISSING_TABLE_005"
        supported_resources = ["google_storage_bucket"]
        categories = ["IAM"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan Cloud Storage bucket configuration for uniform access."""
        uniform_bucket_level_access = conf.get("uniform_bucket_level_access")
        if uniform_bucket_level_access and uniform_bucket_level_access[0] in TRUE_VALUES:
            return CheckResult.PASSED
            
        return CheckResult.FAILED


class GKENodePoolMustHaveShieldedNodes(BaseResourceCheck):
    """Ensure GKE node pools have shielded nodes enabled."""
    
    def __init__(self) -> None:
        name = "Ensure GKE node pools have shielded nodes enabled"
        id = "CKV_GCP_MISSING_TABLE_006"
        supported_resources = ["google_container_node_pool"]
        categories = ["GENERAL_SECURITY"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan GKE node pool configuration for shielded nodes."""
        node_config = conf.get("node_config")
        if not node_config:
            return CheckResult.FAILED
            
        if isinstance(node_config, list):
            node_config = node_config[0]
            
        shielded_instance_config = node_config.get("shielded_instance_config")
        if not shielded_instance_config:
            return CheckResult.FAILED
            
        if isinstance(shielded_instance_config, list):
            shielded_instance_config = shielded_instance_config[0]
            
        enable_secure_boot = shielded_instance_config.get("enable_secure_boot")
        enable_integrity_monitoring = shielded_instance_config.get("enable_integrity_monitoring")
        
        if (enable_secure_boot and enable_secure_boot[0] in TRUE_VALUES and
            enable_integrity_monitoring and enable_integrity_monitoring[0] in TRUE_VALUES):
            return CheckResult.PASSED
            
        return CheckResult.FAILED


class ServiceAccountMustNotHaveKeys(BaseResourceCheck):
    """Ensure service accounts don't have downloadable keys."""
    
    def __init__(self) -> None:
        name = "Ensure service accounts don't have downloadable keys"
        id = "CKV_GCP_MISSING_TABLE_007"
        supported_resources = ["google_service_account_key"]
        categories = ["IAM"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan for service account keys - they should not exist."""
        # If a service account key resource exists, it's a security risk
        return CheckResult.FAILED


class VPCMustHaveFlowLogsEnabled(BaseResourceCheck):
    """Ensure VPC subnets have flow logs enabled for security monitoring."""
    
    def __init__(self) -> None:
        name = "Ensure VPC subnets have flow logs enabled"
        id = "CKV_GCP_MISSING_TABLE_008"
        supported_resources = ["google_compute_subnetwork"]
        categories = ["LOGGING"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan VPC subnet configuration for flow logs."""
        log_config = conf.get("log_config")
        if not log_config:
            return CheckResult.FAILED
            
        if isinstance(log_config, list):
            log_config = log_config[0]
            
        # Flow logs are enabled if log_config exists and is properly configured
        aggregation_interval = log_config.get("aggregation_interval")
        flow_sampling = log_config.get("flow_sampling")
        metadata = log_config.get("metadata")
        
        if aggregation_interval and flow_sampling is not None and metadata:
            return CheckResult.PASSED
            
        return CheckResult.FAILED


class ProjectMustHaveAuditLogsEnabled(BaseResourceCheck):
    """Ensure project has comprehensive audit logging enabled."""
    
    def __init__(self) -> None:
        name = "Ensure project has comprehensive audit logging enabled"
        id = "CKV_GCP_MISSING_TABLE_009"
        supported_resources = ["google_project_iam_audit_config"]
        categories = ["LOGGING"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan project audit configuration."""
        service = conf.get("service")
        audit_log_config = conf.get("audit_log_config")
        
        if not service or not audit_log_config:
            return CheckResult.FAILED
            
        # Check for comprehensive audit logging
        log_types = set()
        if isinstance(audit_log_config, list):
            for config in audit_log_config:
                if isinstance(config, dict):
                    log_type = config.get("log_type")
                    if log_type:
                        log_types.add(log_type[0] if isinstance(log_type, list) else log_type)
        
        # Should have at least ADMIN_READ and DATA_READ
        required_types = {"ADMIN_READ", "DATA_READ"}
        if required_types.issubset(log_types):
            return CheckResult.PASSED
            
        return CheckResult.FAILED


class KMSKeyMustHaveRotationEnabled(BaseResourceCheck):
    """Ensure KMS keys have automatic rotation enabled."""
    
    def __init__(self) -> None:
        name = "Ensure KMS keys have automatic rotation enabled"
        id = "CKV_GCP_MISSING_TABLE_010"
        supported_resources = ["google_kms_crypto_key"]
        categories = ["ENCRYPTION"]
        super().__init__(name=name, id=id, categories=categories, supported_resources=supported_resources)

    def scan_resource_conf(self, conf: dict[str, Any]) -> CheckResult:
        """Scan KMS key configuration for rotation."""
        rotation_period = conf.get("rotation_period")
        
        if rotation_period:
            # Check if rotation period is set (any value indicates rotation is enabled)
            return CheckResult.PASSED
            
        return CheckResult.FAILED


# Register all custom checks
check = GKEClusterMustHavePrivateNodes()
check = GKEClusterMustHaveNetworkPolicy()
check = GKEClusterMustHaveBinaryAuthorization()
check = SecretManagerMustUseCustomerManagedEncryption()
check = CloudStorageMustHaveUniformBucketLevelAccess()
check = GKENodePoolMustHaveShieldedNodes()
check = ServiceAccountMustNotHaveKeys()
check = VPCMustHaveFlowLogsEnabled()
check = ProjectMustHaveAuditLogsEnabled()
check = KMSKeyMustHaveRotationEnabled()