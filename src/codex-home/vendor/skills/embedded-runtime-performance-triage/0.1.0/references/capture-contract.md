# Runtime Capture Contract

Record image/version, process identity, start/end wall time, sample cadence, sample count, and a content hash for raw evidence.

| Signal | Use | Do not infer |
| --- | --- | --- |
| CPU jiffy delta | CPU-heavy threads | source ownership |
| Context-switch delta | scheduling contention | a specific lock without stack evidence |
| `state` / `wchan` | wait class | root cause |
| meminfo/diskstats | pressure trend | DDR bandwidth saturation |
| queue/drop counters | backpressure evidence | transport root cause without a timeline |

Prefer 30-second aggregates for added probes and retain raw captures only outside long-lived knowledge text.
