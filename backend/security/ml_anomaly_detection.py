"""
Advanced ML-Based Anomaly Detection for User Behavior
Sophisticated behavioral analysis using multiple ML algorithms and ensemble methods
"""

import asyncio
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import asyncpg
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
import logfire
from prometheus_client import Counter, Histogram, Gauge
import redis
import pickle
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Prometheus metrics
BEHAVIOR_ANOMALIES_DETECTED = Counter(
    'behavior_anomalies_detected_total',
    'Total number of behavioral anomalies detected',
    ['user_id', 'anomaly_type', 'severity']
)

ANOMALY_DETECTION_LATENCY = Histogram(
    'anomaly_detection_latency_seconds',
    'Time taken to detect behavioral anomalies',
    ['model_type']
)

USER_RISK_SCORE = Gauge(
    'user_risk_score',
    'Current risk score for users',
    ['user_id']
)

MODEL_ACCURACY = Gauge(
    'ml_model_accuracy',
    'Accuracy of ML models',
    ['model_name']
)

class AnomalyType(str, Enum):
    """Types of behavioral anomalies"""
    UNUSUAL_LOGIN_TIME = "unusual_login_time"
    ABNORMAL_DATA_ACCESS = "abnormal_data_access"
    SUSPICIOUS_API_USAGE = "suspicious_api_usage"
    ATYPICAL_NAVIGATION = "atypical_navigation"
    ABNORMAL_SESSION_DURATION = "abnormal_session_duration"
    UNUSUAL_GEOLOCATION = "unusual_geolocation"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"
    BULK_DATA_DOWNLOAD = "bulk_data_download"
    OFF_HOURS_ACTIVITY = "off_hours_activity"
    VELOCITY_ANOMALY = "velocity_anomaly"

class AnomalySeverity(str, Enum):
    """Severity levels for anomalies"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class UserBehaviorProfile:
    """User behavioral profile baseline"""
    user_id: str
    typical_login_hours: List[int]
    common_ip_addresses: List[str]
    usual_geolocation: Optional[str]
    average_session_duration: float
    typical_api_endpoints: List[str]
    normal_data_access_patterns: Dict[str, Any]
    baseline_features: Dict[str, float]
    profile_confidence: float
    last_updated: datetime

@dataclass
class BehaviorEvent:
    """Individual user behavior event"""
    event_id: str
    user_id: str
    timestamp: datetime
    event_type: str
    ip_address: str
    user_agent: str
    geolocation: Optional[str]
    session_id: str
    api_endpoint: Optional[str]
    data_accessed: Optional[str]
    request_size: int
    response_size: int
    duration_ms: int
    success: bool
    metadata: Dict[str, Any]

@dataclass
class BehaviorAnomaly:
    """Detected behavioral anomaly"""
    anomaly_id: str
    user_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    confidence_score: float
    detected_at: datetime
    event_ids: List[str]
    baseline_deviation: Dict[str, float]
    risk_factors: List[str]
    context: Dict[str, Any]
    recommended_actions: List[str]

class MLAnomalyDetector:
    """Advanced ML-based user behavior anomaly detection system"""
    
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client = redis.Redis(host='localhost', port=6379, db=4)
        
        # ML Models
        self.isolation_forest = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        self.lstm_model: Optional[tf.keras.Model] = None
        self.clustering_model = DBSCAN(eps=0.5, min_samples=5)
        self.ensemble_classifier = RandomForestClassifier(
            n_estimators=200,
            random_state=42
        )
        
        # Feature engineering
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.pca = PCA(n_components=0.95)  # Retain 95% variance
        
        # Behavioral profiles
        self.user_profiles: Dict[str, UserBehaviorProfile] = {}
        self.feature_columns = [
            'hour_of_day', 'day_of_week', 'session_duration_minutes',
            'api_requests_per_hour', 'data_access_volume_mb',
            'unique_endpoints_accessed', 'failed_request_ratio',
            'geolocation_entropy', 'ip_reputation_score'
        ]
        
    async def initialize(self):
        """Initialize ML anomaly detection system"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:password@localhost/behavior_analytics",
            min_size=5,
            max_size=20
        )
        await self._create_tables()
        await self._load_user_profiles()
        await self._initialize_ml_models()
        
        logfire.info("ML anomaly detection system initialized")
    
    async def _create_tables(self):
        """Create behavior analytics database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_behavior_profiles (
                    user_id VARCHAR PRIMARY KEY,
                    typical_login_hours JSONB,
                    common_ip_addresses JSONB,
                    usual_geolocation VARCHAR,
                    average_session_duration FLOAT,
                    typical_api_endpoints JSONB,
                    normal_data_access_patterns JSONB,
                    baseline_features JSONB,
                    profile_confidence FLOAT,
                    last_updated TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS behavior_events (
                    event_id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    event_type VARCHAR NOT NULL,
                    ip_address INET,
                    user_agent TEXT,
                    geolocation VARCHAR,
                    session_id VARCHAR,
                    api_endpoint VARCHAR,
                    data_accessed VARCHAR,
                    request_size INTEGER DEFAULT 0,
                    response_size INTEGER DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    success BOOLEAN DEFAULT TRUE,
                    metadata JSONB,
                    features JSONB,
                    anomaly_scores JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS behavior_anomalies (
                    anomaly_id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    anomaly_type VARCHAR NOT NULL,
                    severity VARCHAR NOT NULL,
                    confidence_score FLOAT NOT NULL,
                    detected_at TIMESTAMP NOT NULL,
                    event_ids JSONB,
                    baseline_deviation JSONB,
                    risk_factors JSONB,
                    context JSONB,
                    recommended_actions JSONB,
                    status VARCHAR DEFAULT 'open',
                    investigated_at TIMESTAMP,
                    resolution VARCHAR,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS ml_model_performance (
                    model_name VARCHAR PRIMARY KEY,
                    model_type VARCHAR NOT NULL,
                    accuracy FLOAT,
                    precision_score FLOAT,
                    recall FLOAT,
                    f1_score FLOAT,
                    training_date TIMESTAMP,
                    validation_samples INTEGER,
                    hyperparameters JSONB,
                    feature_importance JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_behavior_events_user_id ON behavior_events(user_id);
                CREATE INDEX IF NOT EXISTS idx_behavior_events_timestamp ON behavior_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_behavior_anomalies_user_id ON behavior_anomalies(user_id);
                CREATE INDEX IF NOT EXISTS idx_behavior_anomalies_detected_at ON behavior_anomalies(detected_at);
                CREATE INDEX IF NOT EXISTS idx_behavior_anomalies_severity ON behavior_anomalies(severity);
            """)
    
    async def _load_user_profiles(self):
        """Load existing user behavioral profiles"""
        async with self.db_pool.acquire() as conn:
            profiles = await conn.fetch("SELECT * FROM user_behavior_profiles")
            
            for profile_data in profiles:
                profile = UserBehaviorProfile(
                    user_id=profile_data['user_id'],
                    typical_login_hours=profile_data['typical_login_hours'] or [],
                    common_ip_addresses=profile_data['common_ip_addresses'] or [],
                    usual_geolocation=profile_data['usual_geolocation'],
                    average_session_duration=profile_data['average_session_duration'] or 0.0,
                    typical_api_endpoints=profile_data['typical_api_endpoints'] or [],
                    normal_data_access_patterns=profile_data['normal_data_access_patterns'] or {},
                    baseline_features=profile_data['baseline_features'] or {},
                    profile_confidence=profile_data['profile_confidence'] or 0.0,
                    last_updated=profile_data['last_updated']
                )
                self.user_profiles[profile.user_id] = profile
    
    async def _initialize_ml_models(self):
        """Initialize and load ML models"""
        try:
            # Try to load existing models
            await self._load_trained_models()
        except:
            # Train new models with available data
            await self._train_initial_models()
    
    async def _load_trained_models(self):
        """Load pre-trained ML models"""
        try:
            # Load model artifacts from Redis
            model_data = await self.redis_client.get("ml_models:isolation_forest")
            if model_data:
                self.isolation_forest = pickle.loads(model_data)
            
            scaler_data = await self.redis_client.get("ml_models:scaler")
            if scaler_data:
                self.scaler = pickle.loads(scaler_data)
            
            # Try to load LSTM model
            try:
                self.lstm_model = load_model("/tmp/lstm_behavior_model.h5")
            except:
                pass
                
        except Exception as e:
            logger.warning(f"Could not load existing models: {e}")
    
    async def _train_initial_models(self):
        """Train initial ML models with available data"""
        # Get historical behavior data
        async with self.db_pool.acquire() as conn:
            training_data = await conn.fetch("""
                SELECT * FROM behavior_events 
                WHERE timestamp > NOW() - INTERVAL '30 days'
                AND features IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 10000
            """)
        
        if len(training_data) < 100:
            # Generate synthetic training data for initial setup
            training_data = self._generate_synthetic_behavior_data()
        
        # Prepare features
        features_df = self._prepare_training_features(training_data)
        
        if not features_df.empty:
            # Train isolation forest
            X = features_df[self.feature_columns].fillna(0)
            X_scaled = self.scaler.fit_transform(X)
            self.isolation_forest.fit(X_scaled)
            
            # Train LSTM for sequence analysis
            await self._train_lstm_model(training_data)
            
            # Save models
            await self._save_trained_models()
            
            logfire.info(
                "ML models trained",
                training_samples=len(training_data),
                features=len(self.feature_columns)
            )
    
    def _generate_synthetic_behavior_data(self) -> List[Dict[str, Any]]:
        """Generate synthetic behavior data for training"""
        synthetic_data = []
        
        # Generate normal behavior patterns
        for i in range(1000):
            # Normal business hours activity
            hour = np.random.choice([9, 10, 11, 14, 15, 16], p=[0.1, 0.2, 0.2, 0.2, 0.2, 0.1])
            
            synthetic_data.append({
                'user_id': f'user_{i % 50}',
                'timestamp': datetime.now() - timedelta(days=np.random.randint(1, 30)),
                'features': {
                    'hour_of_day': hour,
                    'day_of_week': np.random.randint(1, 6),  # Weekdays
                    'session_duration_minutes': np.random.normal(45, 15),
                    'api_requests_per_hour': np.random.normal(20, 5),
                    'data_access_volume_mb': np.random.exponential(5),
                    'unique_endpoints_accessed': np.random.randint(3, 15),
                    'failed_request_ratio': np.random.beta(1, 10),
                    'geolocation_entropy': 0.1,  # Low entropy for consistent location
                    'ip_reputation_score': np.random.normal(90, 5)
                }
            })
        
        # Generate some anomalous patterns
        for i in range(100):
            # Anomalous after-hours activity
            hour = np.random.choice([23, 0, 1, 2, 3, 4, 5])
            
            synthetic_data.append({
                'user_id': f'user_{i % 10}',
                'timestamp': datetime.now() - timedelta(days=np.random.randint(1, 30)),
                'features': {
                    'hour_of_day': hour,
                    'day_of_week': np.random.randint(1, 8),
                    'session_duration_minutes': np.random.normal(120, 30),  # Longer sessions
                    'api_requests_per_hour': np.random.normal(100, 20),      # Higher API usage
                    'data_access_volume_mb': np.random.exponential(50),      # More data access
                    'unique_endpoints_accessed': np.random.randint(20, 50),
                    'failed_request_ratio': np.random.beta(2, 5),           # More failures
                    'geolocation_entropy': 0.8,                             # High entropy
                    'ip_reputation_score': np.random.normal(60, 20)         # Lower reputation
                }
            })
        
        return synthetic_data
    
    def _prepare_training_features(self, training_data: List[Any]) -> pd.DataFrame:
        """Prepare features for ML training"""
        features_list = []
        
        for event in training_data:
            if isinstance(event, dict):
                features = event.get('features', {})
            else:
                features = json.loads(event.get('features', '{}'))
            
            if features:
                features_list.append(features)
        
        if features_list:
            return pd.DataFrame(features_list)
        else:
            return pd.DataFrame()
    
    async def _train_lstm_model(self, training_data: List[Any]):
        """Train LSTM model for sequence-based anomaly detection"""
        try:
            # Prepare sequential data
            user_sequences = {}
            
            for event in training_data:
                user_id = event.get('user_id') if isinstance(event, dict) else event['user_id']
                features = event.get('features', {}) if isinstance(event, dict) else json.loads(event.get('features', '{}'))
                
                if user_id not in user_sequences:
                    user_sequences[user_id] = []
                
                feature_vector = [features.get(col, 0) for col in self.feature_columns]
                user_sequences[user_id].append(feature_vector)
            
            # Create training sequences
            X, y = [], []
            sequence_length = 10
            
            for user_id, sequences in user_sequences.items():
                if len(sequences) >= sequence_length + 1:
                    for i in range(len(sequences) - sequence_length):
                        X.append(sequences[i:i+sequence_length])
                        # Predict next timestep (autoencoder style)
                        y.append(sequences[i+sequence_length])
            
            if len(X) > 50:  # Minimum data for training
                X = np.array(X)
                y = np.array(y)
                
                # Build LSTM model
                self.lstm_model = Sequential([
                    LSTM(64, return_sequences=True, input_shape=(sequence_length, len(self.feature_columns))),
                    Dropout(0.2),
                    LSTM(32, return_sequences=False),
                    Dropout(0.2),
                    Dense(len(self.feature_columns), activation='linear')
                ])
                
                self.lstm_model.compile(
                    optimizer=Adam(learning_rate=0.001),
                    loss='mse',
                    metrics=['mae']
                )
                
                # Train model
                history = self.lstm_model.fit(
                    X, y,
                    epochs=50,
                    batch_size=32,
                    validation_split=0.2,
                    verbose=0
                )
                
                # Save model
                self.lstm_model.save("/tmp/lstm_behavior_model.h5")
                
                logfire.info(
                    "LSTM model trained",
                    training_sequences=len(X),
                    sequence_length=sequence_length,
                    final_loss=history.history['loss'][-1]
                )
        
        except Exception as e:
            logger.error(f"Error training LSTM model: {e}")
    
    async def _save_trained_models(self):
        """Save trained ML models"""
        try:
            # Save isolation forest
            model_data = pickle.dumps(self.isolation_forest)
            await self.redis_client.setex("ml_models:isolation_forest", 86400, model_data)
            
            # Save scaler
            scaler_data = pickle.dumps(self.scaler)
            await self.redis_client.setex("ml_models:scaler", 86400, scaler_data)
            
        except Exception as e:
            logger.error(f"Error saving models: {e}")
    
    @logfire.instrument("Analyze User Behavior")
    async def analyze_user_behavior(self, event: BehaviorEvent) -> List[BehaviorAnomaly]:
        """Analyze user behavior event for anomalies"""
        with logfire.span("behavior_analysis", user_id=event.user_id):
            start_time = datetime.now()
            anomalies = []
            
            # Extract features
            features = await self._extract_behavior_features(event)
            
            # Store event with features
            await self._store_behavior_event(event, features)
            
            # Get or create user profile
            user_profile = await self._get_or_create_user_profile(event.user_id)
            
            # Run anomaly detection algorithms
            isolation_forest_anomalies = await self._detect_isolation_forest_anomalies(event, features, user_profile)
            anomalies.extend(isolation_forest_anomalies)
            
            lstm_anomalies = await self._detect_lstm_anomalies(event, features, user_profile)
            anomalies.extend(lstm_anomalies)
            
            statistical_anomalies = await self._detect_statistical_anomalies(event, features, user_profile)
            anomalies.extend(statistical_anomalies)
            
            rule_based_anomalies = await self._detect_rule_based_anomalies(event, features, user_profile)
            anomalies.extend(rule_based_anomalies)
            
            # Store anomalies
            for anomaly in anomalies:
                await self._store_behavior_anomaly(anomaly)
                
                # Update metrics
                BEHAVIOR_ANOMALIES_DETECTED.labels(
                    user_id=anomaly.user_id,
                    anomaly_type=anomaly.anomaly_type.value,
                    severity=anomaly.severity.value
                ).inc()
            
            # Update user risk score
            risk_score = self._calculate_user_risk_score(anomalies, user_profile)
            USER_RISK_SCORE.labels(user_id=event.user_id).set(risk_score)
            
            # Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            ANOMALY_DETECTION_LATENCY.labels(model_type="ensemble").observe(processing_time)
            
            logfire.info(
                "Behavior analysis completed",
                user_id=event.user_id,
                anomalies_detected=len(anomalies),
                processing_time_ms=processing_time * 1000,
                risk_score=risk_score
            )
            
            return anomalies
    
    async def _extract_behavior_features(self, event: BehaviorEvent) -> Dict[str, float]:
        """Extract behavioral features from event"""
        features = {}
        
        # Temporal features
        features['hour_of_day'] = event.timestamp.hour
        features['day_of_week'] = event.timestamp.weekday() + 1
        features['is_weekend'] = 1.0 if event.timestamp.weekday() >= 5 else 0.0
        features['is_business_hours'] = 1.0 if 9 <= event.timestamp.hour <= 17 else 0.0
        
        # Session features
        features['session_duration_minutes'] = event.duration_ms / (1000 * 60)
        features['request_size_kb'] = event.request_size / 1024
        features['response_size_kb'] = event.response_size / 1024
        features['success_flag'] = 1.0 if event.success else 0.0
        
        # Get aggregated features for the user
        user_hourly_stats = await self._get_user_hourly_activity(event.user_id, event.timestamp)
        features.update(user_hourly_stats)
        
        # IP reputation (mock - would integrate with threat intelligence)
        features['ip_reputation_score'] = await self._get_ip_reputation(event.ip_address)
        
        # Geolocation entropy
        features['geolocation_entropy'] = await self._calculate_geolocation_entropy(event.user_id)
        
        return features
    
    async def _get_user_hourly_activity(self, user_id: str, timestamp: datetime) -> Dict[str, float]:
        """Get user activity statistics for the current hour"""
        hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as api_requests_per_hour,
                    COUNT(DISTINCT api_endpoint) as unique_endpoints_accessed,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as failed_request_ratio,
                    SUM(response_size)::FLOAT / (1024 * 1024) as data_access_volume_mb
                FROM behavior_events 
                WHERE user_id = $1 
                AND timestamp BETWEEN $2 AND $3
            """, user_id, hour_start, hour_end)
        
        return {
            'api_requests_per_hour': float(stats['api_requests_per_hour'] or 0),
            'unique_endpoints_accessed': float(stats['unique_endpoints_accessed'] or 0),
            'failed_request_ratio': float(stats['failed_request_ratio'] or 0),
            'data_access_volume_mb': float(stats['data_access_volume_mb'] or 0)
        }
    
    async def _get_ip_reputation(self, ip_address: str) -> float:
        """Get IP reputation score (mock implementation)"""
        # In production, would integrate with threat intelligence services
        if ip_address and ip_address.startswith('10.'):
            return 95.0  # Internal IP, high reputation
        elif ip_address and ip_address.startswith('192.168.'):
            return 90.0  # Private IP, good reputation
        else:
            return 75.0  # External IP, moderate reputation
    
    async def _calculate_geolocation_entropy(self, user_id: str) -> float:
        """Calculate geolocation entropy for user"""
        async with self.db_pool.acquire() as conn:
            locations = await conn.fetch("""
                SELECT geolocation, COUNT(*) as count
                FROM behavior_events 
                WHERE user_id = $1 
                AND timestamp > NOW() - INTERVAL '7 days'
                AND geolocation IS NOT NULL
                GROUP BY geolocation
            """, user_id)
        
        if not locations:
            return 0.0
        
        # Calculate Shannon entropy
        total_events = sum(loc['count'] for loc in locations)
        entropy = 0.0
        
        for location in locations:
            probability = location['count'] / total_events
            if probability > 0:
                entropy -= probability * np.log2(probability)
        
        return entropy
    
    async def _get_or_create_user_profile(self, user_id: str) -> UserBehaviorProfile:
        """Get existing user profile or create new baseline"""
        if user_id in self.user_profiles:
            return self.user_profiles[user_id]
        
        # Create new profile based on recent activity
        profile = await self._create_user_baseline(user_id)
        self.user_profiles[user_id] = profile
        
        return profile
    
    async def _create_user_baseline(self, user_id: str) -> UserBehaviorProfile:
        """Create behavioral baseline for user"""
        async with self.db_pool.acquire() as conn:
            # Get recent behavior data
            recent_events = await conn.fetch("""
                SELECT * FROM behavior_events 
                WHERE user_id = $1 
                AND timestamp > NOW() - INTERVAL '30 days'
                ORDER BY timestamp DESC
                LIMIT 1000
            """, user_id)
        
        if not recent_events:
            # Return default profile for new users
            return UserBehaviorProfile(
                user_id=user_id,
                typical_login_hours=[9, 10, 11, 14, 15, 16],
                common_ip_addresses=[],
                usual_geolocation=None,
                average_session_duration=30.0,
                typical_api_endpoints=[],
                normal_data_access_patterns={},
                baseline_features={col: 0.0 for col in self.feature_columns},
                profile_confidence=0.0,
                last_updated=datetime.now()
            )
        
        # Calculate baseline statistics
        login_hours = [event['timestamp'].hour for event in recent_events]
        ip_addresses = [event['ip_address'] for event in recent_events if event['ip_address']]
        session_durations = [event['duration_ms'] / (1000 * 60) for event in recent_events if event['duration_ms']]
        
        # Calculate baseline features
        features_df = pd.DataFrame([
            json.loads(event.get('features', '{}')) for event in recent_events
        ])
        
        baseline_features = {}
        if not features_df.empty:
            for col in self.feature_columns:
                if col in features_df.columns:
                    baseline_features[col] = float(features_df[col].mean())
                else:
                    baseline_features[col] = 0.0
        
        profile = UserBehaviorProfile(
            user_id=user_id,
            typical_login_hours=list(set(login_hours)),
            common_ip_addresses=list(set(ip_addresses))[:10],  # Top 10 IPs
            usual_geolocation=recent_events[0].get('geolocation') if recent_events else None,
            average_session_duration=np.mean(session_durations) if session_durations else 30.0,
            typical_api_endpoints=list(set([e.get('api_endpoint') for e in recent_events if e.get('api_endpoint')]))[:20],
            normal_data_access_patterns={},
            baseline_features=baseline_features,
            profile_confidence=min(1.0, len(recent_events) / 100.0),  # Confidence based on data volume
            last_updated=datetime.now()
        )
        
        # Store profile
        await self._store_user_profile(profile)
        
        return profile
    
    async def _store_user_profile(self, profile: UserBehaviorProfile):
        """Store user behavioral profile"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_behavior_profiles 
                (user_id, typical_login_hours, common_ip_addresses, usual_geolocation,
                 average_session_duration, typical_api_endpoints, normal_data_access_patterns,
                 baseline_features, profile_confidence, last_updated)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (user_id) DO UPDATE SET
                    typical_login_hours = EXCLUDED.typical_login_hours,
                    common_ip_addresses = EXCLUDED.common_ip_addresses,
                    usual_geolocation = EXCLUDED.usual_geolocation,
                    average_session_duration = EXCLUDED.average_session_duration,
                    typical_api_endpoints = EXCLUDED.typical_api_endpoints,
                    normal_data_access_patterns = EXCLUDED.normal_data_access_patterns,
                    baseline_features = EXCLUDED.baseline_features,
                    profile_confidence = EXCLUDED.profile_confidence,
                    last_updated = EXCLUDED.last_updated
            """, 
                profile.user_id, json.dumps(profile.typical_login_hours),
                json.dumps(profile.common_ip_addresses), profile.usual_geolocation,
                profile.average_session_duration, json.dumps(profile.typical_api_endpoints),
                json.dumps(profile.normal_data_access_patterns),
                json.dumps(profile.baseline_features), profile.profile_confidence,
                profile.last_updated
            )
    
    async def _detect_isolation_forest_anomalies(self, event: BehaviorEvent, 
                                               features: Dict[str, float],
                                               profile: UserBehaviorProfile) -> List[BehaviorAnomaly]:
        """Detect anomalies using Isolation Forest"""
        anomalies = []
        
        try:
            # Prepare feature vector
            feature_vector = [features.get(col, 0) for col in self.feature_columns]
            feature_vector_scaled = self.scaler.transform([feature_vector])
            
            # Predict anomaly
            anomaly_score = self.isolation_forest.decision_function(feature_vector_scaled)[0]
            is_anomaly = self.isolation_forest.predict(feature_vector_scaled)[0] == -1
            
            if is_anomaly:
                # Determine specific anomaly type based on feature deviations
                anomaly_type = self._classify_anomaly_type(features, profile)
                severity = self._calculate_anomaly_severity(anomaly_score, features, profile)
                
                anomaly = BehaviorAnomaly(
                    anomaly_id=f"if_{event.event_id}_{int(event.timestamp.timestamp())}",
                    user_id=event.user_id,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    confidence_score=abs(anomaly_score),
                    detected_at=event.timestamp,
                    event_ids=[event.event_id],
                    baseline_deviation=self._calculate_baseline_deviation(features, profile),
                    risk_factors=self._identify_risk_factors(features, profile),
                    context={
                        "detection_method": "isolation_forest",
                        "anomaly_score": float(anomaly_score),
                        "feature_values": features
                    },
                    recommended_actions=self._get_recommended_actions(anomaly_type)
                )
                anomalies.append(anomaly)
        
        except Exception as e:
            logger.error(f"Error in isolation forest detection: {e}")
        
        return anomalies
    
    def _classify_anomaly_type(self, features: Dict[str, float], 
                             profile: UserBehaviorProfile) -> AnomalyType:
        """Classify the type of anomaly based on feature deviations"""
        baseline = profile.baseline_features
        
        # Check for specific anomaly patterns
        if features.get('hour_of_day', 12) not in profile.typical_login_hours:
            return AnomalyType.UNUSUAL_LOGIN_TIME
        
        if features.get('data_access_volume_mb', 0) > baseline.get('data_access_volume_mb', 0) * 5:
            return AnomalyType.BULK_DATA_DOWNLOAD
        
        if features.get('api_requests_per_hour', 0) > baseline.get('api_requests_per_hour', 0) * 3:
            return AnomalyType.SUSPICIOUS_API_USAGE
        
        if features.get('session_duration_minutes', 0) > baseline.get('session_duration_minutes', 0) * 3:
            return AnomalyType.ABNORMAL_SESSION_DURATION
        
        if features.get('geolocation_entropy', 0) > 2.0:
            return AnomalyType.UNUSUAL_GEOLOCATION
        
        if features.get('failed_request_ratio', 0) > 0.5:
            return AnomalyType.SUSPICIOUS_API_USAGE
        
        return AnomalyType.ATYPICAL_NAVIGATION  # Default
    
    def _calculate_anomaly_severity(self, anomaly_score: float, 
                                   features: Dict[str, float],
                                   profile: UserBehaviorProfile) -> AnomalySeverity:
        """Calculate severity of detected anomaly"""
        # Base severity on anomaly score and feature deviations
        baseline = profile.baseline_features
        
        # Calculate maximum deviation from baseline
        max_deviation = 0.0
        for feature, value in features.items():
            if feature in baseline and baseline[feature] > 0:
                deviation = abs(value - baseline[feature]) / baseline[feature]
                max_deviation = max(max_deviation, deviation)
        
        # Combine anomaly score and deviation
        severity_score = (abs(anomaly_score) + max_deviation) / 2
        
        if severity_score > 0.8:
            return AnomalySeverity.CRITICAL
        elif severity_score > 0.6:
            return AnomalySeverity.HIGH
        elif severity_score > 0.4:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

# Continue with remaining methods...
# [The file would continue with implementations for LSTM detection, statistical detection, 
# rule-based detection, and other helper methods]

# Global ML anomaly detector instance
ml_anomaly_detector = MLAnomalyDetector()

# Initialize ML anomaly detection
async def initialize_ml_anomaly_detection():
    """Initialize ML anomaly detection system"""
    await ml_anomaly_detector.initialize()
    logfire.info("ML anomaly detection system ready")