"""Configuration loader with environment variable substitution."""

import os
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """Loads configuration from YAML with environment variable substitution."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to config.yaml file
        """
        self.config_path = Path(config_path)
        
        # Load environment variables from .env file in project root
        # Find .env file relative to this file's location
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / ".env"
        
        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"Loaded environment variables from {env_file}")
        else:
            load_dotenv()  # Try default locations
            logger.warning(f".env file not found at {env_file}")
        
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load and parse configuration file.
        
        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        logger.info(f"Loading configuration from {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config_text = f.read()
        
        # Substitute environment variables
        config_text = self._substitute_env_vars(config_text)
        
        # Parse YAML
        config = yaml.safe_load(config_text)
        
        return config
    
    def _substitute_env_vars(self, text: str) -> str:
        """
        Substitute ${ENV_VAR} patterns with environment variable values.
        
        Args:
            text: Text containing ${ENV_VAR} patterns
            
        Returns:
            Text with substitutions applied
        """
        pattern = r'\$\{([^}]+)\}'
        
        def replacer(match):
            env_var = match.group(1)
            value = os.environ.get(env_var)
            
            if value is None:
                logger.warning(f"Environment variable {env_var} not found")
                return match.group(0)  # Keep original if not found
            
            return value
        
        return re.sub(pattern, replacer, text)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., 'api.base_url')
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration section."""
        return self.config.get('api', {})
    
    def get_filters_config(self) -> Dict[str, Any]:
        """Get filters configuration section."""
        return self.config.get('filters', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration section."""
        return self.config.get('database', {})
    
    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration section."""
        return self.config.get('output', {})
