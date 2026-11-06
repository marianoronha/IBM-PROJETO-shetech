"""
Testes básicos dos endpoints do Guardião.

Verifica:
  - Importação do módulo.
  - Inicialização da aplicação FastAPI.
  - GET /health
  - POST /api/guardiao/analyze (texto)
  - POST /api/guardiao/health

Execução:
    cd backend
    python -m pytest tests/test_guardiao_endpoints.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestApplicationStartup:
    """Verifica que a aplicação FastAPI inicializa sem erros."""

    def test_app_is_created(self):
        assert app is not None
        assert app.title.startswith("BB IA MVP")

    def test_health_root(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestGuardiaoHealth:
    """Verifica o endpoint de health do Guardião."""

    def test_guardiao_health(self):
        response = client.get("/api/guardiao/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "guardiao"


class TestGuardiaoAnalyze:
    """Testa o endpoint POST /api/guardiao/analyze com entradas válidas e inválidas."""

    def test_analyze_low_risk_message(self):
        """Uma mensagem comum não deve gerar alto risco."""
        payload = {
            "message": "Olá, como você está?",
            "user_id": "",
            "input_channel": "text",
            "language_profile": "standard",
            "monitoring_consent": True,
        }
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Campos obrigatórios na resposta
        assert "risk_score" in data
        assert "risk_label" in data
        assert "signals" in data
        assert "requires_intervention" in data
        assert "requires_human_review" in data
        assert "intervention_message" in data
        assert "followup_message" in data
        assert "input_channel" in data
        assert "language_profile" in data

        # Tipos corretos
        assert isinstance(data["risk_score"], float)
        assert isinstance(data["signals"], list)
        assert isinstance(data["requires_intervention"], bool)
        assert data["input_channel"] == "text"
        assert data["language_profile"] == "standard"

    def test_analyze_suspicious_message(self):
        """Uma mensagem suspeita de golpe deve retornar score elevado."""
        payload = {
            "message": (
                "Oi mãe, troquei o número. Preciso que você faça um Pix de R$ 2.000 "
                "urgente agora. É para uma emergência, não conta para ninguém."
            ),
            "user_id": "",
            "input_channel": "whatsapp_text",
            "language_profile": "low",
            "monitoring_consent": True,
        }
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert data["language_profile"] == "low"
        assert data["input_channel"] == "whatsapp_text"

    def test_analyze_empty_message_rejected(self):
        """Mensagem vazia deve retornar HTTP 422."""
        payload = {"message": ""}
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code == 422

    def test_analyze_whitespace_only_message_rejected(self):
        """Mensagem só com espaços deve retornar HTTP 400 ou 422."""
        payload = {"message": "   "}
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code in (400, 422)

    def test_analyze_message_too_long_rejected(self):
        """Mensagem acima de 2000 caracteres deve retornar HTTP 422."""
        payload = {"message": "a" * 2001}
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code == 422

    def test_analyze_invalid_channel_rejected(self):
        """Canal inválido deve retornar HTTP 422."""
        payload = {
            "message": "Olá",
            "input_channel": "canal_invalido",
        }
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code == 422

    def test_analyze_invalid_language_profile_rejected(self):
        """Perfil de linguagem inválido deve retornar HTTP 422."""
        payload = {
            "message": "Olá",
            "language_profile": "high",
        }
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code == 422

    def test_analyze_response_has_correct_channel_passthrough(self):
        """O canal enviado deve aparecer na resposta."""
        payload = {
            "message": "Teste de canal SMS",
            "input_channel": "sms_text",
            "language_profile": "standard",
        }
        response = client.post("/api/guardiao/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["input_channel"] == "sms_text"


class TestBBDecisionHealth:
    """Verifica o endpoint de health do BB Decision."""

    def test_bbdecision_health(self):
        response = client.get("/api/bbdecision/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "bbdecision"
