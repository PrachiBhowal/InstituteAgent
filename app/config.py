from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_api_key: str = ""
    llm_provider: str = "mock"  # mock | openai_compatible
    llm_base_url: str = ""
    llm_model_main: str = ""
    llm_model_fast: str = ""
    embedding_model: str = "multilingual-e5-small"

    institute_name: str = "the Institute"
    institute_tz: str = "Asia/Kolkata"

    classifier_threshold: float = 0.55
    max_tool_calls: int = 3
    pending_ttl_seconds: int = 300   # confirm window for write actions

    admin_contact_name: str = "Admin Office"
    admin_contact_email: str = ""
    admin_contact_phone: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
