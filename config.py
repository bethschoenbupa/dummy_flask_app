import os
from dotenv import load_dotenv

import variables as vr

load_dotenv()
load_dotenv(vr.gcp_env_file)

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('FLASK_SECRET', 'a-default-secret-key-for-dev')
    TESTING = False
    DEBUG = False
    RATELIMIT_ENABLED = False
    # Default for cloud logging
    CLOUD_SAVE_LOGGING = os.environ.get("CLOUD_SAVE_LOGGING", "false").lower() in ('true', '1')
    USE_CLOUD_PROMPTS = False
    # Default route limit
    ROUTE_LIMIT = os.environ.get("ROUTE_LIMIT", "1000 per hour")
    ENABLE_REQUEST_LOGGING = True

    # Shadow traffic settings are controlled from per‑environment config in the config folder.
    # Disabled by default to prevent accidental use in production.
    SHADOW_TRAFFIC_TOPIC = os.getenv("SHADOW_TRAFFIC_TOPIC")
    ALLOW_SHADOW_TRAFFIC = os.getenv("ALLOW_SHADOW_TRAFFIC", "false").lower() == "true"
    
    # Caching
    ENABLE_CACHING = True
    CACHE_TYPE = "SimpleCache"
    # measured in seconds - default is a day
    CACHE_DEFAULT_TIMEOUT = 24 * 60 * 60   
    
class ProductionConfig(Config):
    """Production configuration."""
    # Production should get its secret key from the environment
    SECRET_KEY = os.environ.get('FLASK_SECRET')
    # Ensure cloud logging is explicitly enabled or disabled based on env for prod
    CLOUD_SAVE_LOGGING = os.environ.get("CLOUD_SAVE_LOGGING", "true").lower() in ('true', '1')

    ENABLE_CACHING = True
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 24 * 60 * 60))

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    CLOUD_SAVE_LOGGING = False
    ALLOW_SHADOW_TRAFFIC = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True    
    # Use a fixed, simple secret key for tests
    SECRET_KEY = 'test-secret-key'    
    CLOUD_SAVE_LOGGING = False 
    USE_CLOUD_PROMPTS = False   
    # don't save any logs
    ENABLE_REQUEST_LOGGING = False
    ALLOW_SHADOW_TRAFFIC = True

    ENABLE_CACHING = False

# A dictionary to map string names to the config classes
config_by_name = {
    'production': ProductionConfig,
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
