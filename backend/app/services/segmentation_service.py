import logging
import re
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


class SegmentationService:
    def __init__(self):
        pass

    def segment_by_silence(self, transcription_result: dict, silence_threshold: float = 0.5) -> dict:
        segments = []
        current_words = []
        current_start = None

        all_words = []
        for seg in transcription_result.get("segments", []):
            for word in seg.get("words", []):
                all_words.append(word)

        if not all_words:
            return self._empty_result("silence_based", transcription_result)

        for i, word in enumerate(all_words):
            if current_start is None:
                current_start = word["start"]
                current_words = [word]
            else:
                prev_word = all_words[i - 1] if i > 0 else None
                if prev_word and (word["start"] - prev_word["end"]) >= silence_threshold:
                    segments.append(self._build_segment(segments, current_words))
                    current_words = [word]
                    current_start = word["start"]
                else:
                    current_words.append(word)

        if current_words:
            segments.append(self._build_segment(segments, current_words))

        return {
            "segments": segments,
            "total_segments": len(segments),
            "metadata": {
                "method": "silence_based",
                "silence_threshold": silence_threshold,
                "total_duration": transcription_result.get("duration", 0),
            },
        }

    def segment_by_sentences(self, transcription_result: dict) -> dict:
        full_text = transcription_result.get("text", "")
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        duration = transcription_result.get("duration", 0)
        avg_duration = duration / max(len(sentences), 1)

        segments = []
        current_time = 0
        for i, sentence in enumerate(sentences):
            start = current_time
            end = current_time + avg_duration
            segments.append({
                "segment_id": i + 1,
                "start": round(start, 2),
                "end": round(end, 2),
                "text": sentence,
                "duration": round(avg_duration, 2),
                "word_count": len(sentence.split()),
                "confidence": 0.85,
            })
            current_time = end

        return {
            "segments": segments,
            "total_segments": len(segments),
            "metadata": {
                "method": "sentence_based",
                "total_duration": duration,
            },
        }

    def segment_by_time(self, transcription_result: dict, segment_duration: float = 30.0) -> dict:
        full_text = transcription_result.get("text", "")
        duration = transcription_result.get("duration", 0)
        words = full_text.split()
        total_words = len(words)
        total_duration = duration

        words_per_segment = max(1, int(total_words * (segment_duration / total_duration))) if total_duration > 0 else total_words

        segments = []
        seg_id = 0
        for i in range(0, total_words, words_per_segment):
            seg_words = words[i:i + words_per_segment]
            seg_start = (i / total_words) * total_duration if total_words > 0 else 0
            seg_end = min(((i + len(seg_words)) / total_words) * total_duration, total_duration)

            seg_id += 1
            segments.append({
                "segment_id": seg_id,
                "start": round(seg_start, 2),
                "end": round(seg_end, 2),
                "text": " ".join(seg_words),
                "duration": round(seg_end - seg_start, 2),
                "word_count": len(seg_words),
                "confidence": 0.8,
            })

        return {
            "segments": segments,
            "total_segments": len(segments),
            "metadata": {
                "method": "time_based",
                "segment_duration": segment_duration,
                "total_duration": total_duration,
            },
        }

    def segment_speakers(self, transcription_result: dict) -> dict:
        segments = transcription_result.get("segments", [])
        result_segments = []
        current_speaker = 1
        last_end = 0
        speaker_changes = 0

        for i, seg in enumerate(segments):
            gap = seg.get("start", 0) - last_end if i > 0 else 0
            if gap > 2.0 and speaker_changes < 10:
                current_speaker += 1
                speaker_changes += 1

            result_segments.append({
                "segment_id": i + 1,
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", ""),
                "duration": round(seg.get("end", 0) - seg.get("start", 0), 2),
                "word_count": len(seg.get("text", "").split()),
                "confidence": 0.7,
                "speaker_id": f"speaker_{current_speaker}",
            })
            last_end = seg.get("end", 0)

        return {
            "segments": result_segments,
            "total_segments": len(result_segments),
            "metadata": {
                "method": "speaker_heuristic",
                "speakers_detected": current_speaker,
                "total_duration": transcription_result.get("duration", 0),
            },
        }

    def process_segmentation(self, transcription_result: dict, method: str = "silence", **kwargs) -> dict:
        if not transcription_result.get("text"):
            return self._empty_result(method, transcription_result)

        if method == "silence":
            result = self.segment_by_silence(transcription_result, **kwargs)
        elif method == "sentence":
            result = self.segment_by_sentences(transcription_result)
        elif method == "time":
            result = self.segment_by_time(transcription_result, **kwargs)
        elif method == "speaker":
            result = self.segment_speakers(transcription_result)
        else:
            result = self.segment_by_silence(transcription_result, **kwargs)

        result["segments"] = self._merge_short_segments(result["segments"])
        result["segments"] = self._remove_empty_segments(result["segments"])
        result["segments"] = self._normalize_timestamps(result["segments"])
        result["total_segments"] = len(result["segments"])

        return result

    def _build_segment(self, segments: list, words: list) -> dict:
        text = " ".join(w["word"] for w in words)
        probs = [w.get("probability", 0.8) for w in words]
        avg_confidence = sum(probs) / len(probs) if probs else 0.8
        return {
            "segment_id": len(segments) + 1,
            "start": round(words[0]["start"], 2),
            "end": round(words[-1]["end"], 2),
            "text": text,
            "duration": round(words[-1]["end"] - words[0]["start"], 2),
            "word_count": len(words),
            "confidence": round(avg_confidence, 3),
        }

    def _empty_result(self, method: str, transcription_result: dict) -> dict:
        return {
            "segments": [],
            "total_segments": 0,
            "metadata": {
                "method": method,
                "total_duration": transcription_result.get("duration", 0),
            },
        }

    def _merge_short_segments(self, segments: list, min_duration: float = 2.0) -> list:
        if not segments:
            return segments
        merged = [segments[0].copy()]
        for seg in segments[1:]:
            if merged[-1]["duration"] < min_duration:
                merged[-1]["text"] += " " + seg["text"]
                merged[-1]["end"] = seg["end"]
                merged[-1]["duration"] = round(seg["end"] - merged[-1]["start"], 2)
                merged[-1]["word_count"] += seg.get("word_count", 0)
            else:
                merged.append(seg.copy())
        return merged

    def _remove_empty_segments(self, segments: list) -> list:
        return [s for s in segments if s.get("text", "").strip()]

    def _normalize_timestamps(self, segments: list) -> list:
        if not segments:
            return segments
        normalized = [segments[0].copy()]
        for seg in segments[1:]:
            new_seg = seg.copy()
            if new_seg["start"] < normalized[-1]["end"]:
                new_seg["start"] = normalized[-1]["end"]
            if new_seg["end"] <= new_seg["start"]:
                new_seg["end"] = new_seg["start"] + 0.1
            normalized.append(new_seg)
        return normalized


@lru_cache()
def get_segmentation_service() -> SegmentationService:
    return SegmentationService()
