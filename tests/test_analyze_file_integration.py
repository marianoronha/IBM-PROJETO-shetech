"""
Testes de integração para o endpoint /api/guardiao/analyze-file.

Executa com o backend rodando em http://localhost:8001.
Cria arquivos de teste em memória — sem gravar nada em disco.

Uso:
    python tests/test_analyze_file_integration.py
"""

import io
import json
import struct
import sys
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8001"


def _post_file(img_bytes: bytes, mime: str, lang: str = "standard") -> dict:
    """Envia o arquivo via multipart/form-data e retorna o JSON da resposta."""
    boundary = "BoundaryX1234ABCD"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="upload"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + img_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="language_profile"\r\n\r\n'
        f"{lang}\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/api/guardiao/analyze-file",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=180)
    return json.loads(resp.read())


def _post_json(message: str, lang: str = "standard") -> dict:
    payload = json.dumps({"message": message, "language_profile": lang}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/guardiao/analyze",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def make_png(lines: list) -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (700, 50 + 40 * len(lines)), color="white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((10, 20 + i * 40), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg(lines: list) -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (700, 50 + 40 * len(lines)), color="white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((10, 20 + i * 40), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def make_silent_wav(duration_sec: int = 2, sample_rate: int = 16000) -> bytes:
    """Cria um arquivo WAV silencioso válido em memória."""
    n_samples = sample_rate * duration_sec
    data_size = n_samples * 2  # 16-bit mono
    buf = io.BytesIO()
    # WAV header
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))        # chunk size
    buf.write(struct.pack("<H", 1))         # PCM
    buf.write(struct.pack("<H", 1))         # mono
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * 2))  # byte rate
    buf.write(struct.pack("<H", 2))         # block align
    buf.write(struct.pack("<H", 16))        # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(b"\x00" * data_size)
    return buf.getvalue()


def run_tests():
    passed = 0
    failed = 0
    results = []

    # ── Test 1: Text analysis (baseline) ───────────────────────────────────
    print("\n[1] Analise de texto (linha base)...")
    try:
        r = _post_json(
            "Oi mae, troquei meu numero. Preciso que voce faca um Pix de R$ 800 urgente agora."
        )
        assert r["risk_score"] > 30, f"Score baixo demais: {r['risk_score']}"
        print(f"    PASS HTTP 200 | score={r['risk_score']} | label={r['risk_label']}")
        passed += 1
        results.append(("Texto fraudulento", "PASS", r["risk_score"], r["risk_label"]))
    except Exception as e:
        print(f"    FAIL {e}")
        failed += 1
        results.append(("Texto fraudulento", "FAIL", None, str(e)))

    # ── Test 2: PNG with fraudulent text ───────────────────────────────────
    print("\n[2] Imagem PNG com texto fraudulento (EasyOCR pode levar ~30s na 1a vez)...")
    try:
        img_bytes = make_png([
            "BANCO DO BRASIL URGENTE",
            "Sua conta sera bloqueada. Acesse: http://bb-fraude.net/validar",
            "Informe sua senha e CPF agora para desbloquear.",
        ])
        r = _post_file(img_bytes, "image/png")
        print(f"    PASS HTTP 200 | score={r['risk_score']} | label={r['risk_label']}")
        print(f"    Sinais detectados: {[s['label'] for s in r['signals']]}")
        passed += 1
        results.append(("PNG fraudulento", "PASS", r["risk_score"], r["risk_label"]))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    FAIL HTTP {e.code}: {body[:300]}")
        failed += 1
        results.append(("PNG fraudulento", "FAIL", None, f"HTTP {e.code}"))
    except Exception as e:
        print(f"    FAIL {e}")
        failed += 1
        results.append(("PNG fraudulento", "FAIL", None, str(e)))

    # ── Test 3: PNG with legitimate text ───────────────────────────────────
    print("\n[3] Imagem PNG com texto legitimo...")
    try:
        img_bytes = make_png([
            "Reuniao de equipe amanha as 14h na sala 3.",
            "Trazer os relatorios do mes para analise.",
        ])
        r = _post_file(img_bytes, "image/png")
        print(f"    PASS HTTP 200 | score={r['risk_score']} | label={r['risk_label']}")
        passed += 1
        results.append(("PNG legitimo", "PASS", r["risk_score"], r["risk_label"]))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    FAIL HTTP {e.code}: {body[:300]}")
        failed += 1
        results.append(("PNG legitimo", "FAIL", None, f"HTTP {e.code}"))
    except Exception as e:
        print(f"    FAIL {e}")
        failed += 1
        results.append(("PNG legitimo", "FAIL", None, str(e)))

    # ── Test 4: JPEG image ─────────────────────────────────────────────────
    print("\n[4] Imagem JPEG com texto suspeito...")
    try:
        img_bytes = make_jpeg([
            "Faca um Pix de R$ 500 urgente agora para mim.",
            "Acesse o link: http://acesso-bb.fraude.net/verificar",
        ])
        r = _post_file(img_bytes, "image/jpeg")
        print(f"    PASS HTTP 200 | score={r['risk_score']} | label={r['risk_label']}")
        print(f"    Sinais detectados: {[s['label'] for s in r['signals']]}")
        passed += 1
        results.append(("JPEG suspeito", "PASS", r["risk_score"], r["risk_label"]))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    FAIL HTTP {e.code}: {body[:300]}")
        failed += 1
        results.append(("JPEG suspeito", "FAIL", None, f"HTTP {e.code}"))
    except Exception as e:
        print(f"    FAIL {e}")
        failed += 1
        results.append(("JPEG suspeito", "FAIL", None, str(e)))

    # ── Test 5: Silent WAV audio ───────────────────────────────────────────
    print("\n[5] Audio WAV silencioso (Whisper - pode levar ~20s na 1a vez)...")
    try:
        wav_bytes = make_silent_wav(duration_sec=2)
        r = _post_file(wav_bytes, "audio/wav")
        # Audio silencioso deve retornar score baixo (sem fala detectada)
        print(f"    PASS HTTP 200 | score={r['risk_score']} | label={r['risk_label']}")
        passed += 1
        results.append(("WAV silencioso", "PASS", r["risk_score"], r["risk_label"]))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    FAIL HTTP {e.code}: {body[:300]}")
        failed += 1
        results.append(("WAV silencioso", "FAIL", None, f"HTTP {e.code}"))
    except Exception as e:
        print(f"    FAIL {e}")
        failed += 1
        results.append(("WAV silencioso", "FAIL", None, str(e)))

    # ── Test 6: Invalid file type ───────────────────────────────────────────
    print("\n[6] Arquivo com tipo invalido (text/plain)...")
    try:
        _post_file(b"hello world", "text/plain")
        print("    FAIL - deveria ter retornado HTTP 400")
        failed += 1
        results.append(("Tipo invalido", "FAIL", None, "Nao retornou 400"))
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print(f"    PASS HTTP 400 (esperado)")
            passed += 1
            results.append(("Tipo invalido", "PASS", None, "HTTP 400"))
        else:
            body = e.read().decode(errors="replace")
            print(f"    FAIL HTTP {e.code} (esperava 400): {body[:200]}")
            failed += 1
            results.append(("Tipo invalido", "FAIL", None, f"HTTP {e.code}"))
    except Exception as e:
        print(f"    FAIL {e}")
        failed += 1
        results.append(("Tipo invalido", "FAIL", None, str(e)))

    # ── Test 7: Text analysis with low profile ──────────────────────────────
    print("\n[7] Analise de link suspeito (perfil linguagem simples)...")
    try:
        r = _post_json(
            "Acesse seu cadastro em http://bb-verificacao.site/dados e atualize sua senha agora.",
            lang="low",
        )
        assert r["risk_score"] > 0, f"Score zero inesperado"
        print(f"    PASS HTTP 200 | score={r['risk_score']} | label={r['risk_label']} | profile={r['language_profile']}")
        passed += 1
        results.append(("Link suspeito (low)", "PASS", r["risk_score"], r["risk_label"]))
    except Exception as e:
        print(f"    FAIL {e}")
        failed += 1
        results.append(("Link suspeito (low)", "FAIL", None, str(e)))

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"RESULTADOS: {passed} passaram / {failed} falharam")
    print(f"{'='*60}")
    for name, status, score, detail in results:
        mark = "PASS" if status == "PASS" else "FAIL"
        score_str = f" score={score}" if score is not None else ""
        print(f"  [{mark}] {name}{score_str} -- {detail}")

    return failed == 0


if __name__ == "__main__":
    print("Testando endpoint /api/guardiao/analyze-file...")
    print(f"Backend: {BASE_URL}")
    ok = run_tests()
    sys.exit(0 if ok else 1)
