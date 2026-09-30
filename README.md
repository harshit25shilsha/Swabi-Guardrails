# Guardrail Service

A standalone, synchronous chat-moderation API for a multi-vendor marketplace covering tours, hotels, rentals, and vehicles. The marketplace backend calls this service before delivering a message and uses the returned decision to deliver or reject it.

The service does not own conversations, users, WebSockets, message storage, or persistence. The marketplace backend remains responsible for those concerns.

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Detection Strategy](#detection-strategy)
- [API Contract](#api-contract)
- [Response Format](#response-format)
- [Categories](#categories)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running the Service](#running-the-service)
- [Testing](#testing)
- [Observability](#observability)
- [Resilience](#resilience)
- [Project Layout](#project-layout)
- [Marketplace Integration](#marketplace-integration)
- [Design Decisions](#design-decisions)
- [Out of Scope](#out-of-scope)

## What It Does

The service classifies marketplace chat messages as `ALLOW` or `BLOCK`. It looks for messages that share or disguise contact information, share payment details or external links, move communication or transactions off-platform, or otherwise attempt to evade marketplace policy.

The moderation policy is intended to block:

- Phone numbers, including numbers written as words or encoded in sequences
- Plain or obfuscated email addresses
- URLs and bare domains
- Social or messaging contact information
- Payment details and off-platform transaction requests
- Requests to move communication off-platform
- Other prohibited marketplace content

An allowed message can be delivered by the backend. A blocked message should be rejected and handled according to the marketplace's user-notification policy.

## Architecture

```text
User / Vendor
      |
      | WebSocket message
      v
Marketplace Backend
      |
      | HTTP POST /api/v1/validate-message
      v
Guardrail Service
      |
      | ALLOW / BLOCK response
      v
Marketplace Backend
      |                         |
      +-- ALLOW: deliver        +-- BLOCK: reject and notify
```

The guardrail is stateless with respect to marketplace data: it has no database and does not persist users, conversations, or messages. It does keep process-local counters, latency samples, and circuit-breaker state in memory; these reset when a process restarts and are not shared between worker processes.

## Detection Strategy

Moderation runs in two ordered layers.

### 1. Deterministic detectors

These checks run locally and do not call the LLM. The first matching detector returns a block immediately.

| Detector | What it checks |
|---|---|
| `phone` | Indian mobile-number patterns, including common separators and optional `91` country code |
| `number_words` | Runs of English, transliterated Hindi, or Devanagari number words |
| `encoded_digits` | Relational/arithmetic phrasing combined with sequence structure |
| `arithmetic_digits` | Multiple digit-word arithmetic expressions, such as `do plus do` |
| `digit_density` | A structural threshold for scattered or mixed digits |
| `email` | Plain and common obfuscated email formats |
| `payment` | UPI IDs matching supported provider suffixes |
| `url` | HTTP(S), `www`, and bare domains with recognized top-level domains |

Deterministic detections are assigned fixed confidence values by the moderation service. These are rule scores, not calibrated probabilities. The social-contact detector is currently a placeholder; social handles and intent are handled by the LLM layer.

### 2. LLM moderation

If no deterministic check matches, the message is classified by the configured Groq model. The system prompt asks the model to classify semantic intent in English, Hindi, Hinglish, Devanagari, and mixed text, and treats the message as untrusted input. The response is parsed as JSON and validated with a Pydantic model.

The service can make up to `LLM_CONSENSUS_ATTEMPTS` calls:

- A `BLOCK` result returns immediately.
- If attempts return only `ALLOW`, the highest-confidence allow is returned.
- Failed attempts are skipped when another attempt succeeds. If every attempt fails, the error is passed to the service layer, which fails open.

A policy layer converts the validated LLM result into the final action. The LLM does not directly construct the public API response.

## API Contract

### `POST /api/v1/validate-message`

Requires a Bearer token and a JSON body. Messages must contain 1 to 4,000 characters.

Headers:

```http
Authorization: Bearer <GUARDRAIL_API_TOKEN>
Content-Type: application/json
```

Minimum request:

```json
{
  "message": "Let's continue on WhatsApp."
}
```

Optional metadata can be included for backend-side correlation:

```json
{
  "message": "Let's continue on WhatsApp.",
  "message_id": "msg_abc123",
  "conversation_id": "conv_456",
  "sender_id": "user_789",
  "sender_role": "user"
}
```

`sender_role`, when provided, must be `user` or `vendor`. The metadata fields are accepted by the API but are not used by the moderation decision.

Typical error responses:

| Status | Meaning |
|---|---|
| `401` | Missing or invalid Bearer token |
| `422` | Invalid request body or field validation failure |
| `5xx` | Unexpected service or infrastructure error |

LLM failures are normally handled by the service's fail-open path and returned as an `ALLOW` response with HTTP `200`; network and infrastructure failures can still produce a non-`200` response.

## Response Format

Example block response:

```json
{
  "allowed": false,
  "action": "BLOCK",
  "category": "OFF_PLATFORM_COMMUNICATION",
  "confidence": 0.96,
  "source": "llm",
  "request_id": "gr_52b80e854eaa49ac",
  "prompt_version": "marketplace_<hash>"
}
```

Example allow response:

```json
{
  "allowed": true,
  "action": "ALLOW",
  "category": null,
  "confidence": 0.99,
  "source": "llm",
  "request_id": "gr_52b80e854eaa49ac",
  "prompt_version": "marketplace_<hash>"
}
```

The examples use illustrative confidence and identifier values. The response also includes an `X-Request-ID` header matching the `request_id` in the body.

| Field | Meaning |
|---|---|
| `allowed` | Whether the marketplace may deliver the message |
| `action` | Explicit `ALLOW` or `BLOCK` decision |
| `category` | Moderation category, or `null` for an allow |
| `confidence` | Detector score or LLM confidence from `0.0` to `1.0` |
| `source` | `deterministic`, `llm`, or `fail_open` |
| `request_id` | Request correlation ID, prefixed with `gr_` |
| `prompt_version` | Version hash derived from the active system prompt |

Store the decision and correlation fields with the message on the marketplace side if needed for audit, debugging, or analytics. Do not store the raw message in guardrail logs.

## Categories

| Category | Meaning |
|---|---|
| `PHONE_NUMBER` | Phone or contact number, including disguised sequences |
| `EMAIL` | Plain or obfuscated email address |
| `SOCIAL_CONTACT` | Social or messaging handle/contact information |
| `EXTERNAL_URL` | URL or bare domain |
| `PAYMENT_INFORMATION` | Payment information, including supported UPI patterns |
| `OFF_PLATFORM_COMMUNICATION` | Request to move a conversation elsewhere |
| `OFF_PLATFORM_TRANSACTION` | Request to pay or transact outside the platform |
| `OTHER_PROHIBITED_CONTENT` | Other policy violations |

## Getting Started

### Prerequisites

- Python 3.10 or newer
- A Groq API key
- Access to the configured Groq model; the example model is `openai/gpt-oss-120b`

### Install

From the repository root, create and activate a virtual environment, then install the pinned dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Command Prompt, activate with `.venv\Scripts\activate.bat`. On macOS or Linux, use `python -m venv .venv`, `source .venv/bin/activate`, and then the same pip install command.

### Configure

Create a `.env` file in the repository root and set the required values listed below. Generate a random API token, for example:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

The checked-in `.env.example` currently has invalid Python-style syntax for its two circuit-breaker entries. If you copy it, replace those lines with ordinary dotenv assignments:

```dotenv
LLM_CIRCUIT_FAILURE_THRESHOLD=5
LLM_CIRCUIT_OPEN_SECONDS=60
```

Do not commit `.env`; it is excluded by `.gitignore`.

## Environment Variables

The first nine settings below are required by `app/config.py`; the values shown are the sample values in `.env.example`.

| Variable | Example value | Required | Description |
|---|---:|:---:|---|
| `GUARDRAIL_API_TOKEN` | Replace with a secure token | Yes | Bearer token expected from the marketplace backend |
| `GROQ_API_KEY` | Replace with your key | Yes | Credential used for Groq API calls |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Yes | Model name sent to Groq |
| `GROQ_TIMEOUT_SECONDS` | `30` | Yes | Timeout for a Groq request |
| `LLM_TEMPERATURE` | `0.0` | Yes | Generation temperature |
| `LLM_MAX_TOKENS` | `1024` | Yes | Maximum model output tokens |
| `LLM_CONSENSUS_ATTEMPTS` | `2` | Yes | Maximum classification attempts |
| `LLM_CIRCUIT_FAILURE_THRESHOLD` | `5` | Yes | Consecutive failed LLM classifications before opening the circuit |
| `LLM_CIRCUIT_OPEN_SECONDS` | `60` | Yes | Time before the circuit allows a half-open probe |
| `SERVICE_VERSION` | `0.2.0` | No | Version reported by `/health`; code default is `0.2.0` |
| `LOG_LEVEL` | `INFO` | No | Python logging level; code default is `INFO` |
| `LOG_FORMAT` | `json` | No | `json` or `text`; code default is `json` |

Settings are loaded from `.env` in the process working directory. Keep credentials out of source control and restrict access to the environment in which the service runs.

## Running the Service

Development server with automatic reload:

```bash
uvicorn app.main:app --reload --port 8000
```

The interactive API documentation is available at `http://localhost:8000/docs`; OpenAPI JSON is at `http://localhost:8000/openapi.json`.

For a single-VM deployment, bind Uvicorn only to a trusted network interface and place TLS termination in a trusted reverse proxy:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

The counters and circuit breaker are in memory per process. With multiple Uvicorn workers, each worker has independent metrics and circuit state; use one worker for a single coherent in-memory view, or provide external aggregation/state before scaling workers. `/health`, `/metrics`, and the API documentation are unauthenticated, so restrict network access to them.

## Testing

The test suite uses pytest. The local test suite avoids live Groq calls:

```bash
python -m pytest -m "not integration" -v
```

It covers detector behavior, API authentication and responses, observability, circuit-breaker state transitions, and mocked LLM consensus.

Integration tests call the real Groq API and require a valid `.env` configuration and network access. They may consume API quota and take several minutes due to pacing and retries:

```bash
python -m pytest -m integration -v
```

Running `python -m pytest -v` without a marker also includes the integration tests.

Manual smoke test from a shell with `GUARDRAIL_API_TOKEN` set:

```bash
curl -X POST http://localhost:8000/api/v1/validate-message \
  -H "Authorization: Bearer $GUARDRAIL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Call me at 9876543210"}'
```

## Observability

### Request logs

The middleware emits one structured moderation event per validated moderation request. The event includes the request ID, action, category, confidence, decision source, latency, prompt version, and a truncated SHA-256 message hash. It does not include the raw message in that event. Set `LOG_FORMAT=text` for plain-text application logs.

Example fields:

```json
{
  "ts": "2026-09-30T04:38:00.180307+00:00",
  "level": "INFO",
  "logger": "guardrail.request",
  "message": "moderation",
  "request_id": "gr_52b80e854eaa49ac",
  "action": "BLOCK",
  "category": "PHONE_NUMBER",
  "confidence": 0.99,
  "source": "deterministic",
  "latency_ms": 12.4,
  "message_hash": "a1b2c3d4e5f6a7b8",
  "prompt_version": "marketplace_<hash>"
}
```

### Health endpoint

`GET /health` returns service status, process uptime, configured service version, and prompt version. It is a liveness-style response and does not verify Groq availability.

```bash
curl http://localhost:8000/health
```

### Metrics endpoint

`GET /metrics` returns Prometheus text format. Counters and latency samples are process-local and reset on restart; the p95 latency is calculated from the most recent 1,000 observed moderation requests.

```bash
curl http://localhost:8000/metrics
```

Exported metrics include:

- `guardrail_requests_total`
- `guardrail_allows_total`
- `guardrail_blocks_total`
- `guardrail_blocks_by_category{category="..."}`
- `guardrail_sources{source="..."}`
- `guardrail_llm_calls_total`
- `guardrail_llm_failures_total`
- `guardrail_fail_open_total`
- `guardrail_latency_p95_ms`
- `guardrail_circuit_state{state="closed|open|half_open"}`
- `guardrail_circuit_trips_total`
- `guardrail_circuit_rejections_total`

Both `/health` and `/metrics` are unauthenticated. Do not expose them to untrusted networks.

## Resilience

### Consensus

The service requests multiple LLM classifications to reduce sensitivity to a single variable model response. A returned `BLOCK` short-circuits the remaining attempts. If there is no block and at least one attempt returns `ALLOW`, the highest-confidence successful allow is used. If all attempts fail, the classification error is recorded by the circuit breaker and the service layer returns fail-open.

### Circuit breaker

After the configured number of consecutive LLM classification failures, the circuit opens. While open, LLM calls are rejected immediately and the service returns an allow with `source: "fail_open"`. After `LLM_CIRCUIT_OPEN_SECONDS`, one request is allowed as a half-open probe. A successful classification closes the circuit; a failed probe opens it again.

The circuit breaker protects only the LLM layer. Deterministic matches are still evaluated and blocked before the LLM call.

### Fail-open behavior

When the LLM is unavailable and no deterministic detector matches, the service returns:

```json
{
  "allowed": true,
  "action": "ALLOW",
  "category": null,
  "confidence": 0.0,
  "source": "fail_open"
}
```

This is a product decision: an LLM outage does not by itself stop marketplace chat. The marketplace backend should also fail open on a guardrail timeout, network error, or unexpected non-`200` response, and should log that fallback separately.

## Project Layout

```text
guardrail-service/
|-- app/
|   |-- main.py                    # FastAPI app and router registration
|   |-- config.py                  # Pydantic settings loaded from .env
|   |-- api/
|   |   |-- moderation.py          # Authenticated moderation endpoint
|   |   `-- metrics.py              # Health and Prometheus endpoints
|   |-- models/
|   |   `-- moderation.py          # Request, response, and LLM models
|   |-- detectors/
|   |   |-- normalize.py            # Unicode normalization and whitespace
|   |   |-- phone.py                # Phone-number pattern
|   |   |-- email.py                # Plain and obfuscated emails
|   |   |-- url.py                  # URLs and bare domains
|   |   |-- payment.py              # UPI pattern
|   |   |-- social.py               # Reserved placeholder; returns no match
|   |   |-- number_words.py         # English/Hindi number-word runs
|   |   |-- arithmetic_digits.py    # Arithmetic digit encodings
|   |   |-- encoded_digits.py       # Relational digit sequences
|   |   `-- digit_density.py        # Structural digit-density rule
|   |-- llm/
|   |   |-- client.py               # Lazy Groq client
|   |   `-- moderator.py            # Prompt, JSON parsing, consensus, breaker
|   |-- policies/
|   |   `-- policy.py               # LLM classification to final decision
|   |-- services/
|   |   `-- moderation.py           # Normalization and moderation orchestration
|   `-- observability/
|       |-- circuit_breaker.py      # CLOSED / OPEN / HALF_OPEN state machine
|       |-- counters.py             # Thread-safe in-memory metrics
|       |-- logging_setup.py        # JSON and text log formatters
|       `-- middleware.py           # Request IDs, latency, logging, counters
|-- tests/                          # Unit and live-LLM integration tests
|-- .env.example
|-- .gitignore
|-- pytest.ini
|-- requirements.txt
`-- README.md
```

## Marketplace Integration

Call the guardrail from the backend's message handler before delivering the message. Do not call it directly from the frontend.

```python
import os
import requests

GUARDRAIL_URL = os.environ["GUARDRAIL_URL"]
GUARDRAIL_TOKEN = os.environ["GUARDRAIL_API_TOKEN"]


def check_message(message, sender_id, conversation_id):
    try:
        response = requests.post(
            f"{GUARDRAIL_URL}/api/v1/validate-message",
            headers={"Authorization": f"Bearer {GUARDRAIL_TOKEN}"},
            json={
                "message": message,
                "sender_id": sender_id,
                "conversation_id": conversation_id,
            },
            timeout=5,
        )
    except requests.RequestException:
        return {"allowed": True, "source": "fail_open_network"}

    if response.status_code == 200:
        return response.json()
    return {"allowed": True, "source": f"fail_open_{response.status_code}"}
```

The backend should use the decision before delivery, persist the decision metadata alongside the message if required, and notify the sender when a message is blocked. Always set a short timeout and log network or non-`200` fail-open outcomes. A five-second timeout is a suggested integration value, not a timeout enforced by this service.

## Design Decisions

- **Stateless marketplace integration:** persistence and conversation ownership remain in the backend.
- **Synchronous HTTP:** the backend waits for a decision before delivering the message.
- **Fail open on LLM failure:** outages do not block otherwise-unmatched messages by default.
- **Two moderation layers:** deterministic rules handle known patterns; the LLM handles semantic intent.
- **No raw message in moderation event logs:** the middleware logs a truncated hash for correlation.
- **Open operational endpoints:** `/health` and `/metrics` must be restricted at the network boundary.

## Out of Scope

The service currently does not include a database, rate limiting, an admin UI, distributed queues, a webhook workflow, RAG, fine-tuning, a vector database, or a separate language-detection service. Docker and Kubernetes deployment manifests are also not included.

## License

Internal - Swabi.

## Support

For integration questions, contact the guardrail owner. For Groq API issues, see the [Groq documentation](https://console.groq.com/docs).
