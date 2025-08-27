"""Configuration management for the auction draft tool."""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class DraftConfig:
    """Configuration for auction draft settings."""
    budget: int = 200
    num_teams: int = 10
    sleeper_draft_id: Optional[str] = None
    sleeper_user_id: Optional[str] = None
    sleeper_username: Optional[str] = None
    refresh_interval: int = 30
    roster_positions: Dict[str, int] = None
    strategy_type: str = "value"
    data_source: str = "fantasypros"  # fantasypros or sleeper
    data_path: str = "data/data/sheets"
    min_projected_points: float = 0.0
    
    def __post_init__(self):
        """Set default roster positions if not provided."""
        if self.roster_positions is None:
            self.roster_positions = {
                "QB": 1,
                "RB": 2,
                "WR": 2,
                "TE": 1,
                "FLEX": 2,
                "K": 1,
                "DST": 1,
                "BN": 5
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DraftConfig':
        """Create from dictionary."""
        return cls(**data)


class ConfigManager:
    """Manages configuration loading and saving for the auction draft tool."""
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "config.json")
        self._config: Optional[DraftConfig] = None
        
    def load_config(self, reload: bool = False) -> DraftConfig:
        """
        Load configuration from file.
        
        Args:
            reload: Force reload from file even if already loaded
            
        Returns:
            DraftConfig object
        """
        if self._config is not None and not reload:
            return self._config
            
        if not os.path.exists(self.config_file):
            # Create default config file if it doesn't exist
            self._config = DraftConfig()
            self.save_config()
            return self._config
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Handle legacy config format and add missing fields
            config_data = self._migrate_config(data)
            self._config = DraftConfig.from_dict(config_data)
            
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            print(f"Error loading config: {e}")
            print("Using default configuration")
            self._config = DraftConfig()
            
        return self._config
    
    def save_config(self, config: Optional[DraftConfig] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save (uses current if not provided)
        """
        if config is not None:
            self._config = config
            
        if self._config is None:
            raise ValueError("No configuration to save")
            
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def update_config(self, **kwargs) -> DraftConfig:
        """
        Update configuration with new values.
        
        Args:
            **kwargs: Configuration values to update
            
        Returns:
            Updated configuration
        """
        config = self.load_config()
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                print(f"Warning: Unknown config field '{key}'")
                
        self.save_config(config)
        return config
    
    def get_sleeper_config(self) -> Dict[str, Optional[str]]:
        """Get Sleeper-specific configuration."""
        config = self.load_config()
        return {
            'draft_id': config.sleeper_draft_id,
            'user_id': config.sleeper_user_id,
            'username': config.sleeper_username
        }
    
    def get_roster_config(self) -> Dict[str, int]:
        """Get roster configuration."""
        config = self.load_config()
        return config.roster_positions
    
    def get_draft_settings(self) -> Dict[str, Any]:
        """Get draft-specific settings."""
        config = self.load_config()
        return {
            'budget': config.budget,
            'num_teams': config.num_teams,
            'roster_positions': config.roster_positions,
            'strategy_type': config.strategy_type
        }
    
    def get_data_settings(self) -> Dict[str, Any]:
        """Get data source settings."""
        config = self.load_config()
        return {
            'data_source': config.data_source,
            'data_path': config.data_path,
            'min_projected_points': config.min_projected_points
        }
    
    def _migrate_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate older config formats to current format.
        
        Args:
            data: Raw config data from file
            
        Returns:
            Migrated config data
        """
        # Add default values for missing fields
        defaults = DraftConfig()
        migrated = defaults.to_dict()
        
        # Override with existing values
        migrated.update(data)
        
        # Handle specific migrations
        if 'BN' in migrated.get('roster_positions', {}):
            # Convert BN to BENCH if needed
            roster = migrated['roster_positions']
            if 'BENCH' not in roster and 'BN' in roster:
                roster['BENCH'] = roster.pop('BN')
        
        return migrated
    
    def reset_to_defaults(self) -> DraftConfig:
        """Reset configuration to defaults."""
        self._config = DraftConfig()
        self.save_config()
        return self._config
    
    def __str__(self) -> str:
        """String representation."""
        config = self.load_config()
        return f"ConfigManager(budget=${config.budget}, teams={config.num_teams}, strategy={config.strategy_type})"


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: str = "config") -> ConfigManager:
    """
    Get the global configuration manager instance.
    
    Args:
        config_dir: Configuration directory
        
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager


def load_config(config_dir: str = "config", reload: bool = False) -> DraftConfig:
    """
    Convenience function to load configuration.
    
    Args:
        config_dir: Configuration directory
        reload: Force reload from file
        
    Returns:
        DraftConfig object
    """
    manager = get_config_manager(config_dir)
    return manager.load_config(reload)


def save_config(config: DraftConfig, config_dir: str = "config") -> None:
    """
    Convenience function to save configuration.
    
    Args:
        config: Configuration to save
        config_dir: Configuration directory
    """
    manager = get_config_manager(config_dir)
    manager.save_config(config)


def update_config(config_dir: str = "config", **kwargs) -> DraftConfig:
    """
    Convenience function to update configuration.
    
    Args:
        config_dir: Configuration directory
        **kwargs: Configuration values to update
        
    Returns:
        Updated configuration
    """
    manager = get_config_manager(config_dir)
    return manager.update_config(**kwargs)
