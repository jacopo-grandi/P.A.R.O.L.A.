# Telling who speaks with sherpa-onnx — light trial, 2026-10-16

**Question.** How wrong is sherpa-onnx (pyannote 3.0 segmentation + WeSpeaker VoxCeleb ResNet34-LM voice model + simple clustering) at saying who speaks, before we use it in the app?

**Data.** Two meetings from the AMI test set (IS1009a, 14 min; ES2004a, 17.5 min; 4 people each, Mix-Headset audio), with the `only_words` references from pyannote/AMI-diarization-setup. AMI is under CC BY 4.0, the references under Apache-2.0.

**Metric.** DER (diarization error rate) on 10 ms frames, with no tolerance at the edges, overlaps included: time missed + invented + given to the wrong person, divided by the reference's speech time (`parola.eval.diarization`, with hand-built tests). This is the same way pyannote reports its numbers.

**Results** (sherpa-onnx 1.13.8, 4 threads on the CPU of an M4 Pro, about 100 s for 31.5 min of audio).

| Configuration | DER | IS1009a | ES2004a | Voices found (IS / ES) |
|---|---|---|---|---|
| threshold 0.5 (default) | 61.2% | 51.3% | 68.7% | 16 / 67 |
| threshold 0.7 | 46.7% | 47.2% | 46.3% | 7 / 38 |
| threshold 0.8 | 39.6% | 49.1% | 32.4% | 3 / 20 |
| threshold 0.9 | 33.8% | 42.4% | 27.2% | 2 / 12 |
| 4 voices given (oracle) | 36.3% | 43.1% | 31.2% | 4 / 4 |

Missed speech (7–12%) and invented speech (4–7%) are normal. Almost all the error is **voice given to the wrong person** (11–52%). For comparison, pyannote reports 18.8% on AMI (IHM) with pipeline 3.1, which uses the same segmentation and the same voice model, and 17.0% with community-1: the difference lies in how the voices are clustered.

**On the real meeting** ("Altri" channel of the test meeting, 30 min): threshold 0.5 → 11 voices, 0.7 → 4, 0.9 → 2. Without a reference there is no way to know which is right. Memory: 0.55 GB peak. Time: about 2 minutes.

**What it means.** As it is, sherpa-onnx mixes up the voices too much for the app: one turn in three would go to the wrong speaker. The voice model and the segmentation do not seem to be the problem, because they are the same as pyannote's. The problem is the clustering.

**Limits.** Only two meetings (31.5 min), in English, recorded in a room in 2005: no Meet audio and no Italian.

## Better clustering on top of sherpa-onnx

**Method.** sherpa-onnx's pieces (threshold 0.5: many small pieces) are analysed again: each one is split into windows, each window gets a voice print (the same WeSpeaker), and the voice prints are grouped with spectral clustering. The number of voices is estimated from the largest gap between eigenvalues (NME-SC, as in NeMo). Each piece takes the most frequent voice among its windows. The prototype is outside the project: only numpy and scipy, no new dependency.

| Configuration | DER | IS1009a | ES2004a | Voices found (IS / ES) |
|---|---|---|---|---|
| sherpa-onnx, threshold 0.7 | 46.7% | 47.2% | 46.3% | 7 / 38 |
| sherpa-onnx, 4 voices given (oracle) | 36.3% | 43.1% | 31.2% | 4 / 4 |
| **spectral, 3 s windows (step 1.5)** | **30.0%** | 33.7% | 27.2% | 5 / 5 |
| spectral, 2 s windows (step 1) | 31.9% | 34.5% | 30.0% | 4 / 5 |
| spectral, each window decides (3 s) | 34.1% | 42.1% | 28.2% | 5 / 5 |
| spectral, each window decides (1.5 s) | 39.0% | 44.3% | 35.1% | 4 / 5 |

The error goes down from 47% to 30%, and the number of voices becomes almost right: 4–5 for meetings with 4 people. Two parts of the error remain: swapped voices (10–18%) and missed or invented speech (11–19%), which comes from the segmentation and not from the clustering.

**Comparison with pyannote.** pyannote's 17–19% is measured on all 16 meetings of the AMI test set, not on these two: it is not a like-for-like comparison. IS1009a seems the harder of the two. To know how far off we really are, pyannote would have to be measured on these same two meetings.

**Limits.** Six configurations tried on the same two meetings (31.5 min): the best parameters may not hold elsewhere.
