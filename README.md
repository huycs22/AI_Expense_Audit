# AI Expense Audit System

A local application that reads a Purchase Order, Invoice, and Payment Request, checks the documents before payment, and lets reviewers trace findings to their sources. Built for the [AI Expense Audit System assignment](Expense_Audit_System_Candidate_Pack/AI_Expense_Audit_System.md) using **FastAPI, PostgreSQL, React/TypeScript, and Cloudflare Workers AI**.

The UI and findings use Vietnamese; code and technical documentation use English. Included documents are synthetic assessment samples, not real transactions.

## Contents

- [Scope and business assumptions](#scope-and-business-assumptions)
- [Quick start](#quick-start)
- [Get Cloudflare credentials](#get-cloudflare-credentials)
- [Use the application](#use-the-application)
- [Architecture and workflow](#architecture-and-workflow)
- [Configuration](#configuration)
- [API](#api)
- [Cost, performance, and retries](#cost-performance-and-retries)
- [Tests and evaluation](#tests-and-evaluation)
- [Troubleshooting](#troubleshooting)
- [Security and submission contents](#security-and-submission-contents)

## Scope and business assumptions

Version 1 processes **exactly three logical documents**, one of each type:

| Document | Audit purpose |
|---|---|
| Purchase Order (PO) | Ordered items, quantities, prices, and terms |
| Invoice | Billed items, totals, tax, and supplier payment information |
| Payment Request | Requested payment, references, beneficiary details, and approvals |

Each accepts a multipage PDF or ordered PNG/JPEG images. A PDF may contain native-text and scanned pages. A **Purchase Request** authorizes procurement and is different from the Payment Request used here; it is outside this version's payment-audit scope.

Document types can be recognized automatically or supplied as manual hints. Cross comparisons require supported reference relationships; upload order or matching supplier names alone do not establish a transaction.

Business checks are LLM-led. Python supplies generic normalization, exact arithmetic, typed contracts, and evidence verification. Production checks do not contain sample IDs, prices, item codes, or an expected issue count.

Business assumptions:

- An explicitly pending approval is a review concern under the [demo policy](backend/app/features/audits/policy.json), not a universal legal payment prohibition.
- Beneficiary/account-holder names do **not** have to match the company name. Differences alone are not anomalies unless an explicit supplied policy requires equality. Account-number comparisons remain separate.
- Missing policy, unclear relationships, and unreadable evidence stay unresolved rather than producing invented rules.
- No findings means only no issues detected in the assessed scope. It never authorizes payment.
- Multiple invoices/POs, allocations, authentication, and production deployment are deferred.

## Quick start

### Prerequisites

- Python **3.11+**.
- Node.js **22+** and npm.
- Docker Desktop running with Linux containers, or an existing PostgreSQL instance.
- Cloudflare Workers AI credentials and access to the configured models.

Commands use PowerShell and start at the repository root. On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

### 1. Clone and install

```powershell
git clone https://github.com/huycs22/AI_Expense_Audit.git
cd AI_Expense_Audit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

The lockfile includes development/test dependencies. Editable installation makes `app` available to the server, migrations, and scripts.

### 2. Configure the private environment file

Follow [Get Cloudflare credentials](#get-cloudflare-credentials), then edit the root `.env`:

```dotenv
CLOUDFLARE_ACCOUNT_ID=YOUR_ACCOUNT_ID
CLOUDFLARE_API_TOKEN=YOUR_WORKERS_AI_TOKEN
DATABASE_URL=postgresql+psycopg://expense:expense_local@127.0.0.1:5432/expense_audit
```

The database values are disposable local-development defaults from `compose.yaml`, not hosted credentials. Use your own `DATABASE_URL` for an existing PostgreSQL server. The backend reads `.env`; Git ignores it. Never put tokens in frontend code or `VITE_*` variables.

### 3. Start PostgreSQL and migrate

```powershell
docker compose up -d postgres
docker compose ps
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

Wait for PostgreSQL to become healthy. Compose starts **only PostgreSQL**; backend/frontend start below. Database data persists in the `expense_pg` Docker volume.

### 4. Start the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use one backend process. The current background-job coordinator does not support multiple Uvicorn workers.

### 5. Start the frontend in another terminal

```powershell
cd frontend
npm ci
npm run dev
```

| Address | Purpose |
|---|---|
| http://127.0.0.1:5173 | Application |
| http://127.0.0.1:8000/docs | API documentation |
| http://127.0.0.1:8000/api/health | Backend/PostgreSQL health |

Vite proxies development API requests to port 8000. `npm run build` creates the frontend production bundle; a production hosting setup is not included. Stop application processes with Ctrl+C. `docker compose stop postgres` stops the database without deleting its volume.

## Get Cloudflare credentials

Follow Cloudflare's official [Workers AI REST API setup guide](https://developers.cloudflare.com/workers-ai/get-started/rest-api/):

1. Sign in to the [Cloudflare dashboard](https://dash.cloudflare.com/) and choose your account.
2. Open **Workers AI**, then **Use REST API**.
3. Select **Create a Workers AI API Token**, review the account scope/permissions, and create it.
4. Copy the token and **Account ID** from the setup screen.
5. Set `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in the root `.env`.

For a custom token, Cloudflare currently specifies **Workers AI Read** and **Workers AI Edit** permissions. Scope it to the intended account. Use that same account's ID, not a Zone ID. The application calls REST directly; no Worker deployment or AI Gateway is needed.

After database setup, this optional small inference probe checks connectivity and records usage:

```powershell
.\.venv\Scripts\python.exe -u -X utf8 backend/scripts/probe_provider.py
```

The probe consumes usage. A valid token does not guarantee model access or available quota. Restart the backend after changing `.env` because settings are cached. Consult the [model catalog](https://developers.cloudflare.com/workers-ai/models/) and [pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) for current access conditions.

## Use the application

1. In **Tải lên**, choose the three PDFs in `Expense_Audit_System_Candidate_Pack/Sample/`. Automatic recognition is the default; manual type hints are available.
2. For images, group pages by logical document in page order. Do not mix PDF and images within one group.
3. Start analysis and follow the persisted status.
4. In **Trích xuất**, inspect observations/item rows beside the selected source. Clicking a citation opens its page; all document pages' facts are intentionally visible together.
5. In **Kiểm tra nội bộ**, select a document, inspect its anomaly count, and choose an individual finding.
6. In **Đối chiếu chứng từ**, choose a cross finding to display all related documents/pages beside its explanation and proof.
7. Review API cost/log and timing stages, then reopen saved results from history without further inference.

The horizontal navigator renders one stage at a time. Filters, selected findings, and scroll positions survive stage switches and reset on page refresh. Failed/interrupted/incomplete or outdated audits can be explicitly retried.

Limits: **20 MB/file, 60 MB/set, 10 pages/document**. Corrupt/encrypted PDFs, invalid decoded file types, and unsupported document sets are rejected or marked incomplete.

## Architecture and workflow

```mermaid
flowchart LR
  A[Upload three documents] --> B[Read text and render pages]
  B --> C[AI extraction and classification]
  C --> D[Ground and review source coverage]
  D --> E[Independent source semantics]
  E --> F[Internal audit per document]
  F --> G[Verify document references]
  G --> H[Cross-document audit]
  H --> I[Verify proofs and business meaning]
  I --> J[Persist report and usage]
  J --> K[Review alongside sources]
```

### Feature-based structure

```text
backend/
  app/core/                 Configuration, database, Cloudflare adapter
  app/features/documents/   Intake, storage, page reading, source routes
  app/features/extraction/  Schemas, normalization, grounding, source review
  app/features/audits/      Orchestration, prompts, policy, calculator, verification
  app/features/usage/       Call ledger, pricing snapshot, local budget
  migrations/               Alembic schema versions
  scripts/                  Connectivity, fixtures, evaluation, database utilities
  tests/                    Unit and PostgreSQL integration checks
frontend/
  src/features/             Upload, extraction, audits, history, cost/timing
  src/shared/               API client, types, labels, stage navigator
  e2e/                      Browser checks
Expense_Audit_System_Candidate_Pack/
  AI_Expense_Audit_System.md Original assignment
  Sample/                   Three unchanged synthetic PDFs
compose.yaml                PostgreSQL development service
.env.example                Placeholder configuration
EVALUATION.md               Dated measurements and unfinished acceptance
WORKFLOW_DESIGN.md          Extended workflow/verification details
```

Features own routes, schemas, services, and persistence where applicable. Shared infrastructure stays in `core`. PostgreSQL stores documents/pages, observations/stage artifacts, findings, and API calls; JSONB accommodates variable layouts and versioned artifacts. Originals/previews live under ignored `data/`.

### Step inputs and outputs

| Step | Input | Method/tools | Output |
|---|---|---|---|
| Intake | Three grouped documents | FastAPI, decoded type/size/page/order validation | Originals and audit/document IDs |
| Read | PDF/image pages | pdfplumber text/coordinates, PDFium rendering, Pillow decoding | Stable page/block evidence and previews |
| Extract | Native evidence/scanned images | Gemma text and visual extraction | Roles, observations, row groups, citations, uncertainties |
| Normalize/review | Observations and originals | Pydantic, conservative dates/Decimal, AI source review | Grounded typed values and coverage results |
| Source semantics | Originals without draft labels | Independent AI actor/term interpretation | Grounded additions/corrections, preserved item groups |
| Internal audit | One document across all pages | LLM check planning, restricted calculator, findings/meaning review | Findings, formulas, assessed topics, unresolved checks |
| Relationships | Document numbers/references | LLM links plus exact citation verification | Supported/conflicting/unresolved links |
| Cross audit | Related documents, internal outputs, policy | Formula calculations, qualitative comparison coverage, meaning review | Cross findings and unresolved checks |
| Save/display | Findings/proofs and sources | Validation, grouping, PostgreSQL, React | Source-linked report, history, cost, timing |

Markdown conversion is unnecessary. Native text retains measured coordinates. Visual transcriptions are labelled and are not independently OCR-verified. Mixed PDFs route using page quality, supplying native evidence alongside image input when needed.

Observations preserve original text, normalized values, citations, and row grouping. Description, quantity, unit, unit price, and amount stay associated with the same item. Repeated occurrences across pages remain available for contradiction checks. Identifier completeness requires grounded evidence on each page containing an identifier; another same-page prose mention need not create a duplicate field.

### Audit logic and prompts

[Extraction prompts](backend/app/features/extraction/prompts/) and [audit prompts](backend/app/features/audits/prompts/) are versioned plain text.

The planner declares left/right formulas over registered observations. Python compiles dependencies and executes allowed arithmetic/date operations using Decimal. Generated Python and invented literal operands never execute. Findings cite declared check IDs; verification attaches terminal comparisons and full source provenance. An unrelated calculation cannot substitute for the claimed proof.

Internal review inspects each document separately across pages. Cross review verifies references, matches rows by code/description, and compares amounts, payment balance, accounts, and supported terms. Another model conversation adjudicates whether formulas/evidence actually support the business claims. Unsupported/uncertain claims stay unresolved. Repeated proofs and related row checks are grouped while internal/cross scopes stay explicit.

Repairs and semantic corrections are bounded. Truncated output is not accepted; regeneration reads original evidence rather than repeating an invalid draft. Embedded instructions are untrusted document content. AI adjudication does not guarantee business truth or complete check coverage.

Processing states (`queued`, `processing`, `completed`, `failed`, `interrupted`) are separate from assessment (`review_required`, `no_issues_detected_in_assessed_scope`, `incomplete_analysis`). Partial findings and successful extractions remain inspectable after failure.

## Configuration

See [.env.example](.env.example); Pydantic Settings reads the root `.env`.

| Variable | Example/default | Purpose |
|---|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Empty placeholder | Inference account |
| `CLOUDFLARE_API_TOKEN` | Empty placeholder | Backend-only token |
| `CLOUDFLARE_MODEL` | `@cf/google/gemma-4-26b-a4b-it` | Native-text extraction |
| `CLOUDFLARE_VISION_MODEL` | `@cf/google/gemma-4-26b-a4b-it` | Visual extraction |
| `CLOUDFLARE_INTERNAL_MODEL` | Same Gemma model | Internal/source reasoning |
| `CLOUDFLARE_CROSS_MODEL` | Same Gemma model | Cross reasoning |
| `DATABASE_URL` | Local PostgreSQL URL | SQLAlchemy/psycopg connection |
| `STORAGE_DIR` | `data` | Originals and derived artifacts |
| `DAILY_NEURON_BUDGET` | Example `10000`; code fallback `8000` | Local daily inference guard |
| `BUDGET_SCOPE` | `application` | Shared application budget; optional `account` scope |
| `MAX_FILE_MB` | `20` | Per-file limit |
| `MAX_DOCUMENT_PAGES` | `10` | Page limit |
| `MAX_COMPLETION_TOKENS` | `7000` | Extraction output bound |
| `AUDIT_COMPLETION_TOKENS` | `12000` | Audit output bound |
| `API_TIMEOUT_SECONDS` | `180` | Provider timeout |

Models are configurable independently. Defaults reflect the implementation's live experiments. Access conditions/model IDs can change; re-evaluate accuracy when changing models.

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/audits` | Multipart upload; returns HTTP 202 and audit ID |
| `GET /api/audits?limit=30&offset=0` | Saved history |
| `GET /api/audits/{id}` | Status, extraction, findings, completeness, usage |
| `GET /api/audits/{id}/documents/{document_id}` | Document and source URLs |
| `GET /api/documents/{document_id}/files/{file_id}` | Original file |
| `GET /api/documents/{document_id}/pages/{number}` | Page preview |
| `GET /api/audits/{id}/stages` | Stage versions/status/timings/errors |
| `POST /api/audits/{id}/retry` | Resume an eligible failed/interrupted/incomplete/outdated audit |

Automatic mode uses `mode=auto` with `document_1`, `document_2`, `document_3`. Manual mode uses `mode=manual` with `purchase_order`, `invoice`, `payment_request`. Repeated multipart fields represent ordered image pages. Do not mix modes. `/docs` exposes the request/response schemas.

## Cost, performance, and retries

Every API attempt persists model, stage, status/retry metadata, latency, reported tokens, pricing version, and estimated cost. Missing usage is unknown. The UI shows **USD and VND**, with an editable illustrative 25,000 VND/USD rate, not live foreign exchange. Billed charges and account-wide quota remaining are unknown.

The [dated rate snapshot](backend/app/features/usage/pricing.json) converts tokens into estimated Neurons and list-price USD. Neurons are used internally for budget accounting; the UI shows currencies. Calls within a free allowance still have estimated list-price value, not necessarily billed cost.

Cloudflare currently documents a 10,000-Neuron daily free allowance resetting at 00:00 UTC (07:00 Vietnam); paid-plan usage above its included allowance can incur charges. Check [current pricing/quota rules](https://developers.cloudflare.com/workers-ai/platform/pricing/). The local budget cannot see other applications' spending. Increasing it does not resolve provider quota exhaustion.

Performance controls:

- At most two concurrent model requests.
- Successful stages reused only for matching input/prompt/model/policy/schema fingerprints.
- One backend process, persisted stage state, orphaned jobs marked interrupted at startup.
- Bounded output/repairs and conservative reservations for failed/unknown-usage attempts.
- Provider quota/access failures stop calls; no paid-model fallback or automatic billing upgrade.
- History reopening and stage navigation use saved results without AI calls.

The optimized normal workload is **23 calls**: nine extraction/source-review calls, nine internal-audit calls, and five cross calls (relationships, numerical planning, focused qualitative planning, shared findings, shared independent meaning review). Repairs remain additional and bounded. The former standalone identity findings/meaning calls are no longer run. Source quotes are sent once through a quote catalog rather than repeated per observation. This optimization remains under evaluation; the latest Gemma run completed but included an unsupported date finding and required extra repairs; unchanged accuracy and a substantial latency reduction are not yet verified. See EVALUATION.md for measurements.

Independent source/meaning reviews add calls and latency. Timing separates elapsed audit time (including waits/retries) from summed API latency, which may overlap. Cached retries are not fresh end-to-end benchmarks.

## Tests and evaluation

Assignment weights: extraction and audit accuracy **20% each**; business understanding and architecture **15% each**; AI integration and maintainability **10% each**; performance and database/documentation/UI **5% each**. Traceable accuracy and honest limitations take priority over feature count.

### Offline and database checks

```powershell
# Backend unit tests, no Cloudflare calls
.\.venv\Scripts\python.exe -m pytest backend/tests -q -m 'not integration'
.\.venv\Scripts\python.exe -m ruff check backend

# Separate PostgreSQL test database, then include integration tests
.\.venv\Scripts\python.exe backend/scripts/test_database.py
.\.venv\Scripts\python.exe -m pytest backend/tests -q

# Frontend components and build
cd frontend
npm test
npm run build
```

Integration tests default to `expense_audit_test`; override `TEST_DATABASE_URL` if needed. They isolate persistence and stub inference; they do not establish model accuracy. Coverage includes arithmetic/date proofs, grounding, schema errors, quota/retry behavior, usage, and PostgreSQL/API history.

### Browser checks

With servers running, from `frontend/`:

```powershell
npx playwright install chromium
npm run test:e2e
```

Most checks use saved reports; absent fixtures can cause documented skips. `E2E_AUDIT_ID` targets an existing audit. Fresh inference upload is opt-in via `LIVE_AI_E2E=1` and consumes usage.

### Actual Cloudflare inference

From the root after database setup:

```powershell
# Provided synthetic PDFs; consumes API usage
.\.venv\Scripts\python.exe -u -X utf8 backend/scripts/evaluate.py --scenario original --auto-classify

# Derived fixture generation and live image/mixed/corrected evaluations
.\.venv\Scripts\python.exe -X utf8 backend/scripts/prepare_fixtures.py
.\.venv\Scripts\python.exe -u -X utf8 backend/scripts/evaluate.py --scenario images --input-dir data/fixtures/images
.\.venv\Scripts\python.exe -u -X utf8 backend/scripts/evaluate.py --scenario mixed --input-dir data/fixtures/mixed
.\.venv\Scripts\python.exe -u -X utf8 backend/scripts/evaluate.py --scenario clean --input-dir data/fixtures/clean
```

Fixture rendering needs a Unicode font; the script uses Windows Arial for Vietnamese. Generated inputs/exports stay in ignored `data/`. `--reuse-audit ID` resumes saved inputs; `--export-only` scores without inference. `--reuse-unchanged-from ID` is an evaluation-only cache helper for byte-identical ordered companion files with matching fingerprints.

Evaluation measures critical-field accuracy, semantic issue matching, evidence validity, tokens, cost, and latency. Synthetic originals contain HDMI arithmetic, Dock quantity, invoice/PO total, requested-payment, bank account, and approval discrepancies. Historical evaluation also expected a name-difference category; this expectation is **not the current policy**. Name differences alone must not count as required anomalies in the current revision.

### Measured results and limits

[EVALUATION.md](EVALUATION.md) records dated live results, retries, failures, cache reuse, and unfinished cases. Successful historical runs used real Cloudflare inference. A Payment Request recovery completed all three documents with no unresolved checks and 22/22 critical values manually present. Its strict field-key score was 21/22 because an account-number key was outside the evaluator allowlist. That retry reused PO/Invoice stages, took 268 seconds, and added estimated $0.01588246; it was not a full fresh-run benchmark.

These measurements precede current policy-grounded name comparisons and per-page identifier completeness. A later audit failed Payment Request review on repeated same-page identifiers; validation was corrected, but live recovery has not been verified. Historical seven-category recall and corrected-case results do not establish current acceptance. Fresh image-only, mixed, corrected, multipage, unreadable, reference-mismatch, and injection evaluations remain incomplete for the latest revision. Three synthetic samples cannot establish general business accuracy.

## Troubleshooting

| Symptom | Action |
|---|---|
| Docker daemon unavailable | Start Docker Desktop/Linux containers or use an existing PostgreSQL server |
| Database connection fails | Check Compose health, port 5432 conflicts, and `DATABASE_URL` |
| Missing tables | Apply Alembic migrations from the root |
| `ModuleNotFoundError: app` | Use virtualenv Python and editable backend install |
| UI cannot reach backend | Check port 8000, `/api/health`, and the Vite proxy |
| Cloudflare 401/403 | Check token permissions/expiry, account scope/ID, and model access |
| HTTP 429 / code 4006 / free allocation exhausted | Check Cloudflare account quota/plan; stop calls and retry when available |
| Local daily budget exhausted | Check local ledger and cap; this differs from provider quota |
| Failed/incomplete audit | Inspect errors/unresolved checks and retry after resolving the cause |
| Outdated report | Explicit retry applies new prompt/schema contracts |
| `.env` change not applied | Restart backend to reload settings |

Keep successful stages and financial accounting when troubleshooting. Clearing history does not restore provider quota.

## Security and submission contents

Included: source, prompts/policy, dependency lockfiles, migrations, Compose, tests/evaluation scripts, documentation, `.env.example`, and unchanged synthetic expense-audit assignment files.

Ignored: private environment files, dependencies, uploaded runtime files, generated fixtures/evaluations, logs, build/browser artifacts, database dumps/key files, and the unrelated import-risk assignment. Operational logs avoid document bodies and credentials; failed-response diagnostics stay private in PostgreSQL.

This is a local assessment application. Public deployment needs authentication/authorization, managed secrets, durable/distributed jobs, deployment-specific database/storage settings, retention controls, and representative evaluation. Findings assist human review; they do not certify fraud, legality, or payment approval.
