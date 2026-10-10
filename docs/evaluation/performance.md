# Preparation Performance

Preparation combines two independent improvements: a local cache reduces repeated
validation during slot enumeration, while scenario workers improve throughput
across independent boards. The cache stores boolean cross-word and existing-axis
checks for one board and language. It is discarded after enumeration. Parallelism
does not split a scenario or change solver ordering.

## Measurement boundary

The [offline benchmark](../../scripts/benchmark_preparation.py) compares the frozen
pre-cache enumerator with cached serial preparation and cached preparation using
two and four workers. Each trial uses a fresh temporary artifact directory, so
resume hits cannot masquerade as faster generation. The uncached comparison uses
the current coordinator with the pre-change enumeration function. Fixed scenario
fixtures additionally check that serial and spawned execution agree.

```bash
# Short 5D/10D matrix, four scenarios per trial, three repetitions by default.
uv run python scripts/benchmark_preparation.py

# Full 250-/500-word 5D scenarios and small 10D scenarios; potentially hours.
uv run python scripts/benchmark_preparation.py --full --repetitions 3

# Read an existing large scenario and compare its last board/rack enumeration.
uv run python scripts/benchmark_preparation.py --enumeration-only \
  --enumeration-scenario outputs/evaluation/final/scenarios/final.d5.b500.r00.json
```

`--rounds` controls independent scenarios and `--output-parent` chooses the parent
of a newly allocated temporary directory. Existing production artifacts are only
read when explicitly passed for enumeration measurement. There are no LLM calls.
The report path is printed at startup; trial logs, resolved specs, artifacts, and
incrementally saved JSON results remain there for inspection.

The report records Python, OR-Tools, OS, CPU count, physical RAM, hash seed,
certification failures, and scenario fingerprints. Scenario comparisons preserve
every transition and normalize only embedded temporary paths. Timings distinguish
enumeration, remaining optimization, generator steps including the initial move,
preparation, and full subprocess wall time. Times summed over processes are CPU
work durations and can exceed wall time. Summary medians and ranges include failed
trials, whose counts must be considered when comparing them.

RSS monitoring samples the simultaneous parent/child process tree every 100 ms;
it is approximate and may double-count shared pages. Per-process peak RSS is also
recorded. Restricted environments that prohibit process inspection report a null
tree RSS instead. Enumeration reports the recursively reachable cache size,
including referenced keys, separately from process RSS. Timing runs are separate
from that cache-size measurement.

## Correctness evidence

The [reference fixture](../../tests/fixtures/generation_reference.json)
contains six small 2D/5D/10D scenarios over two sampling rounds and every slot list
for their transition racks. It was captured with the unchanged generator before
the submission cleanup, using the fixed recipes in `tests/fixtures/config/`.
Its metadata records the source revision. It replaces a previously referenced
fixture that was absent from Git; it is not evidence from before the cache change.
Regression tests compare serial and real spawn execution with different hash
seeds against this fixture, and compare scenario bytes at identical paths.

[Cache tests](../../tests/test_generation_cache.py) also vary the board, language,
and rack against an independent frozen enumerator and verify cache lifetime.
[Process tests](../../tests/test_preparation_parallel.py) cover worker exceptions,
hard process exits, actual SIGINT, progress counts, shared grammars, missing
snapshots, unregistered files, atomic output, and resumption. Independent existing
brute-force optimality tests remain unchanged.

The [development guide](../development.md) describes the current offline suite.
Provider profiles and small preparation recipes are test-owned, so changes to
active experiments no longer invalidate those regression tests.

Full 250-/500-word scenario throughput and repeated large-workload certification
rates are intentionally left to the separately runnable full matrix. The
automatic four-worker cap is CPU-based; short-run results do not certify its
memory use or timeout behavior for every large workload.

## Local measurements, 9 October 2026

The measurements below were recorded on a
10-CPU, 16-GiB ARM Mac with Python 3.12.3 and OR-Tools 9.15.6755. Tests were not
running concurrently. Each comparison has two repetitions; ranges describe those
two samples rather than a confidence interval.

| Last-board enumeration | Uncached median | Cached median | Speedup | Reachable cache size |
|---|---:|---:|---:|---:|
| `final.d5.b250.r09` | 7.42 s | 3.11 s | 2.39× | 68.4 MiB |
| `final.d5.b500.r00` | 13.02 s | 5.59 s | 2.33× | 135.2 MiB |

All 39,601 and 74,972 slots respectively, including domains and score bounds,
matched the uncached reference. These are enumeration measurements on saved
boards, not timings for generating complete 250-/500-word scenarios.

| Fresh preparation: four scenarios | Cache | Workers | Wall median (range) | Maximum sampled tree RSS |
|---|---|---:|---:|---:|
| 5D, 5 words | off | 1 | 6.30 s (6.18–6.41) | 162 MiB |
| 5D, 5 words | on | 1 | 5.64 s (5.42–5.85) | 162 MiB |
| 5D, 5 words | on | 2 | 4.34 s (4.33–4.36) | 467 MiB |
| 5D, 5 words | on | 4 | 3.37 s (3.26–3.49) | 736 MiB |
| 10D, 3 words | off | 1 | 8.87 s (8.86–8.88) | 164 MiB |
| 10D, 3 words | on | 1 | 6.33 s (6.26–6.39) | 164 MiB |
| 10D, 3 words | on | 2 | 4.78 s (4.66–4.90) | 476 MiB |
| 10D, 3 words | on | 4 | 3.53 s (3.48–3.58) | 732 MiB |

All 16 trials completed, producing 64 scenarios without certification failures.
Corresponding scenarios had identical normalized fingerprints in every variant.
Four workers plus the cache reduced median wall time by factors of 1.87 and 2.52
against uncached serial execution in these small 5D and 10D workloads. Relative
to cached serial execution, the factors were 1.67 and 1.79. These measurements
support the initial four-worker cap on the target Mac for the short workloads;
large-scenario throughput and timeout behavior still require the full matrix.
