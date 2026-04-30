import os
import time
import logging
from functools import lru_cache
from typing import Optional

import ffmpeg

from app.config import settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    pass


class AudioConversionError(TranscriptionError):
    pass


class UnsupportedFormatError(TranscriptionError):
    pass


class TranscriptionService:
    _model = None
    _loaded = False
    _lock = None

    def __init__(self):
        pass

    @classmethod
    def load_model(cls):
        if cls._loaded:
            return
        if cls._lock is None:
            import threading
            cls._lock = threading.Lock()
        with cls._lock:
            if cls._loaded:
                return
            model_name = settings.WHISPER_MODEL
            model_path = os.path.join(settings.WHISPER_MODEL_DIR, model_name)
            logger.info(f"Loading whisper model: {model_name} ({settings.WHISPER_COMPUTE_TYPE})")
            from faster_whisper import WhisperModel
            from faster_whisper.utils import download_model as _original_download

            def _patched_download(size_or_id, output_dir=None, local_files_only=False, cache_dir=None):
                if os.path.isdir(size_or_id) and os.path.exists(os.path.join(size_or_id, "model.bin")):
                    return size_or_id
                return _original_download(size_or_id, output_dir, local_files_only, cache_dir)

            import faster_whisper.transcribe
            faster_whisper.transcribe.download_model = _patched_download

            cls._model = WhisperModel(
                model_path,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
                cpu_threads=4,
                num_workers=1,
                local_files_only=True,
            )
            cls._loaded = True
            logger.info("Whisper model loaded successfully")

    @classmethod
    def preload(cls):
        """Call at worker startup to preload model into memory."""
        cls.load_model()

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        TranscriptionService.load_model()
        start_time = time.time()

        wav_path = audio_path
        if not audio_path.endswith(".wav"):
            wav_path = self._convert_audio(audio_path)

        try:
            segments, info = TranscriptionService._model.transcribe(
                wav_path,
                language=language,
                beam_size=5,
                word_timestamps=True,
            )

            result_segments = []
            full_text = []
            for seg in segments:
                seg_dict = {
                    "id": seg.id,
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                    "words": [
                        {
                            "word": w.word,
                            "start": w.start,
                            "end": w.end,
                            "probability": w.probability,
                        }
                        for w in (seg.words or [])
                    ],
                }
                result_segments.append(seg_dict)
                full_text.append(seg.text.strip())

            processing_time = time.time() - start_time

            return {
                "text": " ".join(full_text),
                "language": info.language,
                "duration": info.duration,
                "segments": result_segments,
                "processing_time": round(processing_time, 2),
            }
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise TranscriptionError(f"Transcription failed: {e}")
        finally:
            if wav_path != audio_path and os.path.exists(wav_path):
                os.remove(wav_path)

    def transcribe_from_minio(self, object_name: str, language: Optional[str] = None) -> dict:
        from app.services.minio_service import get_minio_service
        minio_service = get_minio_service()

        tmp_dir = settings.UPLOAD_DIR
        os.makedirs(tmp_dir, exist_ok=True)
        local_path = os.path.join(tmp_dir, os.path.basename(object_name))

        try:
            minio_service.download_file(object_name, local_path)
            return self.transcribe(local_path, language)
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    def get_supported_languages(self) -> list[str]:
        return [
            "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo",
            "br", "bs", "ca", "cs", "cy", "da", "de", "el", "en", "es",
            "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw",
            "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja",
            "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo",
            "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
            "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt",
            "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq",
            "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl",
            "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh",
        ]

    def _convert_audio(self, input_path: str) -> str:
        output_path = input_path.rsplit(".", 1)[0] + "_converted.wav"
        try:
            (
                ffmpeg
                .input(input_path)
                .output(output_path, acodec="pcm_s16le", ac=1, ar="16000")
                .overwrite_output()
                .run(quiet=True)
            )
            logger.info(f"Converted {input_path} -> {output_path}")
            return output_path
        except ffmpeg.Error as e:
            logger.error(f"Audio conversion failed: {e}")
            raise AudioConversionError(f"Failed to convert {input_path}: {e}")


@lru_cache()
def get_transcription_service() -> TranscriptionService:
    return TranscriptionService()
