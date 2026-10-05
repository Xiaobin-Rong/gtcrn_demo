"""Regenerate all ten demo RNNoise clips with the official v0.2 release model."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA256 = 'dece58eabca6a722a0bd9dbc8dfadba27abac1271760fad65e1071f54717dc78'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RNNoise:
    def __init__(self, library):
        self.lib = ctypes.CDLL(str(Path(library).resolve()))
        self.lib.rnnoise_create.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_create.restype = ctypes.c_void_p
        self.lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_get_frame_size.restype = ctypes.c_int
        self.lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
        self.lib.rnnoise_process_frame.restype = ctypes.c_float
        if self.lib.rnnoise_get_frame_size() != 480:
            raise ValueError('Expected RNNoise v0.2 480-sample frames')

    def __call__(self, audio):
        length = len(audio)
        # Drain the delayed spectrum and overlap-add frames, then remove 20 ms.
        padded = np.pad(audio, (0, (-length) % 480 + 960)) * np.float32(32768)
        output = np.empty_like(padded)
        state = self.lib.rnnoise_create(None)
        if not state:
            raise RuntimeError('rnnoise_create failed')
        try:
            for offset in range(0, len(padded), 480):
                inp = np.ascontiguousarray(padded[offset:offset + 480])
                out = output[offset:offset + 480]
                self.lib.rnnoise_process_frame(state,
                    out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                    inp.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
        finally:
            self.lib.rnnoise_destroy(state)
        return output[960:960 + length] / np.float32(32768)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, help='Built RNNoise v0.2 shared library')
    parser.add_argument('--source', required=True, help='Patched official release source directory')
    args = parser.parse_args()
    source = Path(args.source)
    if sha256(source / 'src/rnnoise_data.c') != MODEL_SHA256:
        raise ValueError('Use the official v0.2 release tarball bundled default model')
    rnnoise = RNNoise(args.library)
    inputs = []
    for directory in ('DNS3_test_set', 'DNS3_blind_test_set'):
        paths = sorted(path for path in (ROOT / 'samples' / directory).glob('*.wav')
                       if not any(tag in path.stem for tag in ('_RNNoise', '_GTCRN', '_clean')))
        if len(paths) != 5:
            raise ValueError(f'Expected five noisy inputs in {directory}, found {len(paths)}')
        inputs.extend(paths)
    manifest = {
        'rnnoise_version': 'v0.2',
        'model': 'official release tarball bundled default (rnnoise_create(NULL))',
        'model_sha256': MODEL_SHA256,
        'model_header_sha256': sha256(source / 'src/rnnoise_data.h'),
        'library_sha256': sha256(args.library),
        'generator_sha256': sha256(__file__),
        'processing_sample_rate': 48000,
        'output_sample_rate': 16000,
        'output_subtype': 'PCM_16',
        'compensated_delay_samples_48k': 960,
        'resampling': 'scipy.signal.resample_poly defaults, 16k->48k->16k',
        'clips': [],
    }
    for path in inputs:
        noisy, rate = sf.read(path, dtype='float32')
        if rate != 16000 or noisy.ndim != 1:
            raise ValueError(f'Expected 16 kHz mono input: {path}')
        input48 = resample_poly(noisy, 3, 1).astype(np.float32)
        enhanced = resample_poly(rnnoise(input48), 1, 3).astype(np.float32)
        if len(enhanced) != len(noisy) or not np.all(np.isfinite(enhanced)):
            raise ValueError(f'Invalid enhanced output: {path}')
        stem = path.stem.removesuffix('_noisy')
        destination = path.with_name(stem + '_RNNoise_v0.2.wav')
        sf.write(destination, enhanced, rate, subtype='PCM_16')
        decoded, decoded_rate = sf.read(destination)
        if decoded_rate != rate or len(decoded) != len(noisy) or not np.any(decoded):
            raise ValueError(f'Invalid encoded WAV: {destination}')
        manifest['clips'].append({
            'input': path.relative_to(ROOT).as_posix(),
            'output': destination.relative_to(ROOT).as_posix(),
            'input_sha256': sha256(path), 'output_sha256': sha256(destination),
            'samples_16k': len(noisy),
            'peak_before_pcm_encoding': float(np.max(np.abs(enhanced))),
            'samples_outside_pcm16_range': int(np.count_nonzero(
                (enhanced < -1) | (enhanced >= 1))),
        })
        print(destination.relative_to(ROOT))
    (ROOT / 'rnnoise-v0.2-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
