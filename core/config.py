import json
import pathlib
import time
from typing import Any, Dict, Optional

CONFIG_DIRECTORY = pathlib.Path(__file__).parent.parent / "config"

class ConfigManager:
    """
    Manages loading and accessing configuration settings from JSON files.
    """
    
    def __init__(self, tiers_path: Optional[str] = None, api_keys_path: Optional[str] = None, ttl: int = 20):
        self.tiers_path = pathlib.Path(tiers_path) if tiers_path else CONFIG_DIRECTORY / "tiers.json"
        self.api_keys_path = pathlib.Path(api_keys_path) if api_keys_path else CONFIG_DIRECTORY / "api_keys.json"
        self.ttl = ttl
        
        self._tiers_cache: Optional[Dict[str, Any]] = None
        self._api_keys_cache: Optional[Dict[str, str]] = None
        self._last_load: float = 0.0
    
    def _expired(self) -> bool:
        return (time.time() - self._last_load) > self.ttl
    
    def _load_files(self):
        with self.tiers_path.open("r", encoding="utf-8") as f:
            self._tiers_cache = json.load(f)
        with self.api_keys_path.open("r", encoding="utf-8") as f:
            self._api_keys_cache = json.load(f)
        self._last_load = time.time()
        
    def get_tiers(self) -> Dict[str, Any]:
        if self._tiers_cache is None or self._expired():
            self._load_files()
        return self._tiers_cache
    
    def get_api_key_tier(self, api_key: Optional[str]) -> Optional[str]:
        if self._api_keys_cache is None or self._expired():
            self._load_files()
        if api_key is None:
            return None
        return self._api_keys_cache.get(api_key)