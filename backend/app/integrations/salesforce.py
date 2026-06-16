"""
Integração Salesforce — Fase 2
Busca dados de oportunidades quando API estiver disponível.

Para ativar: preencher variáveis SALESFORCE_* no .env
"""
from app.config import settings


class SalesforceClient:
    """
    Cliente para a API do Salesforce.
    Retorna dados estruturados de oportunidades para o agente TCO.
    """

    def __init__(self):
        self.configured = settings.salesforce_configured
        self._token = None

    async def get_opportunity(self, opportunity_id: str) -> dict | None:
        """
        Busca uma oportunidade pelo ID do Salesforce.
        Retorna os campos relevantes para o TCO:
        - customer_name
        - product
        - volume_mt
        - competitor_name
        - competitor_sku
        - region
        """
        if not self.configured:
            return None

        # TODO: implementar autenticação OAuth2 e chamada à API
        # Documentação: https://developer.salesforce.com/docs/apis
        raise NotImplementedError("Salesforce integration — Fase 2")

    async def save_tco_to_opportunity(self, opportunity_id: str, tco_data: dict) -> bool:
        """
        Salva o TCO gerado como anexo na oportunidade do Salesforce.
        """
        if not self.configured:
            return False

        raise NotImplementedError("Salesforce integration — Fase 2")


# Instância global — reutilizada entre requests
salesforce = SalesforceClient()
