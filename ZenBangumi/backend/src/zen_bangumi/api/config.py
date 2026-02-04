from fastapi import APIRouter, Depends

from zen_bangumi.api.middleware.auth import get_current_user
from zen_bangumi.config.loader import ConfigLoader
from zen_bangumi.config.models import ZenBangumiConfig
from zen_bangumi.domain.models.user import User

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/")
async def get_config(current_user: User = Depends(get_current_user)):
    config = ConfigLoader.load()
    return config.model_dump_json_safe()


@router.put("/")
async def update_config(
    data: dict, current_user: User = Depends(get_current_user)
):
    config = ConfigLoader.load()
    config_dict = config.model_dump(by_alias=True)
    
    for section_name, section_data in data.items():
        if section_name in config_dict and isinstance(section_data, dict):
            if isinstance(config_dict[section_name], dict):
                config_dict[section_name].update(section_data)
            else:
                config_dict[section_name] = section_data
        else:
            config_dict[section_name] = section_data
    
    new_config = ZenBangumiConfig(**config_dict)
    ConfigLoader.save(new_config)
    
    return new_config.model_dump_json_safe()
