"""
Serviço multimodal do Guardião — processamento LOCAL (sem APIs externas).

Responsabilidades:
  - extract_text_from_image: usa EasyOCR + Pillow para extrair texto de imagens.
    Não requer API externa, chave de API ou variáveis de ambiente.
  - transcribe_audio: usa openai-whisper (rodando localmente via PyTorch CPU)
    para transcrever áudios em texto.
    Não requer API externa, chave de API ou variáveis de ambiente.

Ambas as funções retornam uma string de texto que é então analisada pelo
pipeline existente do Guardião (run_guardiao), sem modificar nenhuma parte
do mecanismo de detecção de golpes.

Dependências (todas locais, sem chave de API):
  - Pillow          (validação e pré-processamento de imagens)
  - easyocr         (OCR baseado em redes neurais — modelos baixados na 1ª execução)
  - openai-whisper  (transcrição de áudio — modelo tiny/base baixado na 1ª execução)
  - torch           (exigido pelo whisper e pelo easyocr; CPU é suficiente)
  - imageio-ffmpeg  (bundla ffmpeg estático para o Whisper — sem instalação manual)

SEGURANÇA:
  - Os bytes do arquivo são descartados imediatamente após o processamento.
  - Nunca são registrados em log (nem nome, nem conteúdo).
  - Nenhuma credencial ou chave de API é utilizada ou exigida.
  - O processamento é inteiramente local — nenhum dado sai da máquina.

PRIVACIDADE:
  - Nenhum console.log nem structlog com conteúdo do arquivo.
  - Apenas metadados de erro (tipo de falha, sem conteúdo) são registrados.

LIMITAÇÕES CONHECIDAS:
  - OCR: EasyOCR funciona bem com texto impresso e screenshots; pode ter dificuldade
    com letra cursiva, fontes muito pequenas ou imagens de baixíssima qualidade.
    O OCR extrai texto — não faz interpretação visual de logotipos ou layout.
  - Áudio: Whisper tiny funciona bem para pt-BR em falas claras; pode ter
    dificuldade com ruído intenso, sotaques muito marcados ou qualidade muito baixa.
    Para melhor precisão use modelo "base" (altere "tiny" para "base" abaixo).
  - Modelos baixados automaticamente na primeira execução:
      EasyOCR: ~10-40 MB (detecção + reconhecimento)
      Whisper tiny: ~74 MB
    Requerem conexão com a internet apenas na 1ª execução.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# Tamanho máximo do arquivo aceito pelo serviço (10 MB)
MAX_FILE_BYTES = 10 * 1024 * 1024

# Tipos MIME aceitos
ACCEPTED_IMAGE_TYPES: set[str] = {"image/jpeg", "image/png", "image/webp"}
ACCEPTED_AUDIO_TYPES: set[str] = {
    "audio/mpeg",        # .mp3
    "audio/wav",         # .wav
    "audio/x-wav",       # .wav alternativo
    "audio/mp4",         # .m4a
    "audio/m4a",
    "audio/ogg",         # .ogg
    "audio/vnd.dlna.adts",
}


class MultimodalError(Exception):
    """Erro de processamento multimodal — mensagem é exibida ao usuário."""
    pass


# ---------------------------------------------------------------------------
# Instâncias singleton (carregadas uma vez, reutilizadas entre requisições)
# ---------------------------------------------------------------------------

_easyocr_reader = None   # easyocr.Reader
_whisper_model = None    # whisper model


def _get_ocr_reader():
    """Retorna (ou inicializa) o leitor EasyOCR para português + inglês."""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            # gpu=False: usa CPU — funciona em qualquer ambiente sem GPU
            # verbose=False: não polui o log com mensagens de progresso
            _easyocr_reader = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
            logger.info("EasyOCR inicializado (CPU, línguas: pt, en)")
        except ImportError:
            raise MultimodalError(
                "A biblioteca 'easyocr' não está instalada. "
                "Execute: pip install easyocr"
            )
        except Exception as exc:
            logger.error("Falha ao inicializar EasyOCR: %s", type(exc).__name__)
            raise MultimodalError(
                "Não foi possível inicializar o motor de OCR. "
                "Verifique se 'easyocr' e 'torch' estão instalados corretamente."
            ) from None
    return _easyocr_reader


def _get_whisper_model():
    """Retorna (ou inicializa) o modelo Whisper tiny para transcrição local."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            # "tiny" (~74 MB): bom equilíbrio entre velocidade e qualidade em CPU.
            # Troque por "base" (~142 MB) para melhor precisão em falas difíceis.
            _whisper_model = whisper.load_model("tiny")
            logger.info("Whisper tiny carregado (CPU)")
        except ImportError:
            raise MultimodalError(
                "A biblioteca 'openai-whisper' não está instalada. "
                "Execute: pip install openai-whisper"
            )
        except Exception as exc:
            logger.error("Falha ao carregar modelo Whisper: %s", type(exc).__name__)
            raise MultimodalError(
                "Não foi possível carregar o modelo de transcrição de áudio. "
                "Verifique se 'openai-whisper' e 'torch' estão instalados corretamente."
            ) from None

        # Configura o ffmpeg com caminho absoluto via monkey-patch,
        # garantindo funcionamento independente do PATH do servidor.
        ffmpeg_exe = _get_ffmpeg_exe()
        if ffmpeg_exe:
            _patch_whisper_ffmpeg(ffmpeg_exe)
        else:
            logger.warning(
                "ffmpeg não encontrado. A transcrição de áudio pode falhar. "
                "Execute: pip install imageio-ffmpeg"
            )
    return _whisper_model


def _get_ffmpeg_exe() -> str | None:
    """
    Retorna o caminho absoluto para o executável ffmpeg.

    Estratégia (em ordem de prioridade):
    1. imageio-ffmpeg: bundla um ffmpeg estático — preferível, sem instalação manual.
    2. PATH do sistema: usa ffmpeg instalado pelo usuário.
    3. None se não encontrado.
    """
    import subprocess

    # Tenta imageio-ffmpeg (bundled) primeiro
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            logger.info("ffmpeg localizado via imageio-ffmpeg: %s", os.path.basename(exe))
            return exe
    except ImportError:
        pass
    except Exception:
        pass

    # Verifica ffmpeg no PATH do sistema
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            import shutil
            return shutil.which("ffmpeg")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _patch_whisper_ffmpeg(ffmpeg_exe: str) -> None:
    """
    Faz monkey-patch em whisper.audio.load_audio para usar o caminho absoluto
    do ffmpeg em vez de depender do PATH do processo do servidor.

    Isso é necessário porque o servidor uvicorn pode ser iniciado sem ter
    o diretório do ffmpeg no PATH.
    """
    try:
        import whisper.audio as _wa
        import numpy as np
        from subprocess import CalledProcessError
        from subprocess import run as _run

        _ffmpeg = ffmpeg_exe  # captura no closure

        def _patched_load_audio(file: str, sr: int = _wa.SAMPLE_RATE) -> np.ndarray:
            cmd = [
                _ffmpeg,
                "-nostdin", "-threads", "0",
                "-i", file,
                "-f", "s16le", "-ac", "1",
                "-acodec", "pcm_s16le",
                "-ar", str(sr), "-",
            ]
            try:
                out = _run(cmd, capture_output=True, check=True).stdout
            except CalledProcessError as e:
                raise RuntimeError(
                    f"Failed to load audio: {e.stderr.decode(errors='replace')}"
                ) from e
            return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0

        _wa.load_audio = _patched_load_audio
        logger.info(
            "whisper.audio.load_audio configurado com ffmpeg: %s",
            os.path.basename(ffmpeg_exe),
        )
    except Exception as exc:
        logger.warning(
            "Falha ao configurar whisper com ffmpeg local: %s",
            type(exc).__name__,
        )


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def extract_text_from_image(
    file_bytes: bytes,
    mime_type: str,
) -> str:
    """
    Extrai texto de uma imagem usando EasyOCR (processamento 100% local).

    O texto extraído é retornado como string, pronto para ser analisado
    pelo pipeline do Guardião (run_guardiao).

    Args:
        file_bytes: bytes brutos da imagem (já validados pelo endpoint).
        mime_type: tipo MIME da imagem (ex.: "image/jpeg").

    Returns:
        Texto extraído da imagem com contexto sobre o resultado do OCR.

    Raises:
        MultimodalError: se o processamento falhar.
    """
    if mime_type not in ACCEPTED_IMAGE_TYPES:
        raise MultimodalError(
            f"Formato de imagem não suportado: {mime_type}. "
            "Use JPG, PNG ou WEBP."
        )
    if len(file_bytes) > MAX_FILE_BYTES:
        raise MultimodalError("A imagem excede o tamanho máximo de 10 MB.")

    try:
        from PIL import Image
        import numpy as np

        # Carrega via Pillow para validação e conversão para RGB
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img = img.convert("RGB")  # normaliza (remove alpha, etc.)
        except Exception:
            raise MultimodalError(
                "Não foi possível abrir a imagem. "
                "Verifique se o arquivo não está corrompido."
            )

        # Converte para numpy array (formato esperado pelo EasyOCR)
        img_array = np.array(img)

        # Executa OCR
        reader = _get_ocr_reader()
        detections = reader.readtext(img_array)

        if not detections:
            return (
                "[Imagem recebida — OCR não detectou texto legível]\n"
                "A imagem foi processada mas não contém texto identificável. "
                "Pode ser uma imagem fotográfica sem texto, ou o texto pode estar "
                "muito pequeno ou pouco contrastado para o OCR detectar.\n"
                "Nota: o OCR extrai texto visível; não interpreta logotipos ou layout visual."
            )

        # Ordena detecções por posição vertical (cima para baixo)
        detections_sorted = sorted(detections, key=lambda d: d[0][0][1])

        lines = []
        for bbox, text, confidence in detections_sorted:
            if confidence >= 0.2 and text.strip():
                lines.append(text.strip())

        if not lines:
            return (
                "[Imagem recebida — texto detectado com confiança insuficiente]\n"
                "O OCR detectou regiões de texto mas com qualidade muito baixa. "
                "A imagem pode estar borrada, com pouco contraste ou fonte muito pequena."
            )

        extracted = "\n".join(lines)
        return (
            f"[Texto extraído da imagem via OCR local]\n"
            f"{extracted}"
        )

    except MultimodalError:
        raise
    except Exception as exc:
        logger.error("Falha ao processar imagem via OCR: %s", type(exc).__name__)
        raise MultimodalError(
            "Não foi possível processar a imagem. "
            "Verifique se o arquivo é uma imagem válida e tente novamente."
        ) from None
    finally:
        # Descarta bytes imediatamente — privacidade
        del file_bytes


def transcribe_audio(
    file_bytes: bytes,
    mime_type: str,
    filename: str,
) -> str:
    """
    Transcreve áudio em texto usando Whisper local (openai-whisper + PyTorch CPU).

    O processamento é 100% local — nenhum dado é enviado para serviços externos.
    O texto transcrito é retornado pronto para ser analisado pelo pipeline do Guardião.

    Args:
        file_bytes: bytes brutos do arquivo de áudio.
        mime_type: tipo MIME do áudio.
        filename: nome do arquivo original (apenas extensão usada — nunca logado).

    Returns:
        Transcrição do áudio em texto.

    Raises:
        MultimodalError: se o processamento falhar.
    """
    if mime_type not in ACCEPTED_AUDIO_TYPES:
        raise MultimodalError(
            f"Formato de áudio não suportado: {mime_type}. "
            "Use MP3, WAV, M4A ou OGG."
        )
    if len(file_bytes) > MAX_FILE_BYTES:
        raise MultimodalError("O arquivo de áudio excede o tamanho máximo de 10 MB.")

    # Mapa de extensões seguras (nunca usamos o nome original do arquivo)
    ext_map = {
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".mp4",
        "audio/m4a": ".m4a",
        "audio/ogg": ".ogg",
        "audio/vnd.dlna.adts": ".aac",
    }
    safe_ext = ext_map.get(mime_type, ".mp3")

    # Whisper exige um arquivo em disco (não aceita BytesIO diretamente).
    # Criamos um arquivo temporário que é removido no bloco finally.
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=safe_ext,
            delete=False,
            prefix="guardiao_audio_",
        ) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        model = _get_whisper_model()

        result = model.transcribe(
            tmp_path,
            language="pt",   # força português — melhora precisão para pt-BR
            fp16=False,       # CPU não suporta FP16
            verbose=False,
        )

        transcription = (result.get("text") or "").strip()

        if not transcription:
            return (
                "Áudio recebido, mas não foi possível detectar fala compreensível. "
                "O arquivo pode estar vazio, silencioso ou com qualidade insuficiente "
                "para o modelo Whisper tiny transcrever corretamente."
            )

        return f"[Transcrição do áudio via Whisper local]\n{transcription}"

    except MultimodalError:
        raise
    except Exception as exc:
        logger.error(
            "Falha ao transcrever áudio via Whisper local: %s",
            type(exc).__name__,
        )
        raise MultimodalError(
            "Não foi possível transcrever o áudio. "
            "Verifique se o arquivo é válido e tente novamente."
        ) from None
    finally:
        # Remove arquivo temporário — privacidade garantida
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        del file_bytes
