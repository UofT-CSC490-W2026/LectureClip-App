# Python Hotspot Profiling

This repository includes a focused profiling pass for the backend `process-results` path using Python's standard library `cProfile`, following the guidance in the [`profile` / `cProfile` docs](https://docs.python.org/3/library/profile.html).

The goals were:

- profile five important Python functions on the transcript-to-embedding path
- identify which ones were true Python hotspots rather than AWS/network bottlenecks
- make targeted improvements where the profiler showed meaningful payoff
- record the reasoning and measured impact for future work

## Profiling Tool And Harness

The measurements were taken with a dedicated harness at [`scripts/profile_python_hotspots.py`](scripts/profile_python_hotspots.py).

Set up an isolated environment and run it with:

```bash
python -m venv .venv-profile
.venv-profile/bin/pip install -r tests/requirements.txt
.venv-profile/bin/python scripts/profile_python_hotspots.py
```

The harness uses `cProfile.Profile()` programmatically so each target function can be profiled in isolation with a consistent workload.

## Workload Used

To keep the numbers focused on Python work instead of AWS latency, the harness uses synthetic but realistic data:

- `3900` Amazon Transcribe-style items for token parsing
- `3600` processed tokens for speaker chunking
- `600` transcript segments for embedding generation and Aurora writes
- `1024`-dimension embedding vectors to match the current Titan embedding shape

External services are mocked:

- `bedrock_utils.embed_text()` is replaced with a local stub
- `aurora_utils._execute()` is replaced with a local stub

That means these measurements are best read as CPU and allocation profiles for local Python logic. They are not end-to-end latency numbers for real Bedrock, S3, or Aurora calls.

## Functions Profiled

| Function | File | Why it was chosen |
|---|---|---|
| `_process_items()` | [`src/lambdas/process-results/transcript_utils.py`](src/lambdas/process-results/transcript_utils.py) | Runs over every Transcribe token and normalizes punctuation into the preceding word. |
| `_combine_by_speaker()` | [`src/lambdas/process-results/transcript_utils.py`](src/lambdas/process-results/transcript_utils.py) | Builds speaker chunks and repeatedly grows strings, making it a natural hotspot candidate. |
| `generate_text_embeddings()` | [`src/lambdas/process-results/bedrock_utils.py`](src/lambdas/process-results/bedrock_utils.py) | Executes per segment and builds metadata records around each embedding call. |
| `insert_segments()` | [`src/lambdas/process-results/aurora_utils.py`](src/lambdas/process-results/aurora_utils.py) | Performs per-segment UUID work, parameter building, and mocked Aurora write setup. |
| `insert_embeddings()` | [`src/lambdas/process-results/aurora_utils.py`](src/lambdas/process-results/aurora_utils.py) | Serializes every embedding vector into pgvector text and was expected to be the largest pure-Python cost. |

## Baseline Findings

The baseline `cProfile` run confirmed that `insert_embeddings()` was the clear Python hotspot.

Key baseline observations:

- `insert_embeddings()` spent most of its time in Python string construction for `"[" + ",".join(str(v) for v in embedding) + "]"`.
- `generate_text_embeddings()` was dominated more by repeated `uuid4()` and timestamp work than by the mocked embedding call itself.
- `insert_segments()` spent most of its cumulative time in deterministic `uuid5()` creation.
- `_process_items()` and `_combine_by_speaker()` were real CPU candidates, but far smaller than vector serialization.

## Changes Made

### `_process_items()`

In [`src/lambdas/process-results/transcript_utils.py`](src/lambdas/process-results/transcript_utils.py):

- replaced `math.floor(float(...))` with `int(float(...))` because Transcribe start times are non-negative
- hoisted `result.append` to a local for the tight loop

### `_combine_by_speaker()`

This function was profiled and reviewed, but no optimization was retained.

An alternate implementation was tested, but it regressed the benchmark under this workload. The function remains the original version, and the profiler results are documented here so future work can revisit it with larger transcripts or different chunking rules.

### `generate_text_embeddings()`

In [`src/lambdas/process-results/bedrock_utils.py`](src/lambdas/process-results/bedrock_utils.py):

- hoisted loop-invariant callables and append operations out of the inner loop
- reused a single batch timestamp instead of formatting a new ISO timestamp per segment

### `insert_segments()`

In [`src/lambdas/process-results/aurora_utils.py`](src/lambdas/process-results/aurora_utils.py):

- hoisted `_execute`, `uuid.uuid5`, and `uuid.NAMESPACE_URL` to locals
- avoided recomputing `float(start_s)` multiple times per row
- cached the final index boundary to simplify the next-segment lookup

### `insert_embeddings()`

In [`src/lambdas/process-results/aurora_utils.py`](src/lambdas/process-results/aurora_utils.py):

- replaced Python-level generator plus `",".join(...)` vector serialization with `json.dumps(..., separators=(",", ":"))`
- hoisted `_execute`, `uuid.uuid4`, and the serializer to locals

This was the biggest win because the old implementation spent millions of Python function calls converting floats to strings one element at a time.

## Measured Results

The table below compares the baseline run against the final run using the same harness and workload. The numbers are cumulative milliseconds per function call reported by the harness.

| Function | Baseline ms/call | Final ms/call | Impact |
|---|---:|---:|---:|
| `_process_items()` | 1.457 | 1.236 | 15.2% faster |
| `_combine_by_speaker()` | 0.695 | 0.739 | no retained improvement |
| `generate_text_embeddings()` | 3.296 | 2.874 | 12.8% faster |
| `insert_segments()` | 2.317 | 2.224 | 4.0% faster |
| `insert_embeddings()` | 112.774 | 56.122 | 50.2% faster |

## What The Results Mean

- The most valuable optimization was in `insert_embeddings()`. Vector serialization is still the main cost inside that function, but moving the work into `json.dumps()` cut the cumulative cost roughly in half.
- `generate_text_embeddings()` improved because repeated per-record bookkeeping was reduced. After the change, UUID generation is now the dominant remaining cost in the mocked version.
- `insert_segments()` improved only modestly because deterministic `uuid5()` generation still dominates the function.
- `_process_items()` saw a useful but smaller improvement from tighter loop mechanics.
- `_combine_by_speaker()` should remain unchanged for now. It is still worth profiling again if transcript sizes or chunking rules change, but the tested refactor did not beat the original implementation.

## Deep Dive Example: `insert_embeddings()`

`insert_embeddings()` is the clearest example of why profiling mattered.

Before the change, each embedding vector was serialized with:

```python
"[" + ",".join(str(v) for v in emb_record["embedding"]) + "]"
```

That looks compact, but it does a lot of Python work:

- it iterates once per float in the embedding
- it calls `str(v)` for every element
- it feeds all of those Python strings into `",".join(...)`
- it repeats that work for every segment in the lecture

With the profiling harness workload, that meant:

- `600` segment records
- `1024` floats per vector
- about `614,400` float-to-string conversions per function call

In the baseline profile, the hot path inside `insert_embeddings()` was dominated by the generator expression and `str.join`, which showed up as millions of Python-level calls across repeated runs.

The new code uses:

```python
json.dumps(emb_record["embedding"], separators=(",", ":"))
```

This change was effective for two reasons:

1. The heavy serialization loop moves into the standard library JSON encoder, which is much more efficient than doing float formatting and joining in Python bytecode.
2. The output format is still compatible with what the pgvector insert path needs: a JSON array like `[0.1,0.2,...]` is also a valid vector literal for the current SQL parameter usage.

So the optimization did not just save a few attribute lookups. It replaced a Python-managed inner loop with a library routine designed to serialize large sequences efficiently.

That is why the impact was so much larger than the other changes:

- baseline cumulative cost: `112.774 ms/call`
- final cumulative cost: `56.122 ms/call`
- improvement: about `50.2%`

Just as importantly, the profile after the change still shows `insert_embeddings()` as the main hotspot, but for a very different reason: the remaining time is now concentrated inside `json.encoder.iterencode`, which means the wasteful Python generator overhead has been removed.

## Realistic Usage Patterns

These functions sit on a path whose work scales primarily with transcript size, segment count, and embedding dimension.

### Transcript parsing functions

`_process_items()` and `_combine_by_speaker()` scale with the number of Amazon Transcribe items:

- one pronunciation token is usually one spoken word
- punctuation tokens are additional items
- a one-hour lecture can easily produce many thousands of items

A realistic pattern is:

- short clip: `2-5` minutes, maybe `300-1000` items
- medium lecture: `20-30` minutes, maybe `3,000-8,000` items
- long lecture: `60+` minutes, potentially `10,000+` items

These functions are linear in transcript size, so they are usually safe, but they are called on every processed lecture and run before any embeddings are created. That makes them good candidates for lightweight loop improvements even when the per-call savings are modest.

### `generate_text_embeddings()`

This function scales with the number of speaker chunks produced by `_combine_by_speaker()`.

In realistic usage:

- highly continuous speech with long same-speaker runs produces fewer segments
- more speaker switching or short sentence boundaries produces more segments
- the `_MAX_CHUNK_CHARS` limit also pushes segment counts upward for longer lectures

A practical rule of thumb is that segment counts are much smaller than raw token counts, but they can still be in the hundreds for a single lecture. That matters because each segment currently triggers:

- one Bedrock embedding request
- one metadata record allocation
- one later Aurora segment insert
- one later Aurora embedding insert

So even modest per-segment Python overhead can compound quickly when lectures are processed in batches.

### `insert_segments()`

`insert_segments()` performs one database write per segment. For a lecture that becomes `400` chunks, this function prepares and issues roughly `400` segment upserts.

The profiler shows that its remaining local cost is mostly deterministic UUID generation, not list handling or float conversion. That means future improvements here are more likely to come from architectural changes such as batching or reducing write frequency, rather than more micro-optimizations in Python.

### `insert_embeddings()`

This function is the most sensitive to realistic usage because its cost grows with both:

- number of segments
- embedding dimension

For example:

- `200` segments at `1024` dimensions means serializing `204,800` floats
- `600` segments at `1024` dimensions means serializing `614,400` floats
- larger embedding models or finer transcript chunking push that number higher

In other words, `insert_embeddings()` has a multiplicative scaling pattern:

- more segments means more write operations
- larger vectors mean more serialization work per write

That is why it is the most important hotspot to watch under production-style lecture workloads.

## Quotas And Operational Considerations

Exact AWS quotas vary by account, region, and any quota increases already applied, so the practical guidance here is about load shape rather than a single hard number.

The main realistic pressure points are:

- Bedrock request rate: `generate_text_embeddings()` makes one embedding request per segment, so higher segment counts directly increase outbound model traffic.
- Aurora Data API call volume: `insert_segments()` and `insert_embeddings()` each perform one `_execute()` call per record, which means a lecture with `N` segments currently drives roughly `2N + 1` Aurora writes when you include `upsert_lecture()`.
- Lambda duration budget: `process-results` has a long timeout, but very long transcripts or batch processing can still turn Python-side overhead into meaningful extra runtime.
- Payload size growth: larger embeddings and more verbose transcript text increase SQL parameter sizes and serialization cost.

A realistic per-lecture pattern looks like this:

- `1` lecture row upsert
- `N` segment upserts
- `N` embedding inserts
- `N` Bedrock embedding requests

So if a lecture produces `500` segments, the current flow is approximately:

- `1` Aurora lecture write
- `500` Aurora segment writes
- `500` Aurora embedding writes
- `500` Bedrock embedding calls

That is why the write-path functions were strong hotspot candidates even though the profiling harness mocked AWS itself. The Python work they do is repeated at exactly the same rate as the downstream service calls.

## How To Use This In Practice

For realistic capacity planning, these functions are best thought of in three tiers:

- `_process_items()` and `_combine_by_speaker()` are transcript-size functions
- `generate_text_embeddings()` and `insert_segments()` are segment-count functions
- `insert_embeddings()` is a segment-count times vector-dimension function

If future workloads start involving:

- longer lectures
- finer chunking
- higher embedding dimensions
- more concurrent lecture processing

then `insert_embeddings()` should be the first function to revisit, followed by the overall per-segment write pattern in Aurora rather than only more Python-level tuning.

## Verification

The implementation changes were verified with:

```bash
.venv-profile/bin/pip install -r tests/requirements.txt
.venv-profile/bin/pytest tests/test_process_results.py
```

Result:

- `29` tests passed

The handler-oriented tests were also tightened so Aurora writes are mocked consistently, keeping the test suite aligned with the profiling approach and preventing accidental network-bound behavior during unit tests.
