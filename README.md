# BB IA MVP — Guardião + BB Decision

Protótipo funcional das soluções **Guardião** (IA contra golpes de engenharia social) e **BB Decision** (simulador de decisões financeiras), desenvolvido para o projeto IBM × Banco do Brasil.

---

## Pré-requisitos

| Ferramenta | Versão mínima |
|---|---|
| Python | 3.12 |
| Node.js | 20 LTS |
| pip | 23+ |

---

## 1. Configurar variáveis de ambiente

```bash
cd bb-ia-mvp
cp .env.example .env
# Edite .env com suas credenciais (NUNCA comite o .env)
```

Variáveis obrigatórias:

| Variável | Descrição |
|---|---|
| `LLM_PROVIDER` | `watsonx` (padrão) ou `openai` |
| `WATSONX_API_KEY` | Chave da API IBM watsonx.ai |
| `WATSONX_PROJECT_ID` | ID do projeto IBM watsonx |
| `WATSONX_URL` | URL da instância watsonx (padrão: us-south) |
| `WATSONX_MODEL_ID` | Modelo a usar (padrão: `ibm/granite-13b-chat-v2`) |
| `OPENAI_API_KEY` | Chave OpenAI (necessária apenas se `LLM_PROVIDER=openai`) |

---

## 2. Back-end (FastAPI)

```bash
cd bb-ia-mvp/backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API disponível em: `http://localhost:8000`
Documentação OpenAPI: `http://localhost:8000/docs`

---

## 3. Testes

```bash
cd bb-ia-mvp/backend
pytest tests/ -v --tb=short
```

Para ver cobertura:

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

---

## 4. Front-end (React + Vite)

```bash
cd bb-ia-mvp/frontend
npm install
npm run dev
```

UI disponível em: `http://localhost:5173`

> O front-end espera o back-end rodando em `http://localhost:8000` (configurado via proxy Vite).
> Para alterar o endereço do back-end, crie um arquivo `.env` em `frontend/` com:
> ```
> VITE_API_URL=http://seu-backend:8000
> ```
> Por padrão (desenvolvimento local), o proxy do Vite encaminha `/api/*` automaticamente.

### Testes de componente (frontend)

```bash
cd bb-ia-mvp/frontend
npm test
```

Para modo watch:
```bash
npm run test:watch
```

---

## 5. Estrutura de Pastas

```
bb-ia-mvp/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── api/                       # Rotas REST
│   │   ├── guardiao/                  # Agente LangGraph (6 nós)
│   │   ├── bbdecision/                # Motor financeiro + narrador
│   │   ├── llm/                       # Abstração watsonx.ai / OpenAI
│   │   ├── audit/                     # Log estruturado JSON
│   │   ├── data/                      # Dados sintéticos
│   │   └── db/                        # Modelos SQLAlchemy
│   └── tests/
├── frontend/
│   └── src/
├── docs/                              # Arquitetura, OpenAPI, relatórios
├── .env.example                       # Template de variáveis (sem segredos)
└── .gitignore
```

---

## 6. Dados Sintéticos

Todos os dados de usuário, transações e casos de teste são **100% fictícios**.
Nenhum dado real de cliente é usado em nenhuma etapa.

---

## 7. Aviso Legal

> As simulações do BB Decision são **estimativas** para fins de demonstração.
> Não constituem garantia de resultado nem recomendação de investimento.

---

## 8. Segurança

- Nenhuma credencial está no código ou em arquivos versionados.
- Entradas do usuário são sanitizadas antes de chegar ao LLM (proteção anti-prompt-injection).
- Logs de auditoria não contêm dados pessoais identificáveis.

---

## 9. Documentação Adicional

| Documento | Localização |
|---|---|
| Arquitetura e decisões técnicas | `docs/architecture.md` |
| OpenAPI spec | `docs/openapi.yaml` |
| Matriz de rastreabilidade | `docs/traceability_matrix.md` |
| Relatório de IA Responsável | `docs/responsible_ai_report.md` |
