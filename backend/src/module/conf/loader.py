import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .const import ENV_TO_ATTR
from .models import Config

logger = logging.getLogger(__name__)
CONFIG_ROOT = Path("config")

try:
    from module.__version__ import VERSION
except ImportError:
    logger.info("Can't find version info, use DEV_VERSION instead")
    VERSION = "DEV_VERSION"

CONFIG_PATH = (
    CONFIG_ROOT / "config_dev.json"
    if VERSION == "DEV_VERSION"
    else CONFIG_ROOT / "config.json"
).resolve()


class Settings(Config):
    def __init__(self):
        super().__init__()
        if CONFIG_PATH.exists():
            self.load()
            self.save()
        else:
            self.init()

    def load(self) -> None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        config_obj = Config.model_validate(config)
        for key, value in config_obj.__dict__.items():
            setattr(self, key, value)
        logger.info("Config loaded")

    def save(self, config_dict: dict[str, object] | None = None) -> None:
        if not config_dict:
            config_dict = self.model_dump()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)

    def init(self) -> None:
        load_dotenv(".env")
        self.__load_from_env()
        self.save()

    def __load_from_env(self) -> None:
        config_dict = self.model_dump()
        for key, section in ENV_TO_ATTR.items():
            for env, attr in section.items():
                if env in os.environ:
                    if isinstance(attr, list):
                        for _attr in attr:
                            attr_name = _attr[0] if isinstance(_attr, tuple) else _attr
                            config_dict[key][attr_name] = self.__val_from_env(
                                env, _attr
                            )
                    else:
                        attr_name = attr[0] if isinstance(attr, tuple) else attr
                        config_dict[key][attr_name] = self.__val_from_env(env, attr)
        config_obj = Config.model_validate(config_dict)
        for key, value in config_obj.__dict__.items():
            setattr(self, key, value)
        logger.info("Config loaded from env")

    @staticmethod
    def __val_from_env(env: str, attr: tuple):
        if isinstance(attr, tuple):
            conv_func = attr[1]
            return conv_func(os.environ[env])
        else:
            return os.environ[env]


settings = Settings()
