"""
Configurações da aplicação — carregadas do .env
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # IA
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    # Banco
    database_url: str

    # App
    secret_key: str
    environment: str = "development"
    cors_origins: List[str] = ["http://localhost:5173"]

    # Salesforce (fase 2 — opcionais)
    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    salesforce_username: str = ""
    salesforce_password: str = ""
    salesforce_security_token: str = ""
    salesforce_instance_url: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def salesforce_configured(self) -> bool:
        return bool(self.salesforce_client_id and self.salesforce_client_secret)

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
