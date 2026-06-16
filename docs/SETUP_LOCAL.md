# Setup local (sem custo de hospedagem)

Este guia roda o TCO Engine inteiramente na sua máquina — sem Railway, sem PostgreSQL hospedado.
Único custo possível: uso da Claude API, que começa com ~$5 de crédito gratuito.

---

## Pré-requisitos

- Python 3.12+ ([python.org](https://python.org))
- Node.js 20+ ([nodejs.org](https://nodejs.org))
- Sua `ANTHROPIC_API_KEY` (já criada em console.anthropic.com)

Verificar se já tem instalado:
```bash
python3 --version
node --version
```

---

## 1. Configurar variáveis de ambiente

Na raiz do projeto:
```bash
cp .env.example .env
```

Abra o `.env` num editor de texto e preencha **apenas** esta linha:
```
ANTHROPIC_API_KEY=sk-ant-sua-chave-aqui
```

Todo o resto já tem valores padrão prontos para uso local (SQLite, secret key de desenvolvimento, etc).

---

## 2. Rodar o backend

```bash
cd backend
python3 -m venv venv

# Ativar o ambiente virtual:
source venv/bin/activate          # Mac/Linux
venv\Scripts\activate             # Windows

pip install -r requirements.txt
```

Copiar o `.env` da raiz para dentro de `backend/` (o FastAPI lê o `.env` da pasta onde é executado):
```bash
cp ../.env .env
```

Iniciar o servidor:
```bash
uvicorn app.main:app --reload
```

Se tudo certo, deve aparecer:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Teste no navegador: **http://localhost:8000/health** — deve responder `{"status":"ok"}`.

Na primeira execução, um arquivo `tco_local.db` é criado automaticamente dentro de `backend/` — esse é o seu banco SQLite com todas as tabelas do schema.

---

## 3. Rodar o frontend

Em **outro terminal** (deixe o backend rodando no primeiro):

```bash
cd frontend
npm install
npm run dev
```

Deve aparecer:
```
Local: http://localhost:5173/
```

Abra esse endereço no navegador — é a interface do TCO Engine.

---

## 4. Testar o fluxo completo

1. Acesse http://localhost:5173
2. Vá em **New TCO** (chat)
3. Digite algo como: *"Cliente Nestlé, 800 MT de Palm Oil, concorrente Octabin"*
4. O agente deve responder usando a Claude API

Se o agente responder com erro, confira o terminal do backend — a mensagem de erro ali costuma indicar exatamente o que falta (chave inválida, etc).

---

## Quando migrar para hospedagem

Esse setup local é perfeito para validar a ideia com você mesmo e talvez 1-2 vendedores próximos, testando no mesmo Wi-Fi. Quando quiser que **qualquer vendedor, de qualquer lugar**, acesse o sistema, aí sim faz sentido:

1. Trocar SQLite por PostgreSQL (mudar uma linha no `.env`)
2. Hospedar em Railway, Render ou similar (os arquivos `railway.toml` já estão no projeto, prontos para esse momento)

Não precisa decidir isso agora — primeiro valide se o agente gera TCOs úteis.
