# Asynchronous Execution

## Concurrency Window

Evaluate creates asynchronous tasks for pending jobs and limits concurrent provider calls with a global semaphore. `max_concurrency` determines the size of this window; the default is ten.

As soon as an active call finishes, the next waiting job occupies the free slot. The limit applies across all model profiles rather than separately per model.

Tasks use LiteLLM's asynchronous interface. Backoff and cooldown waits happen outside the semaphore and do not occupy a concurrency slot.

The orchestration lives in `runner.py`. `job_execution.py` owns semaphore usage, cooldowns, retry policy, provider calls, parsing, and evaluation.

## Rate Limits

Rate limits depend on the model, project, and organization, so the implementation does not hard-code OpenAI usage-tier values.

Current limits must be checked in the provider console. For OpenAI, the official documentation covers both organization/project limits and model-specific tables:

- <https://platform.openai.com/docs/guides/rate-limits/usage-tiers>
- <https://platform.openai.com/docs/models/gpt-5-mini>

Retry delay precedence:

1. The provider's `Retry-After` header.
2. Relevant rate-limit reset headers.
3. Exponential backoff with random jitter.

`429`, timeouts, and temporary `5xx` errors are classified as retryable. Authentication, bad-request, schema, and content-policy errors are not retried automatically.

Provider SDK retries are explicitly disabled. Only `job_execution.py` may repeat requests, ensuring that the count, runtime, and error for each attempt remain observable. If a run config sets `max_retries: 0`, a timeout is stored as a final transport error and the request is not sent again.

A model-specific rate-limit error creates a cooldown for that model profile. Other model profiles may continue. Waiting retries do not occupy a global concurrency slot.

Failed requests often still count against provider minute limits, so backoff must not become a tight retry loop.

## Persistence

Each final attempt artifact stores:

- a UTC timestamp,
- runtime for the final LLM call and all request attempts,
- retry number,
- failed attempts and retry wait times,
- the configured reasoning effort,
- provider and model metadata,
- hashes of the prompts actually sent,
- usage data,
- rate-limit metadata when available,
- the raw response or error classification,
- parsing and evaluation results.

Individual request attempts are grouped in the final attempt artifact rather than materialized as separate files.

After a successful provider call, the same job is not sent again even if the model response is semantically invalid.

## Deterministic Order

Before execution, the job list is shuffled deterministically with a seed derived from the run config. This prevents complexity tiers and models from being placed in systematic time blocks that might correlate with provider load or time-of-day effects.
