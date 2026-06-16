# Setup: GitHub + Railway

Guia para colocar o TCO Engine no ar pela primeira vez.

---

## 1. Criar o repositório no GitHub

1. Acesse [github.com/new](https://github.com/new)
2. Nome: `tco-engine`
3. Visibilidade: **Private** (recomendado — contém lógica comercial)
4. Não inicializar com README (já temos)
5. Criar repositório

## 2. Fazer o primeiro push

No terminal, dentro da pasta `tco-engine`:

```bash
git init
git add .
git commit -m "feat: initial project structure"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/tco-engine.git
git push -u origin main
```

## 3. Criar projeto no Railway

1. Acesse [railway.app](https://railway.app) → **New Project**
2. Selecionar **Deploy from GitHub repo**
3. Autorizar Railway a acessar seu GitHub
4. Selecionar o repositório `tco-engine`
5. Railway detecta automaticamente o `railway.toml`

## 4. Adicionar PostgreSQL

1. No painel Railway → **+ New Service** → **Database** → **PostgreSQL**
2. Railway injeta automaticamente `DATABASE_URL` no ambiente

## 5. Configurar variáveis de ambiente

No painel Railway, em cada serviço, adicionar:

**Backend:**
```
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=<gerar com: python -c "import secrets; print(secrets.token_hex(32))">
ENVIRONMENT=production
CORS_ORIGINS=https://tco-engine-frontend.up.railway.app
```

**Frontend:**
```
VITE_API_URL=https://tco-engine-backend.up.railway.app
```

## 6. Deploy automático

A partir de agora, cada `git push main` dispara um novo deploy automaticamente.

```bash
# Fluxo de trabalho normal
git add .
git commit -m "feat: implement TCO calculator"
git push
# Railway faz o deploy em ~2 minutos
```

## 7. Acessar a aplicação

Railway gera URLs públicas para cada serviço:
- Frontend: `https://tco-engine-frontend.up.railway.app`
- Backend: `https://tco-engine-backend.up.railway.app`
- Health check: `https://tco-engine-backend.up.railway.app/health`

---

## Adicionar vendedores como usuários

Por enquanto (fase 1 sem auth completo): compartilhar a URL do frontend.
Na fase 2, adicionar autenticação por email ou SSO corporativo.
