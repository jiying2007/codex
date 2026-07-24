---
name: embedded-audio-stream-triage
description: "Use when the user asks Codex to diagnose embedded audio playback or transport problems such as PCM/encoded stream discontinuity, startup delay, volume resets, clipping, underrun/overrun, dropped first words or tails, sequence gaps, reordering, echo, or unsynchronized start/data/end paths across shared memory, pub-sub, callbacks, queues, and hardware output."
version: 0.1.0
last_updated: 2026-07-14
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Embedded Audio Stream Triage

Trace an audio stream end to end before changing buffer sizes or retry behavior.

## Inputs

Accept any combination of:

- producer, transport, decoder, player, and hardware-output source paths;
- PCM or encoded format details, frame sizes, sample rate, channels, bit depth, and stream identifiers;
- sequence, timestamp, queue-depth, underrun, overflow, latency, volume, and callback logs;
- shared-memory envelopes, pub-sub messages, ring buffers, task queues, and start/data/end events;
- a known-good capture, reproduction conditions, or an audible symptom description.

## Workflow

1. Fix the stream contract:
   - map every producer-to-speaker hop;
   - record format, frame duration, alignment, stream ID, sequence, timestamp, start/end semantics, and gain ownership;
   - distinguish control messages from payload transport and state how they are synchronized.
2. Build one timeline:
   - normalize clocks and calculate expected bytes and duration per frame;
   - mark startup, first audible sample, gaps, duplicates, reordering, stream rollover, drain, tail flush, and device stop;
   - separate observed evidence from inferred timing.
3. Audit lifecycle and ordering:
   - verify start, data, tail, and end are ordered or made idempotent across transports;
   - check duplicate start/end, stale stream IDs, missing sequence reset, late callbacks, and shutdown races;
   - require an explicit policy for loss, reordering, and abandoned streams.
4. Audit buffering and backpressure:
   - compare producer cadence, consumer cadence, queue capacity, watermarks, chunk alignment, and prebuffer delay;
   - identify starvation, overflow, partial-frame handling, padding, and silent data loss;
   - do not increase buffering until the failing boundary is identified and the latency cost is quantified.
5. Audit concurrency and cost:
   - locate blocking callbacks, per-frame allocation or copies, lock contention, priority inversion, and teardown ownership;
   - verify that discarded frames still release buffers and that drain cannot deadlock shutdown.
6. Audit gain and acoustic paths:
   - trace global, per-stream, software, and hardware gain without assuming `100` means unchanged amplitude;
   - distinguish transport gaps, clipping, resampling artifacts, acoustic echo, AEC routing errors, and microphone feedback.
7. Add the smallest probes:
   - prefer stream ID, sequence, byte count, queue depth, underrun/overflow count, first/last timestamp, and drop reason;
   - rate-limit probes and avoid logging raw audio or every packet by default.
8. Validate a focused matrix:
   - cover short and long streams, rapid restart, delayed or missing end, partial tail, slow consumer, sequence gap, volume changes, and shutdown;
   - report host/SIL evidence separately from real-device listening or HIL evidence.

## Output

Return:

- an end-to-end contract and timeline;
- findings ranked by evidence and user-visible impact;
- a minimal probe or patch plan;
- a latency, memory, CPU, and compatibility trade-off summary;
- a focused regression matrix and residual hardware/acoustic risk;
- a gate result: `stable`, `needs-more-data`, `needs-fix`, or `unsafe-to-release`.

## Guardrails

- Do not diagnose audible discontinuity from buffer size alone.
- Do not treat sequence gaps as packet loss until stream rollover, filtering, and logging loss are excluded.
- Do not move control and payload onto different transports without an explicit ordering contract.
- Do not log or archive raw voice content; retain only sanitized counters and short event markers.
- Do not claim echo cancellation or final audio quality without real-device evidence.
