
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
  - Pillow
  - easyocr
  - openai-whisper
  - torch
  - imageio-ffmpeg

SEGURANÇA:
  - Os bytes do arquivo não são registrados em logs.
  - Nenhuma credencial ou chave de API é utilizada ou exigida.
  - O processamento é inteiramente local.

PRIVACIDADE:
  - Nenhum log contém o conteúdo do arquivo.
  - Apenas metadados de erro são registrados.

LIMITAÇÕES CONHECIDAS:
  - OCR: EasyOCR pode ter dificuldade com letras cursivas,
    fontes pequenas ou imagens de baixa qualidade.
  - O OCR extrai texto, mas não interpreta logotipos ou layout visual.
  - Áudio: Whisper tiny pode apresentar dificuldade com ruídos,
    sotaques ou gravações de baixa qualidade.
  - Modelos podem precisar ser baixados na primeira execução.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile

from typing import cast

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

MAX_FILE_BYTES = 10 * 1024 * 1024

ACCEPTED_IMAGE_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ACCEPTED_AUDIO_TYPES: set[str] = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/m4a",
    "audio/ogg",
    "audio/vnd.dlna.adts",
}


class MultimodalError(Exception):
    """Erro de processamento multimodal exibido ao usuário."""


# ---------------------------------------------------------------------------
# Instâncias singleton
# ---------------------------------------------------------------------------

_easyocr_reader = None
_whisper_model = None


def _get_ocr_reader():
    """
    Retorna ou inicializa o EasyOCR para português e inglês.

    O modelo é carregado apenas quando necessário e reutilizado
    nas próximas análises.
    """
    global _easyocr_reader

    if _easyocr_reader is None:
        try:
            import easyocr

            _easyocr_reader = easyocr.Reader(
                ["pt", "en"],
                gpu=False,
                verbose=False,
            )

            logger.info(
                "EasyOCR inicializado (CPU, línguas: pt, en)"
            )

        except ImportError:
            raise MultimodalError(
                "A biblioteca 'easyocr' não está instalada. "
                "Execute: pip install easyocr"
            ) from None

        except Exception as exc:
            logger.error(
                "Falha ao inicializar EasyOCR: %s",
                type(exc).__name__,
            )

            raise MultimodalError(
                "Não foi possível inicializar o motor de OCR. "
                "Verifique se 'easyocr' e 'torch' estão instalados corretamente."
            ) from None

    return _easyocr_reader


def _get_whisper_model():
    """
    Retorna ou inicializa o modelo Whisper tiny.

    O processamento é local, via CPU.
    """
    global _whisper_model

    if _whisper_model is None:
        try:
            import whisper

            _whisper_model = whisper.load_model("tiny")

            logger.info(
                "Whisper tiny carregado (CPU)"
            )

        except ImportError:
            raise MultimodalError(
                "A biblioteca 'openai-whisper' não está instalada. "
                "Execute: pip install openai-whisper"
            ) from None

        except Exception as exc:
            logger.error(
                "Falha ao carregar modelo Whisper: %s",
                type(exc).__name__,
            )

            raise MultimodalError(
                "Não foi possível carregar o modelo de transcrição de áudio. "
                "Verifique se 'openai-whisper' e 'torch' estão instalados corretamente."
            ) from None

        ffmpeg_exe = _get_ffmpeg_exe()

        if ffmpeg_exe:
            _patch_whisper_ffmpeg(ffmpeg_exe)
        else:
            logger.warning(
                "ffmpeg não encontrado. "
                "A transcrição de áudio pode falhar. "
                "Execute: pip install imageio-ffmpeg"
            )

    return _whisper_model


# ---------------------------------------------------------------------------
# FFmpeg
# ---------------------------------------------------------------------------

def _get_ffmpeg_exe() -> str | None:
    """
    Retorna o caminho absoluto do executável FFmpeg.

    Prioridades:
    1. imageio-ffmpeg
    2. FFmpeg no PATH do sistema
    3. None
    """
    import shutil
    import subprocess

    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()

        if exe and os.path.isfile(exe):
            logger.info(
                "ffmpeg localizado via imageio-ffmpeg: %s",
                os.path.basename(exe),
            )
            return exe

    except ImportError:
        pass

    except Exception:
        pass

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )

        if result.returncode == 0:
            return shutil.which("ffmpeg")

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _patch_whisper_ffmpeg(ffmpeg_exe: str) -> None:
    """
    Configura whisper.audio.load_audio para utilizar o caminho
    absoluto do FFmpeg.
    """
    try:
        import whisper.audio as _wa
        import numpy as np

        from subprocess import CalledProcessError
        from subprocess import run as _run

        _ffmpeg = ffmpeg_exe

        def _patched_load_audio(
            file: str,
            sr: int = _wa.SAMPLE_RATE,
        ) -> np.ndarray:

            cmd = [
                _ffmpeg,
                "-nostdin",
                "-threads",
                "0",
                "-i",
                file,
                "-f",
                "s16le",
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(sr),
                "-",
            ]

            try:
                out = _run(
                    cmd,
                    capture_output=True,
                    check=True,
                ).stdout

            except CalledProcessError as exc:
                raise RuntimeError(
                    "Failed to load audio: "
                    f"{exc.stderr.decode(errors='replace')}"
                ) from exc

            return (
                np.frombuffer(out, np.int16)
                .flatten()
                .astype(np.float32)
                / 32768.0
            )

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
# Extração de texto de imagens
# ---------------------------------------------------------------------------

def extract_text_from_image(
    file_bytes: bytes,
    mime_type: str,
) -> str:
    """
    Extrai texto de imagens usando EasyOCR local.

    Args:
        file_bytes: bytes da imagem.
        mime_type: tipo MIME do arquivo.

    Returns:
        Texto extraído da imagem.

    Raises:
        MultimodalError: quando não é possível processar a imagem.
    """

    if mime_type not in ACCEPTED_IMAGE_TYPES:
        raise MultimodalError(
            f"Formato de imagem não suportado: {mime_type}. "
            "Use JPG, PNG ou WEBP."
        )

    if len(file_bytes) > MAX_FILE_BYTES:
        raise MultimodalError(
            "A imagem excede o tamanho máximo de 10 MB."
        )

    try:
        from PIL import Image
        import numpy as np

        # Abre e normaliza a imagem
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img = img.convert("RGB")

        except Exception:
            raise MultimodalError(
                "Não foi possível abrir a imagem. "
                "Verifique se o arquivo não está corrompido."
            ) from None

        # Converte para o formato esperado pelo EasyOCR
        img_array = np.array(img)

        reader = _get_ocr_reader()

        # Correção de tipagem:
        # bbox = coordenadas
        # text = texto extraído
        # confidence = valor numérico de confiança
        detections = cast(
            list[tuple[list[list[int]], str, float]],
            reader.readtext(img_array),
        )

        if not detections:
            return (
                "[Imagem recebida — OCR não detectou texto legível]\n"
                "A imagem foi processada mas não contém texto identificável. "
                "Pode ser uma imagem fotográfica sem texto, ou o texto pode "
                "estar muito pequeno ou pouco contrastado.\n"
                "Nota: o OCR extrai texto visível; não interpreta logotipos "
                "ou layout visual."
            )

        # Ordena de cima para baixo
        detections_sorted = sorted(
            detections,
            key=lambda d: d[0][0][1],
        )

        lines: list[str] = []

        for bbox, text, confidence in detections_sorted:
            if confidence >= 0.2 and text.strip():
                lines.append(text.strip())

        if not lines:
            return (
                "[Imagem recebida — texto detectado com confiança insuficiente]\n"
                "O OCR detectou regiões de texto, mas com qualidade muito baixa. "
                "A imagem pode estar borrada, com pouco contraste "
                "ou fonte muito pequena."
            )

        extracted = "\n".join(lines)

        return (
            "[Texto extraído da imagem via OCR local]\n"
            f"{extracted}"
        )

    except MultimodalError:
        raise

    except Exception as exc:
        logger.error(
            "Falha ao processar imagem via OCR: %s",
            type(exc).__name__,
        )

        raise MultimodalError(
            "Não foi possível processar a imagem. "
            "Verifique se o arquivo é uma imagem válida e tente novamente."
        ) from None

    finally:
        del file_bytes


# ---------------------------------------------------------------------------
# Transcrição de áudio
# ---------------------------------------------------------------------------

def transcribe_audio(
    file_bytes: bytes,
    mime_type: str,
    filename: str,
) -> str:
    """
    Transcreve áudio usando Whisper local via PyTorch CPU.

    Args:
        file_bytes: bytes do áudio.
        mime_type: tipo MIME do arquivo.
        filename: nome original, mantido por compatibilidade.

    Returns:
        Transcrição do áudio.

    Raises:
        MultimodalError: se a transcrição falhar.
    """

    if mime_type not in ACCEPTED_AUDIO_TYPES:
        raise MultimodalError(
            f"Formato de áudio não suportado: {mime_type}. "
            "Use MP3, WAV, M4A ou OGG."
        )

    if len(file_bytes) > MAX_FILE_BYTES:
        raise MultimodalError(
            "O arquivo de áudio excede o tamanho máximo de 10 MB."
        )

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

    tmp_path: str | None = None

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
            language="pt",
            fp16=False,
            verbose=False,
        )

        # Correção de tipagem:
        # Verifica que o resultado é uma string antes de usar strip().
        raw_transcription = result.get("text")

        transcription = (
            raw_transcription.strip()
            if isinstance(raw_transcription, str)
            else ""
        )

        if not transcription:
            return (
                "Áudio recebido, mas não foi possível detectar fala compreensível. "
                "O arquivo pode estar vazio, silencioso ou com qualidade "
                "insuficiente para o modelo Whisper tiny transcrever."
            )

        return (
            "[Transcrição do áudio via Whisper local]\n"
            f"{transcription}"
        )

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
        # Remove o arquivo temporário
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        del file_bytes
