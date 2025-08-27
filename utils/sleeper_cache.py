"""
Player data cache manager for Sleeper API data.

This module handles caching of Sleeper player data to avoid repeated API calls
and ensure fresh data is fetched once per day.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from pathlib import Path
import time

from api.sleeper_api import SleeperAPI
from utils.path_utils import get_data_dir, ensure_dir_exists


class SleeperPlayerCache:
    """Manages caching of Sleeper player data."""
    
    def __init__(self, cache_hours: int = 24):
        """
        Initialize the player cache manager.
        
        Args:
            cache_hours: Hours before cache expires (default 24 hours)
        """
        self.cache_hours = cache_hours
        self.cache_dir = get_data_dir() / "cache"
        self.cache_file = self.cache_dir / "sleeper_players.json"
        self.meta_file = self.cache_dir / "sleeper_players_meta.json"
        self.sleeper_api = SleeperAPI()
        
        # Ensure cache directory exists
        ensure_dir_exists(self.cache_dir)
    
    def _get_cache_metadata(self) -> Dict[str, Any]:
        """Get cache metadata including last update time."""
        if not self.meta_file.exists():
            return {
                'last_updated': None,
                'player_count': 0,
                'cache_version': '1.0'
            }
        
        try:
            with open(self.meta_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {
                'last_updated': None,
                'player_count': 0,
                'cache_version': '1.0'
            }
    
    def _save_cache_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save cache metadata."""
        try:
            with open(self.meta_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache metadata: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if the current cache is still valid."""
        if not self.cache_file.exists():
            return False
        
        metadata = self._get_cache_metadata()
        last_updated = metadata.get('last_updated')
        
        if not last_updated:
            return False
        
        try:
            last_update_time = datetime.fromisoformat(last_updated)
            expiry_time = last_update_time + timedelta(hours=self.cache_hours)
            return datetime.now() < expiry_time
        except (ValueError, TypeError):
            return False
    
    def _load_cached_players(self) -> Optional[Dict[str, Any]]:
        """Load players from cache file."""
        if not self.cache_file.exists():
            return None
        
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
    
    def _save_players_to_cache(self, players_data: Dict[str, Any]) -> None:
        """Save players data to cache file."""
        try:
            # Save player data
            with open(self.cache_file, 'w') as f:
                json.dump(players_data, f, separators=(',', ':'))
            
            # Save metadata
            metadata = {
                'last_updated': datetime.now().isoformat(),
                'player_count': len(players_data),
                'cache_version': '1.0',
                'file_size_mb': round(os.path.getsize(self.cache_file) / (1024 * 1024), 2)
            }
            self._save_cache_metadata(metadata)
            
            print(f"Cached {len(players_data)} players to {self.cache_file}")
            print(f"   Cache size: {metadata['file_size_mb']} MB")
            
        except Exception as e:
            print(f"Error saving players to cache: {e}")
    
    def get_players(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get player data, either from cache or fresh from API.
        
        Args:
            force_refresh: Force fetch from API even if cache is valid
            
        Returns:
            Dictionary of player data keyed by player ID
        """
        # Check if we should use cached data
        if not force_refresh and self._is_cache_valid():
            print("Loading players from cache...")
            cached_players = self._load_cached_players()
            if cached_players:
                metadata = self._get_cache_metadata()
                print(f"   Loaded {metadata.get('player_count', 0)} players from cache")
                print(f"   Last updated: {metadata.get('last_updated', 'Unknown')}")
                return cached_players
        
        # Fetch fresh data from API
        print("Fetching fresh player data from Sleeper API...")
        print("   This may take a moment due to the large dataset...")
        
        start_time = time.time()
        
        try:
            players_data = self.sleeper_api.get_all_players()
            
            if not players_data:
                print("No player data received from API")
                # Try to return cached data as fallback
                cached_players = self._load_cached_players()
                if cached_players:
                    print("   Falling back to cached data")
                    return cached_players
                return {}
            
            elapsed_time = time.time() - start_time
            print(f"   Fetched {len(players_data)} players in {elapsed_time:.1f}s")
            
            # Save to cache
            self._save_players_to_cache(players_data)
            
            return players_data
            
        except Exception as e:
            print(f"Error fetching player data: {e}")
            # Try to return cached data as fallback
            cached_players = self._load_cached_players()
            if cached_players:
                print("   Falling back to cached data")
                return cached_players
            return {}
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the current cache."""
        metadata = self._get_cache_metadata()
        
        cache_exists = self.cache_file.exists()
        cache_valid = self._is_cache_valid()
        
        info = {
            'cache_exists': cache_exists,
            'cache_valid': cache_valid,
            'cache_file': str(self.cache_file),
            'metadata': metadata
        }
        
        if cache_exists:
            try:
                file_stat = os.stat(self.cache_file)
                info['file_size_mb'] = round(file_stat.st_size / (1024 * 1024), 2)
                info['file_modified'] = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            except OSError:
                pass
        
        return info
    
    def clear_cache(self) -> bool:
        """Clear the player cache."""
        try:
            if self.cache_file.exists():
                os.remove(self.cache_file)
            if self.meta_file.exists():
                os.remove(self.meta_file)
            print("Player cache cleared")
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False


# Global cache instance
_player_cache = None

def get_player_cache() -> SleeperPlayerCache:
    """Get the global player cache instance."""
    global _player_cache
    if _player_cache is None:
        _player_cache = SleeperPlayerCache()
    return _player_cache

def get_sleeper_players(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Convenience function to get Sleeper player data.
    
    Args:
        force_refresh: Force refresh from API
        
    Returns:
        Dictionary of player data
    """
    cache = get_player_cache()
    return cache.get_players(force_refresh)
