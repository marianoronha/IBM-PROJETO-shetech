"""
Testes de integração — 10 casos para /api/guardiao/analyze-file e /api/guardiao/analyze.

Requer:
  - Backend rodando em http://localhost:8001
  - pyttsx3 instalado (pip install pyttsx3) para síntese de fala real

Uso:
    python tests/test_analyze_file_integration.py

Todos os arquivos de teste são criados em memória ou em temp e descartados.
Nenhum arquivo permanente é gravado no disco.
"""

import io
import json
import os
import struct
import sys
import tempfile
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8001"

# ─── helpers ────────────────────────────────────────────────────────────────

def _post_file(file_bytes: bytes, mime: str, lang: str = "standard",
               context_text: str = "") -> dict:
    boundary = "BoundaryX1234ABCD"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="upload"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + file_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="language_profile"\r\n\r\n'
        f"{lang}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="context_text"\r\n\r\n'
        f"{context_text}\r\n"
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


def make_png(lines: list, width: int = 720, line_height: int = 44) -> bytes:
    from PIL import Image, ImageDraw
    h = 30 + line_height * len(lines)
    img = Image.new("RGB", (width, h), color="white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((12, 15 + i * line_height), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg(lines: list) -> bytes:
    from PIL import Image, ImageDraw
    h = 30 + 44 * len(lines)
    img = Image.new("RGB", (720, h), color=(248, 248, 248))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((12, 15 + i * 44), line, fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def make_silent_wav(duration_sec: int = 1, sample_rate: int = 16000) -> bytes:
    n = sample_rate * duration_sec
    data_size = n * 2
    buf = io.BytesIO()
    buf.write(b"RIFF"); buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE"); buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16)); buf.write(struct.pack("<H", 1))
    buf.write(struct.pack("<H", 1)); buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * 2))
    buf.write(struct.pack("<H", 2)); buf.write(struct.pack("<H", 16))
    buf.write(b"data"); buf.write(struct.pack("<I", data_size))
    buf.write(b"\x00" * data_size)
    return buf.getvalue()


def make_speech_wav(text: str) -> bytes | None:
    """Sintetiza fala real usando pyttsx3 (Windows TTS). Retorna None se indisponível."""
    try:
        import pyttsx3
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="guard_tts_")
        tmp_path = tmp.name
        tmp.close()
        engine = pyttsx3.init()
        # Tenta definir voz em português (PT-BR) se disponível
        voices = engine.getProperty("voices")
        for v in voices:
            if "brazil" in v.name.lower() or "pt" in (v.languages[0] if v.languages else "").lower():
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", 150)
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            wav_bytes = f.read()
        return wav_bytes
    except Exception:
        return None
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ─── test runner ────────────────────────────────────────────────────────────

def run_tests():
    results = []
    passed = failed = 0

    def ok(name, score, label, extra=""):
        nonlocal passed
        passed += 1
        results.append(("PASS", name, score, label, extra))
        print(f"  [PASS] {name}  score={score}  label={label}  {extra}")

    def fail(name, reason):
        nonlocal failed
        failed += 1
        results.append(("FAIL", name, None, None, reason))
        print(f"  [FAIL] {name}  reason={reason}")

    # Wait for backend
    import time
    for _ in range(8):
        try:
            urllib.request.urlopen(f"{BASE_URL}/health", timeout=3)
            break
        except Exception:
            time.sleep(1)

    # ── 1. Mensagem de texto suspeita ───────────────────────────────────────
    print("\n[1] Mensagem de texto suspeita (golpe do número novo)...")
    try:
        r = _post_json("Oi mae, troquei meu numero. Precisa fazer um Pix de R$ 800 agora, urgente.")
        assert r["risk_score"] > 30, f"score={r['risk_score']} baixo demais"
        ok("Texto suspeito", r["risk_score"], r["risk_label"],
           f"sinais={[s['label'] for s in r['signals']]}")
    except Exception as e:
        fail("Texto suspeito", str(e)[:120])

    # ── 2. Link suspeito ────────────────────────────────────────────────────
    print("\n[2] Link suspeito...")
    try:
        r = _post_json("Acesse http://bb-seguranca-conta.net/validar e confirme seus dados agora.")
        assert r["risk_score"] > 0
        ok("Link suspeito", r["risk_score"], r["risk_label"],
           f"sinais={[s['label'] for s in r['signals']]}")
    except Exception as e:
        fail("Link suspeito", str(e)[:120])

    # ── 3. PNG com mensagem fraudulenta ─────────────────────────────────────
    print("\n[3] Imagem PNG com texto fraudulento (EasyOCR — pode levar ~30 s na 1ª vez)...")
    try:
        img = make_png([
            "BANCO DO BRASIL - URGENTE",
            "Sua conta sera bloqueada. Acesse: http://bb-fraude.net/validar",
            "Informe sua senha e CPF agora para desbloquear.",
        ])
        r = _post_file(img, "image/png")
        ok("PNG fraudulento", r["risk_score"], r["risk_label"],
           f"sinais={[s['label'] for s in r['signals']]}")
    except urllib.error.HTTPError as e:
        fail("PNG fraudulento", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        fail("PNG fraudulento", str(e)[:120])

    # ── 4. PNG legítimo ─────────────────────────────────────────────────────
    print("\n[4] Imagem PNG com conteúdo legítimo...")
    try:
        img = make_png([
            "Reuniao de equipe amanha as 14h na sala 3.",
            "Trazer os relatorios do mes para analise.",
        ])
        r = _post_file(img, "image/png")
        ok("PNG legítimo", r["risk_score"], r["risk_label"])
    except urllib.error.HTTPError as e:
        fail("PNG legítimo", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        fail("PNG legítimo", str(e)[:120])

    # ── 5. JPEG com texto suspeito ──────────────────────────────────────────
    print("\n[5] Imagem JPEG com texto suspeito...")
    try:
        img = make_jpeg([
            "Faca um Pix de R$ 500 urgente agora para mim.",
            "Acesse: http://acesso-bb.fraude.net/verificar",
        ])
        r = _post_file(img, "image/jpeg")
        ok("JPEG suspeito", r["risk_score"], r["risk_label"],
           f"sinais={[s['label'] for s in r['signals']]}")
    except urllib.error.HTTPError as e:
        fail("JPEG suspeito", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        fail("JPEG suspeito", str(e)[:120])

    # ── 6. WAV com fala real em português ───────────────────────────────────
    print("\n[6] Áudio WAV com fala real (pyttsx3 → Whisper local)...")
    wav = make_speech_wav(
        "Faca um pix de quinhentos reais urgente para mim agora. "
        "Este é meu novo número. Informe sua senha de acesso."
    )
    if wav:
        try:
            r = _post_file(wav, "audio/wav")
            ok("WAV fala real", r["risk_score"], r["risk_label"],
               f"sinais={[s['label'] for s in r['signals']]}")
        except urllib.error.HTTPError as e:
            fail("WAV fala real", f"HTTP {e.code}: {e.read().decode()[:200]}")
        except Exception as e:
            fail("WAV fala real", str(e)[:120])
    else:
        fail("WAV fala real", "pyttsx3 indisponível — síntese de fala não pôde ser gerada")

    # ── 7. WAV com conteúdo suspeito (contexto explícito) ───────────────────
    print("\n[7] Áudio WAV suspeito com contexto de texto adicional...")
    wav2 = make_speech_wav("Ola, sou do suporte do banco. Preciso que voce informe o CPF e senha agora.")
    if wav2:
        try:
            r = _post_file(wav2, "audio/wav", context_text="Ligação recebida de número desconhecido")
            ok("WAV suspeito + contexto", r["risk_score"], r["risk_label"],
               f"sinais={[s['label'] for s in r['signals']]}")
        except urllib.error.HTTPError as e:
            fail("WAV suspeito + contexto", f"HTTP {e.code}: {e.read().decode()[:200]}")
        except Exception as e:
            fail("WAV suspeito + contexto", str(e)[:120])
    else:
        fail("WAV suspeito + contexto", "pyttsx3 indisponível")

    # ── 8. WAV silencioso ───────────────────────────────────────────────────
    print("\n[8] Áudio WAV silencioso...")
    try:
        r = _post_file(make_silent_wav(2), "audio/wav")
        # Score deve ser baixo (sem fala = sem sinais de golpe)
        ok("WAV silencioso", r["risk_score"], r["risk_label"])
    except urllib.error.HTTPError as e:
        fail("WAV silencioso", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        fail("WAV silencioso", str(e)[:120])

    # ── 9. Arquivo inválido ─────────────────────────────────────────────────
    print("\n[9] Arquivo com tipo inválido (text/plain)...")
    try:
        _post_file(b"this is not an image or audio", "text/plain")
        fail("Tipo inválido", "Deveria ter retornado HTTP 400 mas retornou 200")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            ok("Tipo inválido", None, "HTTP 400", "(esperado)")
        else:
            fail("Tipo inválido", f"HTTP {e.code} inesperado")
    except Exception as e:
        fail("Tipo inválido", str(e)[:120])

    # ── 10. Anexo sem texto adicional (só o arquivo) ────────────────────────
    print("\n[10] Apenas anexo, sem texto adicional...")
    try:
        img = make_png([
            "Parabens! Voce ganhou R$ 10.000. Taxa de liberacao via Pix.",
            "Clique aqui para receber: http://premio-bb.net/liberar",
        ])
        r = _post_file(img, "image/png", context_text="")
        ok("Só anexo (sem texto)", r["risk_score"], r["risk_label"],
           f"sinais={[s['label'] for s in r['signals']]}")
    except urllib.error.HTTPError as e:
        fail("Só anexo (sem texto)", f"HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        fail("Só anexo (sem texto)", str(e)[:120])

    # ── Resumo ───────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"RESULTADO FINAL: {passed} passaram / {failed} falharam de {passed+failed}")
    print(f"{'='*65}")
    for status, name, score, label, extra in results:
        score_str = f" score={score}" if score is not None else ""
        label_str = f" label={label}" if label else ""
        print(f"  [{status}] {name}{score_str}{label_str}  {extra}")

    return failed == 0


if __name__ == "__main__":
    print(f"Testes de integracao — endpoint /api/guardiao/analyze-file")
    print(f"Backend: {BASE_URL}\n")
    ok = run_tests()
    sys.exit(0 if ok else 1)
