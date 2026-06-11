"""
Plugin registry - auto-discovers all plugins in the plugins/ folder.
To add a new file type:
  1. Create plugins/myformat_plugin.py
  2. Inherit from BasePlugin
  3. Set SUPPORTED_EXTENSIONS = [".myformat"]
  4. Implement extract()
  No other changes needed.
"""
import importlib
import os
import pkgutil
import logging
from typing import Dict, Optional, List
from plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(self):
        self._registry: Dict[str, BasePlugin] = {}  # ext -> plugin instance
        self._load_errors: Dict[str, str] = {}
        self._loaded_plugins: List[str] = []

    def discover_and_load(self, plugins_dir: str = "plugins") -> None:
        """Scan plugins directory and register all valid plugins."""
        import plugins as plugins_pkg

        plugin_dir_path = os.path.dirname(plugins_pkg.__file__)

        for _, module_name, _ in pkgutil.iter_modules([plugin_dir_path]):
            if module_name in ("base_plugin", "__init__"):
                continue
            try:
                module = importlib.import_module(f"plugins.{module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BasePlugin)
                        and attr is not BasePlugin
                    ):
                        instance = attr()
                        for ext in instance.get_supported_extensions():
                            self._registry[ext] = instance
                            logger.info(f"Registered plugin {attr_name} for {ext}")
                        self._loaded_plugins.append(attr_name)
            except Exception as e:
                self._load_errors[module_name] = str(e)
                logger.error(f"Failed to load plugin {module_name}: {e}")

        logger.info(f"Plugin discovery complete. Registered extensions: {list(self._registry.keys())}")

    def get_plugin(self, file_path: str) -> Optional[BasePlugin]:
        ext = os.path.splitext(file_path)[1].lower()
        return self._registry.get(ext)

    def supported_extensions(self) -> List[str]:
        return list(self._registry.keys())

    def get_load_errors(self) -> Dict[str, str]:
        return self._load_errors

    def get_loaded_plugins(self) -> List[str]:
        return self._loaded_plugins


# Global registry instance
registry = PluginRegistry()
