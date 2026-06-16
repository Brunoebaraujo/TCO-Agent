# TCO Engine — AI-Powered Total Cost of Ownership

Plataforma de análise de TCO para Goodpack, com agente IA que gera comparações competitivas automaticamente.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | React + Vite + TailwindCSS |
| Backend | Python 3.12 + FastAPI |
| Banco | PostgreSQL 16 |
| IA | Claude API (Anthropic) |
| Hospedagem | Railway |
| CI/CD | GitHub → Railway (automático) |

## Estrutura do repositório

```
tco-engine/
├── frontend/          # React app (interface do vendedor)
│   └── src/
│       ├── components/
│       │   ├── chat/  # Interface de conversa com o agente
│       │   ├── tco/   # Summary visual, formulário de input
│       │   └── ui/    # Componentes reutilizáveis
│       ├── pages/     # Páginas da aplicação
│       ├── hooks/     # React hooks customizados
│       └── lib/       # Utilitários e cliente de API
├── backend/           # FastAPI + motor de cálculo
│   └── app/
│       ├── api/       # Endpoints REST
│       ├── agent/     # Orquestração Claude API
│       ├── calculator/ # Motor de cálculo TCO (lógica do Excel)
│       ├── integrations/ # Salesforce (fase 2), exports PPT/PDF
│       └── db/        # Migrations, modelos, schema SQL
├── docs/              # Documentação do projeto
└── railway.toml       # Configuração de deploy Railway
```

## Setup local

### Pré-requisitos
- Node.js 20+
- Python 3.12+
- PostgreSQL 16+

### 1. Clonar e configurar variáveis

```bash
git clone https://github.com/SEU_USUARIO/tco-engine.git
cd tco-engine
cp .env.example .env
# Editar .env com suas chaves
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head             # Rodar migrations
uvicorn app.main:app --reload    # Servidor em http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                      # App em http://localhost:5173
```

## Deploy no Railway

1. Criar conta em [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo → selecionar este repositório
3. Railway detecta automaticamente frontend e backend
4. Adicionar variáveis de ambiente no painel Railway
5. Cada `git push main` faz deploy automático

## Variáveis de ambiente

Ver `.env.example` para a lista completa. As principais:

```
ANTHROPIC_API_KEY=        # Chave Claude API
DATABASE_URL=             # PostgreSQL connection string (Railway fornece automaticamente)
SALESFORCE_CLIENT_ID=     # Fase 2 — quando acesso for liberado
SALESFORCE_CLIENT_SECRET= # Fase 2
```

## Fases do projeto

- **Fase 1 (atual):** Base de conhecimento + Motor de cálculo + Agente IA + Interface web
- **Fase 2:** Integração Salesforce + Export PowerPoint automático
- **Fase 3:** Alertas de validade de dados + Dashboard de win/loss
