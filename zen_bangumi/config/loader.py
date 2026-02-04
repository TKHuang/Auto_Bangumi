"""Config loader with JSON persistence and environment variable override support."""

import json
import logging
import os
from pathlib import Path

from .models import ZenBangumiConfig

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("data")
CONFIG_PATH = CONFIG_DIR / "config.json"


class ConfigLoader:
    """Load, save, and manage ZenBangumi configuration."""

    CONFIG_PATH = CONFIG_PATH

    @staticmethod
    def load() -> ZenBangumiConfig:
        """Load config from JSON file or create default if not exists."""
        if CONFIG_PATH.exists():
            return ConfigLoader._load_from_file()
        else:
            logger.info("Config file not found, creating default config")
            config = ZenBangumiConfig()
            ConfigLoader.save(config)
            return config

    @staticmethod
    def _load_from_file() -> ZenBangumiConfig:
        """Load config from JSON file with env var override."""
        try:
            with open(ConfigLoader.CONFIG_PATH, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            logger.info(f"Config loaded from {ConfigLoader.CONFIG_PATH}")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config: {e}, using defaults")
            return ZenBangumiConfig()

        config_dict = ConfigLoader._apply_env_overrides(config_dict)
        try:
            return ZenBangumiConfig(**config_dict)
        except Exception as e:
            logger.error(f"Config validation failed: {e}, using defaults")
            return ZenBangumiConfig()

    @staticmethod
    def _apply_env_overrides(config_dict: dict) -> dict:
        """Apply environment variable overrides to config dict.

        Env var format: ZEN_{SECTION}_{FIELD}
        Example: ZEN_DOWNLOADER_HOST=localhost:8080
        """
        env_prefix = "ZEN_"

        for key, value in os.environ.items():
            if not key.startswith(env_prefix):
                continue

            remainder = key[len(env_prefix) :].lower()

            section = None
            field = None

            for section_name in config_dict.keys():
                if remainder.startswith(section_name.replace("_", "")):
                    section = section_name
                    field = remainder[len(section_name.replace("_", "")) + 1 :]
                    break

            if section is None or field is None:
                continue

            if field not in config_dict[section]:
                continue

            env_value = value
            current_value = config_dict[section][field]

            if isinstance(current_value, bool):
                env_value = value.lower() in ("true", "1", "yes")
            elif isinstance(current_value, int):
                try:
                    env_value = int(value)
                except ValueError:
                    logger.warning(f"Invalid int value for {key}: {value}")
                    continue
            elif isinstance(current_value, list):
                env_value = value.split(",")

            config_dict[section][field] = env_value
            logger.info(f"Config override from env: {section}.{field}")

        return config_dict

    @staticmethod
    def save(config: ZenBangumiConfig) -> None:
        """Save config to JSON file."""
        ConfigLoader.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        config_dict = config.model_dump(by_alias=True)
        try:
            with open(ConfigLoader.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            logger.info(f"Config saved to {ConfigLoader.CONFIG_PATH}")
        except IOError as e:
            logger.error(f"Failed to save config: {e}")


def get_config() -> ZenBangumiConfig:
    """Get the global config instance."""
    return ConfigLoader.load()
