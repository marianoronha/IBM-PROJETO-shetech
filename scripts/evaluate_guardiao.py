#!/usr/bin/env python3
"""
Script de avaliação do Guardião.

Calcula: precisão, recall, F1, falsos positivos, falsos negativos e
matriz de confusão para os seguintes modos:
  - rules_only   : apenas as regras determinísticas (sem LLM)
  - hybrid_mock  : regras + MockLLMProvider (⚠️ não representa LLM real)
  - hybrid_real  : regras + provider real (watsonx/openai) quando disponível

⚠️  IMPORTANTE: Resultados com Mock LLM são marcados explicitamente como
    "obtidos com Mock LLM — não representam modelo real de linguagem."

Uso:
  python scripts/evaluate_guardiao.py [--split dev|test|all] [--verbose]

Flags:
  --split   Qual split avaliar: dev, test ou all (padrão: test)
  --verbose Exibe cada predição
"""

import argparse
import json
import sys
import os

# Garante que o backend está no PATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.guardiao.risk_scorer import analyze_level1
from app.guardiao.risk_rules import evaluate_risk_rules, HIGH_RISK_SCORE_THRESHOLD
from app.guardiao.prompt_guard import sanitize_user_input, InputValidationError

DATASET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "backend", "app", "data", "labeled_messages.json"
)

RISK_THRESHOLD = HIGH_RISK_SCORE_THRESHOLD  # 60.0 — intervenção = "scam"


# ---------------------------------------------------------------------------
# Predição por regras (sem LLM)
# ---------------------------------------------------------------------------

def predict_rules_only(text: str) -> tuple[str, float]:
    """
    Faz a predição usando apenas as regras determinísticas do Guardião.
    Retorna (label, score) onde label é 'scam' | 'legitimate'.
    """
    try:
        sanitized = sanitize_user_input(text)
    except InputValidationError:
        return "legitimate", 0.0  # input inválido → conservador

    l1 = analyze_level1(sanitized)
    score = l1.risk_score

    # Avalia regras de intervenção
    state = {
        "final_risk_score": score,
        "level1_result": {
            "signals": [
                {
                    "signal_id": s.signal_id,
                    "label": s.label,
                    "description": s.description,
                    "weight": s.weight,
                    "evidence": s.evidence,
                }
                for s in l1.signals
            ],
            "risk_score": score,
            "risk_label": l1.risk_label,
        },
    }
    requires_intervention, _ = evaluate_risk_rules(state)
    label = "scam" if requires_intervention else "legitimate"
    return label, score


# ---------------------------------------------------------------------------
# Predição híbrida com LLM (usa o provider configurado)
# ---------------------------------------------------------------------------

def predict_hybrid(text: str, llm_provider) -> tuple[str, float, bool]:
    """
    Predição híbrida: regras + LLM.
    O LLM analisa o contexto de casos limítrofes (score 30–70).
    Retorna (label, score, used_llm).

    ⚠️  Se llm_provider.is_mock, o resultado NÃO representa LLM real.
    """
    rules_label, score = predict_rules_only(text)

    # LLM só é consultado em zona de incerteza (score 30–70)
    used_llm = False
    if 30.0 <= score <= 70.0 and llm_provider is not None:
        used_llm = True
        try:
            system_prompt = (
                "Você é um detector de golpes de engenharia social. "
                "Analise a mensagem e responda APENAS com 'scam' ou 'legítimo'."
            )
            response = llm_provider.complete(system_prompt, f"Mensagem: {text[:500]}")
            llm_raw = response.text.strip().lower()
            if "scam" in llm_raw or "golpe" in llm_raw:
                return "scam", score, used_llm
            elif "legít" in llm_raw or "legitim" in llm_raw:
                return "legitimate", score, used_llm
        except Exception:
            pass  # fallback para regras em caso de erro do LLM

    return rules_label, score, used_llm


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def compute_metrics(predictions: list[dict]) -> dict:
    """
    Calcula TP, FP, TN, FN, precisão, recall, F1 e acurácia.
    Positivo = 'scam'.
    """
    tp = fp = tn = fn = 0
    for p in predictions:
        actual = p["actual"]
        pred = p["predicted"]
        if actual == "scam" and pred == "scam":
            tp += 1
        elif actual == "legitimate" and pred == "scam":
            fp += 1
        elif actual == "legitimate" and pred == "legitimate":
            tn += 1
        elif actual == "scam" and pred == "legitimate":
            fn += 1

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    accuracy = (tp + tn) / total if total > 0 else 0.0

    return {
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def print_confusion_matrix(metrics: dict, label: str) -> None:
    tp, fp, tn, fn = metrics["tp"], metrics["fp"], metrics["tn"], metrics["fn"]
    print(f"\n  Matriz de confusao ({label}):")
    print( "                   Predito SCAM  Predito LEGITIMO")
    print(f"  Real SCAM         TP={tp:4d}        FN={fn:4d}")
    print(f"  Real LEGITIMO     FP={fp:4d}        TN={tn:4d}")


def print_metrics(metrics: dict, label: str, is_mock: bool = False) -> None:
    sep = "-" * 60
    mock_warn = "  [!] RESULTADO COM MOCK LLM - NAO REPRESENTA MODELO REAL\n" if is_mock else ""
    print(f"\n{sep}")
    print(f"  Modo: {label}")
    if mock_warn:
        print(mock_warn, end="")
    print(f"  Total avaliado : {metrics['total']}")
    print(f"  Precisao       : {metrics['precision']:.1%}")
    print(f"  Recall         : {metrics['recall']:.1%}")
    print(f"  F1-score       : {metrics['f1']:.1%}")
    print(f"  Acuracia       : {metrics['accuracy']:.1%}")
    print(f"  TP={metrics['tp']}  FP={metrics['fp']}  TN={metrics['tn']}  FN={metrics['fn']}")
    print_confusion_matrix(metrics, label)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Avaliação do Guardião")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="test",
                        help="Split do dataset a usar (padrão: test)")
    parser.add_argument("--verbose", action="store_true",
                        help="Exibe cada predição individualmente")
    args = parser.parse_args()

    # Carrega dataset
    with open(DATASET_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    messages = raw["messages"]

    if args.split != "all":
        messages = [m for m in messages if m["split"] == args.split]

    if not messages:
        print(f"Nenhuma mensagem encontrada para split={args.split}.")
        sys.exit(1)

    scam_count = sum(1 for m in messages if m["label"] == "scam")
    legit_count = sum(1 for m in messages if m["label"] == "legitimate")
    sep = "=" * 60
    print(f"\n{sep}")
    print("  Avaliacao do Guardiao")
    print(f"  Dataset: {len(messages)} mensagens (split={args.split})")
    print(f"  Golpe: {scam_count} | Legitima: {legit_count}")
    print(sep)

    # ----------------------------------------------------------------
    # Modo 1: Apenas regras
    # ----------------------------------------------------------------
    preds_rules = []
    for msg in messages:
        predicted, score = predict_rules_only(msg["text"])
        preds_rules.append({
            "id": msg["id"],
            "actual": msg["label"],
            "predicted": predicted,
            "score": score,
            "category": msg["category"],
            "difficulty": msg["difficulty"],
        })
        if args.verbose:
            marker = "OK" if predicted == msg["label"] else "ERRO"
            print(f"  [{marker}] {msg['id']:8s} real={msg['label']:10s} pred={predicted:10s} score={score:.0f}%  {msg['text'][:60]}")

    metrics_rules = compute_metrics(preds_rules)
    print_metrics(metrics_rules, "Apenas Regras (deterministico)", is_mock=False)

    # ----------------------------------------------------------------
    # Modo 2: Híbrido com Mock LLM
    # ----------------------------------------------------------------
    try:
        from app.llm.provider import MockLLMProvider
        mock_provider = MockLLMProvider()

        preds_hybrid_mock = []
        for msg in messages:
            predicted, score, used_llm = predict_hybrid(msg["text"], mock_provider)
            preds_hybrid_mock.append({
                "id": msg["id"],
                "actual": msg["label"],
                "predicted": predicted,
                "score": score,
                "used_llm": used_llm,
            })

        metrics_hybrid_mock = compute_metrics(preds_hybrid_mock)
        print_metrics(
            metrics_hybrid_mock,
            "Hibrido com Mock LLM [!]",
            is_mock=True,
        )
        llm_used_count = sum(1 for p in preds_hybrid_mock if p["used_llm"])
        print(f"  LLM consultado em {llm_used_count} casos de zona limitrofe (score 30-70%)")
    except ImportError:
        print("\n  Mock LLM nao disponivel.")

    # ----------------------------------------------------------------
    # Modo 3: Híbrido com provider real (se configurado)
    # ----------------------------------------------------------------
    try:
        from app.llm.provider import get_llm_provider, MockLLMProvider
        real_provider = get_llm_provider()
        if isinstance(real_provider, MockLLMProvider):
            print("\n  Provider real nao configurado - pulando avaliacao com LLM real.")
        else:
            preds_hybrid_real = []
            for msg in messages:
                predicted, score, _ = predict_hybrid(msg["text"], real_provider)
                preds_hybrid_real.append({
                    "id": msg["id"],
                    "actual": msg["label"],
                    "predicted": predicted,
                    "score": score,
                })
            metrics_hybrid_real = compute_metrics(preds_hybrid_real)
            print_metrics(
                metrics_hybrid_real,
                f"Hibrido com LLM Real ({real_provider.__class__.__name__})",
                is_mock=False,
            )
    except Exception as e:
        print(f"\n  Provider real nao disponivel: {e}")

    # ----------------------------------------------------------------
    # Analise por dificuldade (regras)
    # ----------------------------------------------------------------
    print(f"\n{'-'*60}")
    print("  Desempenho por dificuldade (Apenas Regras):")
    for diff in ("easy", "medium", "hard"):
        subset = [p for p in preds_rules if any(
            m["id"] == p["id"] and m["difficulty"] == diff for m in messages
        )]
        if subset:
            m = compute_metrics(subset)
            print(f"  {diff:6s}: F1={m['f1']:.1%}  P={m['precision']:.1%}  R={m['recall']:.1%}  ({len(subset)} msgs)")

    # ----------------------------------------------------------------
    # Falsos positivos/negativos notáveis (regras)
    # ----------------------------------------------------------------
    fps = [p for p in preds_rules if p["actual"] == "legitimate" and p["predicted"] == "scam"]
    fns = [p for p in preds_rules if p["actual"] == "scam" and p["predicted"] == "legitimate"]
    if fps:
        print(f"\n  Falsos positivos (legitima classificada como golpe): {len(fps)}")
        for p in fps[:5]:
            msg_text = next((m["text"][:70] for m in messages if m["id"] == p["id"]), "")
            print(f"    {p['id']} score={p['score']:.0f}%: {msg_text}")
    if fns:
        print(f"\n  Falsos negativos (golpe nao detectado): {len(fns)}")
        for p in fns[:5]:
            msg_text = next((m["text"][:70] for m in messages if m["id"] == p["id"]), "")
            cat = next((m["category"] for m in messages if m["id"] == p["id"]), "")
            print(f"    {p['id']} [{cat}] score={p['score']:.0f}%: {msg_text}")

    sep2 = "=" * 60
    print(f"\n{sep2}")
    print("  LIMITACOES DESTA AVALIACAO:")
    print("  - Dataset de 201 msgs sinteticas (nao coletadas de golpes reais).")
    print("  - Regras ajustadas com o split dev - metricas no split test sao mais realistas.")
    print("  - Resultados com Mock LLM nao representam performance de modelo real.")
    print("  - Sem avaliacao de vies ou cobertura regional.")
    print(f"{sep2}\n")


if __name__ == "__main__":
    main()
