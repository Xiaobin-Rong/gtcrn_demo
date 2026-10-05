# GTCRN

Audio examples for the single-channel speech enhancement model GTCRN.

## RNNoise v0.2 examples

Both comparison tables now use the **default model bundled in the official
[RNNoise v0.2 release](https://github.com/xiph/rnnoise/releases/tag/v0.2)**, released
April 15, 2024. All ten RNNoise outputs were regenerated from the existing noisy
WAVs on October 4, 2026. GTCRN, noisy, and clean audio remain the original files.
This demo update accompanies the [benchmark update](https://github.com/Xiaobin-Rong/gtcrn/pull/103).

Processing uses the same model and framing protocol as that benchmark: upsample
the existing mono 16 kHz audio to 48 kHz with SciPy `resample_poly`, scale float
samples by 32768, use fresh `rnnoise_create(NULL)` state per clip, zero-pad the
last partial 480-sample frame, drain two frames, and compensate the fixed
960-sample (20 ms) output delay. Downsample to 16 kHz, retain the input sample
count, and write PCM16 WAVs for browser playback. There is no loudness
normalization, VAD gating, or additional postfilter. The 16 kHz source clips do
not contain native fullband audio; upsampling does not restore that bandwidth.

[`rnnoise-v0.2-manifest.json`](rnnoise-v0.2-manifest.json) records the model,
generator, binary, input/output hashes, lengths, and peaks. PCM16 encoding saturates 15 samples in the kitchen-vessels clip (peak 1.077);
all other clips remain within range. No gain adjustment was applied. Versioned output filenames identify
the release and avoid reusing cached historical RNNoise URLs.

## Reproduce

From the repository root, with Python 3.12, a C compiler, make, patch, and curl:

```sh
mkdir -p generation-work
cd generation-work
curl -fL https://github.com/xiph/rnnoise/releases/download/v0.2/rnnoise-0.2.tar.gz -o rnnoise-0.2.tar.gz
curl -fL https://github.com/xiph/rnnoise/commit/372f7b4b76cde4ca1ec4605353dd17898a99de38.patch -o build-fix.patch
shasum -a 256 rnnoise-0.2.tar.gz build-fix.patch
tar -xzf rnnoise-0.2.tar.gz
cd rnnoise-0.2
patch -p1 < ../build-fix.patch
./configure --disable-examples
make -j4
cd ../..
python3.12 -m venv generation-work/venv
generation-work/venv/bin/pip install -r scripts/requirements.txt
# On Linux substitute .so for .dylib.
generation-work/venv/bin/python scripts/regenerate_rnnoise.py \
  --library generation-work/rnnoise-0.2/.libs/librnnoise.dylib \
  --source generation-work/rnnoise-0.2
```

Verify these download SHA-256 hashes before extracting/building:

- Release: `90fce4b00b9ff24c08dbfe31b82ffd43bae383d85c5535676d28b0a2b11c0d37`
- Build fix: `c491dfba7784ba027f7293259652053bb63bc834aae693269e4b5cf1dda54b05`

The patch is RNNoise's immediate post-release compilation-only fix, needed on
arm64; it does not alter the weights or denoising algorithm. Use the release
tarball: its bundled weights differ from the external model fetched by the Git
tag checkout's `autogen.sh`. The generator verifies the bundled model source
hash. Binary hashes and small numerical differences can vary by build/platform.
