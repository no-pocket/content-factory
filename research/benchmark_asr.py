"""Offline paired ASR timing on authorized PT/EN excerpts, no reference WER claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import importlib.metadata
import platform
import resource
import subprocess
import tempfile
import time
from pathlib import Path

from faster_whisper import WhisperModel
from app.store import load

VOCABULARY = 'GTA VI, Rockstar Games, Vice City, Lucia, Jason, Leonida.'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['tiny', 'base'], required=True)
    parser.add_argument('--pt-job', required=True)
    parser.add_argument('--en-job', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = Path.home() / '.cache/huggingface/hub' / ('models--Systran--faster-whisper-' + args.model) / 'refs/main'
    revision = reference.read_text(encoding='utf-8').strip()
    started = time.monotonic()
    model = WhisperModel(args.model, device='cpu', compute_type='int8', cpu_threads=4,
                         local_files_only=True, revision=revision)
    loaded_seconds = time.monotonic() - started
    rows = []
    with tempfile.TemporaryDirectory(prefix='cf-asr-benchmark-') as temporary:
        for expected, jid in [('pt', args.pt_job), ('en', args.en_job)]:
            job = load(jid)
            audio = Path(temporary) / (expected + '.wav')
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', job['source'], '-t', '60',
                            '-map', '0:a:0', '-vn', '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(audio)],
                           check=True, capture_output=True, timeout=120)
            with audio.open('rb') as handle:
                audio_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
            for repeat in range(2):
                started = time.monotonic()
                generator, info = model.transcribe(str(audio), task='transcribe', beam_size=5,
                                                   vad_filter=True, word_timestamps=True,
                                                   initial_prompt=VOCABULARY)
                segments = [{'start': s.start, 'end': s.end, 'text': s.text,
                             'words': [{'start': w.start, 'end': w.end, 'text': w.word} for w in (s.words or [])]}
                            for s in generator]
                row = {'source_job': jid, 'expected_corpus_language': expected, 'repeat': repeat,
                       'language_detected': info.language, 'language_probability': info.language_probability,
                       'audio_sha256': audio_hash, 'audio_duration': info.duration,
                       'wall_seconds': round(time.monotonic() - started, 3), 'segments': segments,
                       'process_peak_rss_MiB_so_far': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}
                rows.append(row)
                print(args.model, expected, repeat, row['wall_seconds'], info.language, flush=True)
    report = {'model': args.model, 'device': 'cpu', 'compute_type': 'int8', 'threads': 4,
              'cached_model_revision': revision,
              'runtime': {'python': platform.python_version(),
                          'faster_whisper': importlib.metadata.version('faster-whisper'),
                          'ctranslate2': importlib.metadata.version('ctranslate2')},
              'beam_size': 5, 'task': 'transcribe', 'language_forced': False,
              'initial_prompt': VOCABULARY, 'vad_filter': True, 'word_timestamps': True,
              'local_files_only': True, 'model_load_seconds': round(loaded_seconds, 3),
              'process_peak_rss_MiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
              'runs': rows, 'reference_transcript': None, 'WER': None, 'human_quality_verdict': None,
              'limits': 'Two 60-second excerpts, two repetitions. Probability is not accuracy; no human reference. Linux RSS is per isolated model process, includes runtime.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(args.output, flush=True)


if __name__ == '__main__':
    main()
