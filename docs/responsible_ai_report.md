# Relatório de IA Responsável — BB IA MVP

> Versão: 0.1.0 | Atualizado: 2025 | Classificação: Protótipo / Não-produção  
> Este relatório cobre os compromissos e as limitações conhecidas do protótipo.  
> **Deve ser revisado por equipe jurídica e de compliance antes de qualquer uso em produção.**

---

## 1. Resumo Executivo

O BB IA MVP é um protótipo de duas soluções de IA:

1. **Guardião** — sistema agêntico de detecção de golpes de engenharia social (foco em fraudes Pix), com motor de regras determinístico e LLM opcional para narração.
2. **BB Decision** — simulador de decisões financeiras que responde perguntas "E se eu fizer X?", com motor de cálculo 100% determinístico e LLM restrito à narração de resultados.

Ambas as soluções foram projetadas com os princípios de IA Responsável como restrições de design — não como atividade pós-hoc.

---

## 2. Inventário de Usos de IA

| Sistema | Uso do modelo | Tipo | Pode causar dano direto? |
|---|---|---|---|
| Guardião — Nível 1 | Motor de regras Python (sem ML) | Determinístico | Não (falso positivo bloqueia UX, não bloqueia dinheiro) |
| Guardião — Nível 2 | Análise de perfil (heurísticas Python) | Determinístico | Não |
| Guardião — Narração | LLM (mock / watsonx.ai) | Generativo | Não (texto apenas) |
| BB Decision — Cálculo | Motor financeiro Python | Determinístico | Não |
| BB Decision — Narração | LLM (mock / watsonx.ai) | Generativo | Não (disclaimer obrigatório) |

**Nenhuma decisão financeira ou de bloqueio de conta é tomada pelo modelo.** A intervenção do Guardião é uma alerta; a operação Pix só pode ser pausada temporariamente, e o usuário tem controle total.

---

## 3. Avaliação de Risco (ALTAI adaptado)

### 3.1 Transparência e Explicabilidade

| Critério | Status | Detalhe |
|---|---|---|
| Score auditável | ✅ | Cada sinal tem `signal_id`, `label`, `evidence` e `weight` retornados na API |
| Tipo de golpe explicado | ✅ | Campos `scam_name`, `how_it_works`, `how_applied` na intervenção |
| Regras versionadas | ✅ | `RULES_VERSION = "1.1.0"` em `risk_rules.py` |
| LLM restrito à narração | ✅ | Nenhum valor numérico é calculado pelo LLM |
| Mock claramente marcado | ✅ | `LLMResponse.is_mock = True`; relatórios de avaliação rotulados |

### 3.2 Supervisão Humana

| Critério | Status | Detalhe |
|---|---|---|
| Flag de revisão humana | ✅ | `requires_human_review = True` para score ≥ 85 (tier crítico) |
| Usuário tem controle final | ✅ | `user_control_note` em toda intervenção; pausa é temporária |
| Botão para atendente | ✅ | Exibido apenas no fluxo (b) quando Pix correlacionado |
| Sem bloqueio automático | ✅ | Sistema alerta; não bloqueia conta nem cancela transações |

### 3.3 Privacidade e Proteção de Dados (LGPD)

| Critério | Status | Detalhe |
|---|---|---|
| Texto da mensagem não logado | ✅ | `audit/logger.py` persiste apenas score, sinais, timestamp, user_id |
| Dados sintéticos | ✅ | Nenhum dado real de cliente em qualquer arquivo |
| Base legal documentada | ⚠️ | LGPD art. 7º, IX (legítimo interesse — prevenção à fraude); **a validar com advogado** |
| Minimização de dados | ✅ | user_id opcional; sem dados biométricos ou de localização |
| Consentimento explícito | ✅ | Campos `monitoring_consent` e `simulation_consent` em todas as requisições |

### 3.4 Equidade e Não-discriminação

| Critério | Status | Detalhe |
|---|---|---|
| Motor de regras sem atributos protegidos | ✅ | Score baseado em padrões textuais, não em perfil demográfico |
| Perfil de usuário apenas para sensibilidade contextual | ✅ | `level2_analysis` usa histórico de transações — não raça, gênero, etc. |
| Dois perfis de linguagem | ✅ | "standard" e "low" — sem julgamento de valor sobre o usuário |
| Avaliação de viés em subgrupos | ⚠️ | **Não realizada** — dataset sintético não inclui subgrupos demográficos |

### 3.5 Robustez e Segurança

| Critério | Status | Detalhe |
|---|---|---|
| Sanitização de entrada | ✅ | `prompt_guard.py` filtra injeção de prompt, limita comprimento |
| Sem chamadas externas com dados do usuário | ✅ | Mock LLM não envia dados; provedor real só recebe texto sanitizado |
| Fallback determinístico | ✅ | BB Decision e Guardião funcionam sem LLM (mock/regex) |
| Sem autenticação no MVP | ❌ | **Endpoints abertos** — deve ser corrigido antes de qualquer deploy |
| Sem rate limiting | ❌ | **Não implementado** — necessário em produção |

### 3.6 Responsabilidade

| Critério | Status | Detalhe |
|---|---|---|
| Audit log imutável (append-only) | ✅ | JSON Lines em `logs/audit.jsonl` |
| Versão das regras no log | ✅ | Campo `rules_version` no audit log |
| Disclaimer obrigatório no BB Decision | ✅ | Campo `disclaimer` em toda resposta — nunca omitido |
| Limitações documentadas | ✅ | Este relatório + `docs/architecture.md` §8 |

---

## 4. Desempenho do Guardião (Avaliação Interna)

> ⚠️ Resultado obtido com **mock LLM** e **dados sintéticos**. Não reflete desempenho em dados reais.

### 4.1 Configuração da Avaliação

| Parâmetro | Valor |
|---|---|
| Dataset | `labeled_messages.json` (201 mensagens) |
| Split de teste | 40 mensagens |
| Motor avaliado | Rules-only (sem LLM) |
| Data | Gerado no MVP v0.1.0 |

### 4.2 Métricas (Split Teste — Rules-only)

| Métrica | Valor |
|---|---|
| Precisão | 100% |
| Recall | 44,8% |
| F1-Score | 61,9% |
| Falsos Positivos | 0 |
| Falsos Negativos | ~22 (categorias difíceis) |

### 4.3 Análise por Dificuldade

| Dificuldade | Recall |
|---|---|
| Fácil | ~85% |
| Médio | ~50% |
| Difícil | ~0% (falso_sequestro, falsa_central_cartao) |

### 4.4 Causas dos Falsos Negativos

1. **falso_sequestro** — padrões textuais menos específicos; requer análise de contexto emocional que o Nível 1 não cobre.
2. **falsa_central_cartao** — mensagens mimetizam comunicação legítima de banco; difícil separar por regex.
3. Mensagens categorizadas como "difícil" por design contêm poucas palavras-chave explícitas.

### 4.5 Ações Recomendadas

- [ ] Adicionar padrões para `falso_sequestro` em `risk_scorer.py`
- [ ] Adicionar padrões para `falsa_central_cartao` em `risk_scorer.py`
- [ ] Expandir dataset com mais exemplos difíceis de cada categoria
- [ ] Avaliar com LLM real (watsonx.ai) para comparação
- [ ] Realizar avaliação com mensagens reais (anonimizadas) em fase piloto

---

## 5. Limitações Conhecidas

| Limitação | Impacto | Mitigação |
|---|---|---|
| Dataset 100% sintético | Métricas não generalizáveis para dados reais | Fase piloto com dados reais anonimizados |
| Motor de regras cobre 8 tipos de golpe | Novos golpes não detectados | Atualização periódica das regras; LLM como camada adicional |
| Intent parser por regex | BB Decision falha em perguntas ambíguas | Substituir por LLM em produção |
| Sem autenticação | Qualquer pessoa pode chamar a API | Implementar antes de qualquer deploy |
| Sem persistência | Estado em memória; sem histórico entre sessões | Banco de dados em produção |
| Perfis sintéticos (3 usuários) | Nível 2 do Guardião limitado | Integrar com perfil real (com consentimento) |
| Base legal LGPD não validada | Risco regulatório | Revisão jurídica obrigatória |

---

## 6. Compromissos de Desenvolvimento Responsável

Os seguintes princípios foram adotados como restrições de design (não como aspirações):

1. **Nenhum número financeiro calculado por LLM** — 100% determinístico.
2. **Nenhuma decisão de bloqueio automático** — sistema alerta; humano decide.
3. **Supervisão humana obrigatória** para casos críticos (score ≥ 85).
4. **Texto da mensagem nunca persistido** — LGPD por design.
5. **Explicabilidade em toda decisão** — sinais, pesos, evidências retornados na API.
6. **Mock LLM como padrão** — protótipo funciona sem credenciais; não depende de API externa.
7. **Consentimento explícito** em toda requisição que usa perfil do usuário.
8. **Disclaimers obrigatórios** em toda resposta do BB Decision.

---

## 7. Próximos Passos para Produção

> Estes itens são **pré-requisitos** antes de qualquer deploy fora de ambiente local.

| Prioridade | Item |
|---|---|
| 🔴 Crítico | Implementar autenticação e autorização (OAuth2 / JWT) |
| 🔴 Crítico | Revisão jurídica da base legal LGPD |
| 🔴 Crítico | Rate limiting e proteção contra abuso |
| 🟠 Alto | Avaliação com dados reais anonimizados |
| 🟠 Alto | Threat model formal (ver `docs/` para estrutura) |
| 🟠 Alto | Mapeamento LGPD completo (dados coletados, base legal, retenção) |
| 🟡 Médio | Expandir regras para falso_sequestro e falsa_central_cartao |
| 🟡 Médio | Integração com watsonx.ai e avaliação comparativa |
| 🟡 Médio | Avaliação de viés em subgrupos demográficos |
| 🟢 Baixo | Dashboard de monitoramento de qualidade em produção |

---

## 8. Glossário

| Termo | Definição |
|---|---|
| **Tier crítico** | Score ≥ 85/100 — requer revisão humana obrigatória |
| **Fluxo (a)** | Análise de mensagem isolada — gera alerta, sem pausar operação |
| **Fluxo (b)** | Mensagem correlacionada com Pix em andamento — pausa temporária + atendente |
| **Mock LLM** | Provedor determinístico que simula o LLM sem chamadas externas |
| **Motor determinístico** | Código Python puro, sem modelo de ML; mesmo input → mesmo output |
| **PII** | Personally Identifiable Information — dado pessoal identificável |
| **LGPD** | Lei Geral de Proteção de Dados (Lei nº 13.709/2018) |
| **ALTAI** | Assessment List for Trustworthy AI (EU AI HLEG) |

---

*Este relatório foi gerado como parte do MVP BB IA e deve ser revisado e atualizado a cada ciclo de desenvolvimento.*
