"""
Testes unitários do módulo de perfis de linguagem.

Cobre RF-G-18 e RN-07: adaptação de linguagem por perfil.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.guardiao.profiles import (
    LanguageProfile,
    get_profile_instruction,
    get_profile_label,
)


class TestProfiles:
    def test_perfil_standard_retorna_instrucao(self):
        instrucao = get_profile_instruction("standard")
        assert "técnica" in instrucao.lower() or "técnico" in instrucao.lower()

    def test_perfil_low_retorna_instrucao_simples(self):
        instrucao = get_profile_instruction("low")
        assert "simples" in instrucao.lower()

    def test_perfil_invalido_usa_standard(self):
        instrucao = get_profile_instruction("inexistente")
        instrucao_standard = get_profile_instruction("standard")
        assert instrucao == instrucao_standard

    def test_label_low(self):
        assert get_profile_label("low") == "Linguagem simples"

    def test_label_standard(self):
        assert get_profile_label("standard") == "Padrão"

    def test_maiuscula_aceita(self):
        instrucao = get_profile_instruction("LOW")
        instrucao_low = get_profile_instruction("low")
        assert instrucao == instrucao_low
