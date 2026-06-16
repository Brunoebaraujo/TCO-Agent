"""
Configurações da aplicação — carregadas do .env
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # IA
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    # Banco — padrão SQLite local, zero configuração necessária
    database_url: str = "sqlite:///./tco_local.db"

    # App
    secret_key: str = "dev-secret-key-troque-isso-em-producao"
    environment: str = "development"

    # Tipado como str (não List) para evitar que pydantic-settings exija JSON
    # no .env. Convertido para lista via propriedade cors_origins abaixo.
    cors_origins_raw: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")

    # Salesforce (fase 2 — opcionais)
    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    salesforce_username: str = ""
    salesforce_password: str = ""
    salesforce_security_token: str = ""
    salesforce_instance_url: str = ""

    @property
    def cors_origins(self) -> List[str]:
        """
        Aceita no .env tanto uma URL simples (http://a.com) quanto
        múltiplas separadas por vírgula (http://a.com,http://b.com)
        ou formato JSON (["http://a.com"]) — sem exigir sintaxe específica.
        """
        raw = self.cors_origins_raw.strip()
        if raw.startswith("["):
            import json
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def salesforce_configured(self) -> bool:
        return bool(self.salesforce_client_id and self.salesforce_client_secret)


settings = Settings()
