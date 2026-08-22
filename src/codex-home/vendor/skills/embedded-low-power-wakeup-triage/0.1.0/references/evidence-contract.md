# Low-Power Evidence Contract

Record each attempt with: image identity, `boot_id`, uptime, app PID, request time, ACK/result, wakeup source/counter, suspend entry/exit, and restored health state.

| Gate | Minimum evidence | Stop condition |
| --- | --- | --- |
| Smoke | one complete transition and identity comparison | refusal, crash, or unclassified reset |
| Short cycle | 5–20 controlled cycles with source classification | unexpected wake or state drift |
| Long/soak | owner-approved duration, counters, and final restoration | any fatal log, output stall, or missing restoration |

Treat device access, configuration writes, reset, flash, OTA, and wake-source changes as separate authorization boundaries.
