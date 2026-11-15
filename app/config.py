from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    keitaro_url: str = "https://tlgk.host"
    keitaro_api_key: str = ""
    database_url: str = "sqlite:///./keitaro_wrapper.db"
    default_group_id: int | None = None
    default_domain_id: int | None = None
    default_source_id: int | None = None


settings = Settings()
