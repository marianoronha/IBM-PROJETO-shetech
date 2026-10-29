# Matriz de Rastreabilidade — BB IA MVP

> Atualizada ao final de cada bloco de implementação.
> Status: ✅ Atendido | 🔶 Parcial | ❌ Não atendido | ⏳ Planejado

## Guardião

| ID | Requisito (resumo) | Componente | Teste | Status |
|---|---|---|---|---|
| RF-G-01 | Etapa 1: Intake — receber input | `nodes/intake.py` | `test_prompt_guard.py` | ✅ |
| RF-G-02 | Etapa 2: Análise — sinais de engenharia social | `risk_scorer.py`, `nodes/level1_analysis.py` | `test_guardiao_level1.py` | ✅ |
| RF-G-03 | Etapa 3: Tentativa de transação | `nodes/context_cross.py` | `test_guardiao_agent.py::test_com_transacao_pendente_boost_score` | ✅ |
| RF-G-04 | Etapa 4: Cruzamento de contexto | `nodes/context_cross.py` | `test_guardiao_agent.py::test_sem_transacao_pendente_fluxo_completo` | ✅ |
| RF-G-05 | Etapa 5: Intervenção | `nodes/intervention.py` | `test_guardiao_agent.py::TestDoisPerfisLinguagem` | ✅ |
| RF-G-06 | Etapa 6: Acompanhamento | `nodes/followup.py` | `test_guardiao_agent.py::test_todos_nos_preenchidos` | ✅ |
| RF-G-07 | Nível 1: sinais na mensagem | `risk_scorer.py` | `test_guardiao_level1.py` | ✅ |
| RF-G-08 | Nível 2: análise personalizada por perfil (4 critérios) | `level2_analyzer.py`, `nodes/level2_analysis.py` | `test_guardiao_level2.py::TestNivelDoisCriterios` | ✅ |
| RF-G-09 | Suporte multimodal (simulado via texto) | `nodes/intake.py` (channel field) | — | 🔶 Canal registrado, processamento simulado |
| RF-G-10 | Caso obrigatório: golpe do número novo (≥75%) | `risk_scorer.py` | `test_guardiao_level1.py::test_golpe_numero_novo_score_alto` | ✅ |
| RF-G-11 | Caso obrigatório: falso suporte técnico (78%) | `risk_scorer.py` | `test_guardiao_level1.py::test_falso_suporte_tecnico_score_alto` | ✅ |
| RF-G-12 | Entrada simples na tela | `api/guardiao.py`, `pages/Guardiao.tsx` | `components.test.tsx` | ✅ |
| RF-G-13 | Pontuação de risco em % + classificação | `risk_scorer.py` | `test_guardiao_level1.py` | ✅ |
| RF-G-14 | Explicação do tipo de golpe | `nodes/intervention.py` | `test_guardiao_agent.py::test_perfil_standard_mensagem_tecnica` | ✅ |
| RF-G-15 | Como é aplicado o golpe | `nodes/intervention.py` (`how_applied`) | `test_guardiao_agent.py` | ✅ |
| RF-G-16 | Sinais de alerta e orientação | `nodes/intervention.py` (`alert_signals`) | `test_guardiao_agent.py` | ✅ |
| RF-G-17 | Próximo passo pelos canais oficiais | `nodes/intervention.py` (`next_step`) | `test_guardiao_agent.py::test_intervencao_tem_proximo_passo` | ✅ |
| RF-G-18 | Explicação por perfil (padrão / linguagem simples) | `profiles.py`, `nodes/intervention.py` | `test_profiles.py`, `test_guardiao_agent.py::TestDoisPerfisLinguagem` | ✅ |
| RF-G-19 | Comportamento agêntico (LangGraph, 6 nós) | `agent.py` | `test_guardiao_agent.py::test_todos_nos_preenchidos` | ✅ |
| RF-G-20 | Aprende padrão do usuário | `level2_analyzer.py` | `test_guardiao_level2.py::TestDiferencaNivel1Nivel2` | ✅ |

## BB Decision

| ID | Requisito (resumo) | Componente | Teste | Status |
|---|---|---|---|---|
| RF-D-01 | Entrada em linguagem natural | `intent_parser.py` | `test_narrator.py::TestIntentParser` | ✅ |
| RF-D-02 | IA interpreta intenção → cenário estruturado (schema validado) | `intent_parser.py`, `scenarios.py` | `test_narrator.py::TestIntentParser` | ✅ |
| RF-D-03 | Cenário: parcelar em 12x | `calculator.py::scenario_installment` | `test_calculator.py::TestScenarioInstallment` | ✅ |
| RF-D-04 | Cenário: perder renda por 3 meses | `calculator.py::scenario_income_loss` | `test_calculator.py::TestScenarioIncomeLoss` | ✅ |
| RF-D-05 | Cenário: mudar de emprego | `calculator.py::scenario_job_change` | `test_calculator.py::TestScenarioJobChange` | ✅ |
| RF-D-06 | Cenário: comprar uma casa | `calculator.py::scenario_home_purchase` | `test_calculator.py::TestScenarioHomePurchase` | ✅ |
| RF-D-07 | Comparar atual vs. alternativo | `calculator.py`, `api/bbdecision.py` | `test_api.py::test_comparacao_atual_vs_alternativo` | ✅ |
| RF-D-08 | Valores APENAS do motor determinístico (Decimal, zero LLM) | `calculator.py` | `test_calculator.py`, `test_narrator.py::TestNumerosNaoInventados` | ✅ |
| RF-D-09 | Explicação clara e simples | `narrator.py` | `test_narrator.py::TestComparacaoAtualVsAlternativo` | ✅ |
| RF-D-10 | Aviso obrigatório em TODA resposta + SEMPRE visível na UI | `narrator.py::DISCLAIMER`, `api/bbdecision.py`, `components/DisclaimerBanner.tsx` | `test_narrator.py::TestDisclaimerObrigatorio`, `test_api.py`, `components.test.tsx::DisclaimerBanner` | ✅ |
| RF-D-11 | Cenários sob medida (parametrizáveis) | `calculator.py` (parâmetros opcionais) | `test_calculator.py::test_parametros_personalizados` | ✅ |

## Não-Funcionais

| ID | Requisito (resumo) | Componente | Teste | Status |
|---|---|---|---|---|
| RNF-01 | Ciclo agêntico fluido | `agent.py` (LangGraph) | `test_guardiao_agent.py::test_todos_nos_preenchidos` | ✅ |
| RNF-02 | Multimodalidade (simulada) | `nodes/intake.py` | — | 🔶 Canal registrado, processamento simulado |
| RNF-03 | Pontuação com sinais e justificativa | `risk_scorer.py` | `test_guardiao_level1.py` | ✅ |
| RNF-04 | Log de auditoria estruturado | `audit/logger.py` | `test_audit_logger.py` | ✅ |
| RNF-05 | Anti-prompt-injection + validação entrada | `guardiao/prompt_guard.py` | `test_prompt_guard.py`, `test_guardiao_agent.py::TestPromptInjectionNoFluxo` | ✅ |
| RNF-06 | Código limpo + testes + OpenAPI | `api/guardiao.py`, `api/bbdecision.py` (FastAPI auto-OpenAPI) | `test_api.py` | ✅ |
| RNF-07 | Casos de teste FP/FN com métricas | `tests/test_cases_golpes.py` | — | ⏳ Bloco 5 |
| RNF-08 | Somente dados sintéticos | `data/*.json` | — | ✅ |
| RNF-09 | Sem credenciais no código | `.env.example`, `config.py`, `llm/provider.py` | — | ✅ |
| RNF-10 | Indicadores Guardião (métricas) | — | — | ⏳ Bloco 5 |
| RNF-11 | Indicadores BB Decision (métricas) | — | — | ⏳ Bloco 5 |

## Regras de Negócio

| ID | Requisito (resumo) | Componente | Teste | Status |
|---|---|---|---|---|
| RN-01 | Alto risco: regras claras, versionadas, testáveis | `risk_rules.py`, `nodes/decision.py` | `test_risk_rules.py` | ✅ |
| RN-02 | Cliente controla monitoramento | `nodes/intervention.py` (`user_control_note`) | `test_guardiao_agent.py::test_intervencao_tem_controle_do_cliente` | ✅ |
| RN-03 | Toda resposta com motivo transparente | `nodes/intervention.py` (`main_message`) | `test_guardiao_agent.py::test_perfil_standard_mensagem_tecnica` | ✅ |
| RN-04 | Equilíbrio FP/FN | `risk_scorer.py`, `risk_rules.py` | `test_guardiao_level1.py::TestMensagensLegitimas`, `test_risk_rules.py::test_sem_sinais_sem_intervencao` | ✅ |
| RN-05 | Valores apenas do motor determinístico | `calculator.py` (Decimal, ROUND_HALF_UP) | `test_calculator.py`, `test_narrator.py::TestNumerosNaoInventados` | ✅ |
| RN-06 | Aviso de estimativa no BB Decision | `api/bbdecision.py::MANDATORY_DISCLAIMER` | `test_api.py::test_disclaimer_obrigatorio_presente` | ✅ |
| RN-07 | Linguagem adaptada ao perfil | `profiles.py` | `test_profiles.py` | ✅ |

## Conformidade

| ID | Requisito (resumo) | Componente | Teste | Status |
|---|---|---|---|---|
| RC-01 | LGPD — base legal documentada | `docs/responsible_ai_report.md` | — | ⏳ Bloco 5 |
| RC-02 | LGPD — consentimento | `api/guardiao.py::monitoring_consent`, `api/bbdecision.py::simulation_consent` | — | 🔶 Flag implementado, fluxo de consentimento completo no Bloco 5 |
| RC-03 | LGPD — minimização de dados | `state.py`, `audit/logger.py` | `test_audit_logger.py::test_nao_tem_raw_input` | ✅ |
| RC-04 | Revisão humana em alto risco | `risk_rules.py::requires_human_review`, `nodes/decision.py` | `test_risk_rules.py::TestHumanReview` | ✅ |
| RC-05 | Normas Banco Central (Pix) | Documentação + aviso | — | ⏳ Bloco 5 |
| RC-06 | Governança e monitoramento de modelos | `audit/logger.py`, `docs/responsible_ai_report.md` | — | ⏳ Bloco 2/5 |
