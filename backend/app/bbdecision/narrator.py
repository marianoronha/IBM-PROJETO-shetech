"""
Narrator do BB Decision.

RF-D-09: o LLM recebe APENAS os números calculados pelo motor e os narra
em linguagem simples. PROIBIDO inventar ou alterar valores.

ARQUITETURA DE SEGURANÇA:
- O narrator recebe um dict com os resultados do calculator.
- O system prompt instrui explicitamente a NÃO inventar números.
- Modo fallback (sem LLM): gera narrativa determinística a partir dos dados.
- O teste test_narrator_nao_inventa_numeros verifica que todo número
  exibido na narração existe no resultado do motor.

RF-D-10: toda narração inclui o aviso obrigatório de estimativa.
"""

from __future__ import annotations

import re
from typing import Optional

from app.bbdecision.calculator import ScenarioResult

# Não incluir disclaimer no narrator — o campo 'disclaimer' da resposta
# da API já o exibe uma única vez (consolidação P0-2g).
DISCLAIMER = ""

_NARRATOR_SYSTEM_PROMPT = """Você é um assistente financeiro educacional do Banco do Brasil.
Sua tarefa é narrar em linguagem clara e simples os resultados de uma simulação financeira.

REGRAS ABSOLUTAS:
1. Use SOMENTE os números presentes no JSON de resultados fornecido. NUNCA invente valores.
2. NUNCA faça recomendações de investimento.
3. Sempre inclua os avisos e alertas do campo "warnings" na narrativa.
4. Compare claramente o caminho atual com o caminho alternativo.
5. Use linguagem acessível, sem jargão financeiro excessivo.
6. Responda em português do Brasil.
7. Seja conciso: máximo 300 palavras.
"""


def _extract_numbers_from_text(text: str) -> set[float]:
    """
    Extrai números significativos de um texto em formato brasileiro ou inglês.

    Estratégia: identifica tokens numéricos completos na ordem de prioridade:
    1. Formato BR com vírgula decimal: 1.200,50 ou 732.933,60
    2. Formato EN com ponto decimal: 1200.50 ou 732933.60
    3. Inteiros puros (somente quando não são parte de um número já capturado)

    Evita capturar sub-strings de números maiores (ex: '74' de '1869.26').
    """
    result = set()
    # Conjunto de posições já consumidas para não re-capturar sub-strings
    consumed: set[tuple[int, int]] = set()

    # Prioridade 1: BR decimal (1.200,50)
    for m in re.finditer(r"\d{1,3}(?:\.\d{3})*,\d{2}", text):
        consumed.add((m.start(), m.end()))
        try:
            result.add(float(m.group().replace(".", "").replace(",", ".")))
        except ValueError:
            pass

    # Prioridade 2: EN decimal (1200.50 ou 1200.26)
    for m in re.finditer(r"\d+\.\d+", text):
        overlap = any(s <= m.start() < e or s < m.end() <= e for s, e in consumed)
        if not overlap:
            consumed.add((m.start(), m.end()))
            try:
                result.add(round(float(m.group()), 2))
            except ValueError:
                pass

    # Prioridade 3: inteiros puros (apenas se não sobrepostos)
    for m in re.finditer(r"\b\d+\b", text):
        overlap = any(s <= m.start() < e or s < m.end() <= e for s, e in consumed)
        if not overlap:
            consumed.add((m.start(), m.end()))
            try:
                result.add(float(m.group()))
            except ValueError:
                pass

    return result


def _extract_numbers_from_result(result: ScenarioResult) -> set[float]:
    """Extrai todos os valores numéricos do ScenarioResult."""
    nums: set[float] = set()

    def collect(obj) -> None:
        if isinstance(obj, dict):
            for val in obj.values():
                collect(val)
        elif isinstance(obj, float):
            nums.add(round(obj, 2))
        elif isinstance(obj, int) and not isinstance(obj, bool):
            nums.add(float(obj))
        elif isinstance(obj, list):
            for item in obj:
                collect(item)

    collect(result.current_path)
    collect(result.alternative_path)
    collect(result.delta)
    return nums


def _narrative_fallback(result: ScenarioResult) -> str:
    """
    Gera narrativa determinística sem LLM.
    Garante que nenhum número inventado aparece no texto.
    Usado em testes e quando não há provedor LLM configurado.
    """
    alt = result.alternative_path
    cur = result.current_path
    delta = result.delta

    if result.scenario_type == "parcelamento":
        pmt = alt.get("parcela_mensal", 0)
        total = alt.get("total_pago", 0)
        juros = alt.get("juros_totais", 0)
        novo_saldo = alt.get("novo_saldo_disponivel", 0)
        saldo_atual = cur.get("saldo_disponivel", 0)
        taxa = alt.get("taxa_mensal_pct", 0)
        n = alt.get("num_parcelas", 0)
        text = (
            f"Se você parcelar em {n}x, sua parcela mensal será de R$ {pmt:.2f} "
            f"(taxa de {taxa:.2f}% a.m.).\n"
            f"Você pagará R$ {total:.2f} no total — R$ {juros:.2f} em juros.\n"
            f"Seu saldo mensal disponível passará de R$ {saldo_atual:.2f} "
            f"para R$ {novo_saldo:.2f}."
        )

    elif result.scenario_type == "perda_renda":
        deficit = alt.get("deficit_mensal", 0)
        meses = alt.get("meses_perda", 0)
        reserva_restante = alt.get("reserva_restante", 0)
        meses_cobre = cur.get("meses_reserva_cobre", 0)
        insuf = alt.get("reserva_insuficiente", False)
        text = (
            f"Com {meses} meses sem renda, seu deficit mensal será de R$ {deficit:.2f}.\n"
            f"Sua reserva atual cobre aproximadamente {meses_cobre} mês(es) de despesas.\n"
            + (
                f"Após o período, restarão R$ {reserva_restante:.2f} de reserva."
                if not insuf else
                "⚠️ Sua reserva não cobre todo o período de perda de renda."
            )
        )

    elif result.scenario_type == "mudanca_emprego":
        nova_renda = alt.get("nova_renda_mensal", 0)
        novo_saldo = alt.get("novo_saldo_disponivel", 0)
        saldo_atual = cur.get("saldo_disponivel", 0)
        var_renda = delta.get("variacao_renda_mensal", 0)
        meses_trans = alt.get("meses_reserva_suporta_transicao", 0)
        text = (
            f"Com a nova renda de R$ {nova_renda:.2f}, "
            f"{'você ganhará' if var_renda >= 0 else 'você perderá'} "
            f"R$ {abs(var_renda):.2f} por mês em relação ao emprego atual.\n"
            f"Seu saldo disponível passará de R$ {saldo_atual:.2f} "
            f"para R$ {novo_saldo:.2f}.\n"
            f"Sua reserva suporta até {meses_trans} mês(es) de transição."
        )

    elif result.scenario_type == "compra_casa":
        prestacao = alt.get("prestacao_mensal", 0)
        financ = alt.get("financiamento", 0)
        prazo = alt.get("prazo_meses", 360)
        custo_total = alt.get("custo_total_imovel", 0)
        novo_comp = alt.get("novo_comprometimento_renda_pct", 0)
        novo_saldo = alt.get("novo_saldo_disponivel", 0)
        text = (
            f"Financiando R$ {financ:.2f} em {prazo} meses, "
            f"sua prestação será de R$ {prestacao:.2f}/mês.\n"
            f"O custo total do imóvel será R$ {custo_total:.2f}.\n"
            f"Seu comprometimento de renda passará para {novo_comp:.1f}% "
            f"e seu saldo disponível será R$ {novo_saldo:.2f}."
        )

    else:
        text = "Simulação concluída. Verifique os dados abaixo."

    if result.warnings:
        text += "\n\n" + "\n".join(f"⚠️ {w}" for w in result.warnings)

    return text


def narrate(
    result: ScenarioResult,
    llm_provider=None,
    language_profile: str = "standard",
) -> str:
    """
    Narra o resultado da simulação em linguagem natural.

    O LLM recebe APENAS os dados calculados — nunca a pergunta original
    nem os parâmetros brutos do usuário.

    Args:
        result: resultado do motor financeiro determinístico.
        llm_provider: provedor LLM (None = fallback determinístico).
        language_profile: "standard" ou "low".

    Returns:
        Texto narrativo + disclaimer obrigatório.
    """
    if llm_provider is None:
        narrative = _narrative_fallback(result)
    else:
        narrative = _narrate_with_llm(result, llm_provider, language_profile)

    return narrative


def _narrate_with_llm(
    result: ScenarioResult,
    llm_provider,
    language_profile: str,
) -> str:
    """Usa o LLM para narrar os resultados calculados."""
    import json as _json

    tone = (
        "Use linguagem muito simples, evite termos técnicos, "
        "prefira frases curtas e diretas."
        if language_profile == "low"
        else "Use linguagem clara e objetiva."
    )

    # O LLM recebe APENAS os resultados calculados — NUNCA a pergunta original
    payload = {
        "cenario": result.scenario_type,
        "caminho_atual": result.current_path,
        "caminho_alternativo": result.alternative_path,
        "diferencas": result.delta,
        "alertas": result.warnings,
        "premissas": result.assumptions,
    }

    user_msg = (
        f"Instruções de tom: {tone}\n\n"
        f"Resultados da simulação (use SOMENTE estes números):\n"
        f"{_json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    try:
        response = llm_provider.complete(
            system_prompt=_NARRATOR_SYSTEM_PROMPT,
            user_message=user_msg,
        )
        return response.text.strip()
    except Exception:
        # Fallback determinístico em caso de falha do LLM
        return _narrative_fallback(result)
