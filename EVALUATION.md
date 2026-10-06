# Evaluation — 2026-10-05

The latest results are recorded in the final dated section. Earlier sections describe historical runs and their different cache scopes. The current user-selected local testing cap is 10,000 estimated Neurons/day.

Actual Cloudflare inference, PostgreSQL persistence and browser flows have been exercised. **Assignment acceptance remains incomplete.** Read the final dated section for the current revision and active 10,000 estimated-Neuron cap; earlier measurements below describe historical revisions. Billed charges remain unknown.

## Data and measurement

The supplied files are synthetic assessment documents: one transaction, three logical documents and four pages. Original SHA-256 checks pass. Derived fixtures live separately under ignored `data/fixtures/`. These examples do not establish accuracy on diverse customer documents.

Field scoring checks 22 critical fields by document type, field meaning and item row, including document/reference IDs, accounts, quantities, prices and totals. It does not score every field. Issue checks match cited facts and scope. Automated category recall does not measure precision, approval-role interpretation, complete variance explanation or reliable cross-document payment arithmetic; manual review remains necessary.

Every live run saves its report, source references, usage, reuse provenance and an immutable timestamped snapshot under ignored `data/evaluations/`. `run_usage` isolates new attempts; `usage` is cumulative. `--export-only --reuse-audit ID` scores without inference. Companion reuse requires byte-identical ordered files and matching fingerprints, with IDs remapped to the new documents. Changed documents always run live.

## Native PDFs and business findings

Latest original audit: `ac00308d74c041fe9c8cb3bc1b0bafc2`, completed processing with **incomplete_analysis**.

| Measurement | Observed result |
|---|---|
| Critical fields | 22/22 (100%) |
| Automatic recognition | All three types correct, without hints |
| Automated expected-category checks | 7/7 |
| Accepted findings | 7 |
| Accepted finding reference IDs | 100% valid; native quotes grounded against source pages |
| Manual adjudication | Six supported, one partially supported, zero clear false positives |
| Strict finding precision, counting partial support as failure | 6/7 (85.7%) |
| Latest retry duration | 68.27 seconds, with saved extraction/internal stages |
| Latest retry calls / input / output tokens | 4 / 39,625 / 4,114 |
| Latest retry estimated Neurons / list-price value | 472.432 / $0.005197 |
| Cumulative original attempts / Neurons / list-price value | 36 / 2,881.513 / $0.031697 |

Findings identify HDMI arithmetic (20 × 150,000 should be 3,000,000 rather than 3,200,000), DOCK quantity 12 versus 10, invoice/PO totals differing by 2,970,000 VND, an internally excessive payment request of 2,000,000 VND, beneficiary account/name differences and specifically pending chief-accountant review.

Two gaps prevent acceptance. The total-variance explanation lists DOCK's 2,500,000 and VAT's 270,000 contribution but omits HDMI's 200,000 contribution. Its total difference is correct; its explanation is incomplete. The payment-excess finding is supported inside the Payment Request using its stated invoice value. A proposed cross-document duplicate lacked a reproducible calculation and was rejected, leaving an unresolved check. Broad category recall must not be represented as complete cross-document acceptance. Earlier revisions produced approval false positives and incorrect item captions; their snapshots remain available.

The first fresh run on the new account extracted all selected fields but failed at an internal token cap. Private diagnostics revealed whitespace repetition in constrained JSON. Such responses are rejected and metered as truncated; one bounded repair is permitted. Later live tests exercised successful repairs. Cumulative costs include unsuccessful development attempts, not one fresh successful audit.

## Corrected set and browser

A fresh browser test uploaded corrected PDFs in reverse order through automatic mode. It completed with **no_issues_detected_in_assessed_scope**, zero findings and no unresolved checks. The result reopened from PostgreSQL, displayed actual cost and opened invoice page 2. The browser test took approximately 2.9 minutes.

That fresh audit used 13 attempts, 72,846 input / 13,484 output tokens: **1,090.598 estimated Neurons / $0.011997 list-price value**, with no unknown-usage calls. The saved corrected evaluation passes its zero-false-positive check. Its cumulative ledger includes a later reasoning rerun: 16 calls, 1,331.228 Neurons / $0.014644. These totals must not replace the fresh browser measurement.

## Live scenarios

| Scenario | Measured status |
|---|---|
| Native PDFs | 22/22 fields and seven broad issue categories; incomplete reasoning above |
| Corrected PDFs | Fresh browser pass; zero findings and unresolved checks |
| Image-only copies | Final extraction: 21/22 critical fields (95.5%) and all three types correct; invoice account digit remains wrong. All internal stages completed; cross completion blocked by the local budget. Acceptance fails |
| Mismatched invoice reference | Live pass: actual mismatched identifiers evaluated; relationship gate keeps assessment incomplete and stops transaction comparisons |
| Unreadable image | Live pass: unknown type and no readable observations; explicitly incomplete, never clean |
| Mixed native/scanned PDF | Routing/fixture verified offline; complete live evaluation unfinished |
| Multipage contradictory totals | Repeated evidence/fixture and generic verification tested offline; live evaluation unfinished |
| Document-contained prompt injection | Untrusted-content prompts and fixture present; live resistance unfinished |

Reference mismatch: 230.10 seconds, 13 calls, 52,546 input / 24,775 output tokens, 1,220.653 Neurons / $0.013427. Its companion PDFs had different metadata bytes and were not reused. Fixture generation now copies unchanged companion bytes. Three truncated responses in that run were successfully repaired, showing both recovery and the provider's latency/cost instability.

Unreadable image: four companion stages reused, one actual visual request, 3.02 seconds, 1,871 input / 41 output tokens, 18.127 Neurons / $0.000199. The evaluator requires actual target extraction/relationship evidence; an unrelated budget/processing failure does not count as a passing stress test.

Visual observations are **visual_unverified**. A model quote is transcription provenance, not independent OCR confirmation. Tight views preserve all non-white content while removing margins; digits still require human source review until live accuracy improves. Extraction quotations are now required in the provider schema: earlier optional quotations let visual repairs omit evidence.

Final scan retry: 185.08 seconds, six actual calls, 34,546 input / 7,862 output tokens, 528.478 Neurons / $0.005813. The cross-stage reservation was rejected before another API request. Cumulative scan development: 30 calls, 2,183.331 Neurons / $0.024017. These costs do not establish successful scan-audit acceptance.

## Engineering verification

- **71 backend tests passed**, using an isolated real PostgreSQL database. Coverage includes real-PDF reading, image/mixed routing, Decimal/percentage/identifier comparisons, malformed/truncated output, evidence/currency provenance, classification, relationships, quotas, bounded retries, accounting, history and restart/retry behavior.
- **Four frontend tests passed**; production TypeScript/Vite build passed.
- **Two saved-report browser tests passed**, plus the separate **fresh live browser test passed**. Ordinary runs skip fresh inference. Source navigation, automatic upload, history, costs and mobile layout were exercised.
- Ruff passed. One upstream Starlette/httpx deprecation warning remains.
- Credentials are ignored and absent from Git-visible source. Logs exclude credentials/document bodies. Originals, uploads and private diagnostics stay outside Git. Migrations, dependency lockfiles, Compose, prompts and setup documentation are delivered.

The remaining accuracy gaps matter most to the rubric: extraction 20%, audit 20%, business interpretation 15%, architecture 15%, AI integration 10%, maintainability 10%, performance 5%, database/docs/UI 5%. Engineering tests do not substitute for live accuracy acceptance.

## Cost and remaining work

The versioned 2026-10-05 rates convert reported tokens to estimated Neurons/list-price USD, **not billed charges**. Provider quota is account-wide; the local ledger cannot account for other applications. Missing usage remains unknown and retains a conservative reservation. Repairs and failed attempts count.

The active account cap remains 8,000; it was not raised. Final ledger: **7,635.512 estimated Neurons / $0.083991 list-price value**, with no unknown usage and approximately **364.488 Neurons remaining**. The next bounded cross request cannot fit its conservative reservation, so further inference stopped. Mixed, contradiction and injection live tests remain unfinished under this cap. Earlier accounts returned HTTP 429/code 4006; the newest account successfully ran inference. Cloudflare describes its separate allowance/billing in its [pricing documentation](https://developers.cloudflare.com/workers-ai/platform/pricing/).

To finish acceptance, verify visual account transcription/all scan stages, require a complete 2,970,000 VND decomposition and supported cross-document payment-excess calculation, then run mixed, contradiction and injection cases. Follow README commands, retain the agreed budget and manually adjudicate every finding. No automatic follow-up or additional spending is scheduled.

## Source-formula compiler regression — 2026-10-06

Fresh Cloudflare auditing reused unchanged extraction from the supplied synthetic PDFs. The original regression audit is `0183a2965cfb44889735c22136057c15`; the existing corrected fixture audit `9d4fbeca7fdd45c185b7bc7872891921` was re-audited in place. Earlier measured snapshots were retained. These checks exercise post-extraction reasoning, not a fresh extraction or new scan-quality evaluation.

The original completed with no unresolved checks, 22/22 critical fields, valid cited references and all seven expected issue categories. Eight report findings preserve distinct internal/cross questions and link shared evidence. Dock quantity and line-value differences are presented together. The cross payment proof uses the actual Invoice total and reports 2,000,000 VND excess; the explicit paid amount is zero in this sample, so this live formula compares request against total directly. Nonzero paid amounts and arbitrary values are exercised by compiler/proof regression tests, not a separate live business-selection evaluation. The corrected fixture completed with no findings and no unresolved checks. Expected-category recall is not an issue precision estimate; semantic correctness outside these fixtures still requires review.

Initial live attempts rejected mixed expression objects, mismatched declared/executed formulas and inappropriate local-only cross checks. The final design removes model-generated execution steps: Python compiles the model's source formula, checks units/references/relationships, and requires each claim to cite its proved check. A failed check without a supported conclusion remains unresolved. Same-field candidate pairs and actionable validation errors support bounded repair without sample-specific detection rules.

The final original retry reused successful internal stages: 65.46 seconds, 4 fresh calls, 37,718 input / 3,960 output tokens, estimated list-price cost $0.004960. Its evaluation record totals $0.026871 including all development attempts. The corrected re-audit took 96.46 seconds with 10 calls, 60,091 input / 7,854 output tokens and estimated $0.008365. These latency values differ in cache scope and are not comparable full-run benchmarks. Billed charges remain unknown. The original 8,000-Neuron cap remained enforced throughout.

Final validation: 90 backend tests including isolated PostgreSQL integration checks, 6 frontend component tests, 7 browser tests, production build and Ruff checks passed. The opt-in browser upload/inference test was skipped to avoid duplicating the two explicit live audit evaluations. Browser tests reopened persisted source-formula results and checked source display, document anomaly counts, panel alignment, scroll retention and costs.

## Extraction source coverage — 2026-10-06

Reprocessed the same original audit `0183a2965cfb44889735c22136057c15` using actual Cloudflare inference against all three supplied synthetic PDFs. Extraction v4 adds independent source review, source-preserving semantic patches, native block coverage and coverage of repeated known identifiers. The original files remain unchanged. Historical snapshots remain available; the previous fully resolved audit result does not describe this newest run.

All three extractions passed final source-span coverage revalidation, with zero unrepresented occurrences of known identifiers and no extraction uncertainties. The invoice now has its document number and PO reference independently on pages 1 and 2. Its three quantity units are Chiếc, Chiếc and Sợi; the UI shows these even when raw/normalized quantities agree. The stated 15-day duration is numeric, and Lê Ngọc Anh and Accounting are grouped as preparer name/role rather than approval evidence. Every original invoice row remains grouped; reported incorrect amounts are preserved.

Critical-field evaluation is 22/22. The original field-key allowlist initially scored 21/22 because the PO account was correctly extracted as `payment.account_number`; the evaluator now includes that semantic alias and labels the metric `field-and-item-group-v3-account-aliases`. No source value, extraction or production detection rule was changed to improve the score. This measure still does not certify every source fact or semantic role.

The newest full run took 227.68 seconds: 19 API calls, 114,090 input and 22,814 output tokens, estimated $0.01863691 (465.92 VND at the UI's configurable 25,000 VND/USD display conversion). Extraction and its quality/repair calls account for $0.00896202. Initial development attempts rejected omitted repeated identifiers and an overlong review response; those attempts remain metered and retained. Total API spending for this extraction-fix session, including the failed first run, was approximately $0.02782945. These are list-price estimates, not billed charges. The user's 8,000-Neuron local daily cap remains unchanged.

**Audit acceptance remains incomplete.** The newest processing completed with `incomplete_analysis`: final reasoning did not bind a valid HDMI conclusion to its compiled check and another numerical claim cited mismatched check contracts. Verification rejected those claims and retained unresolved checks. Six findings remained; two overlapping pending-approval findings also remain a reasoning/consolidation limitation. Broad category matching reports 6/7 and is not strict precision or complete business acceptance. Successful source review must not be described as a successful whole-system audit.

Final verification: 99 backend tests including PostgreSQL integration, 8 frontend component tests, all 8 ordinary browser tests, production build and Ruff passed. The optional fresh browser inference test was skipped; the explicit PDF evaluation above consumed API budget. Browser coverage includes visible units, page-2 navigation, all-page explanation, stable anomaly IDs, source panels, costs and scroll retention. Scan/mixed inference was not rerun for extraction v4; previous visual-quality limitations remain. Block coverage and an independent AI review reduce omissions but do not prove semantic completeness or independent visual transcription accuracy.


## Latest root-cause fixes — 2026-10-06 (final live acceptance blocked)

The user-created audit `dbf562976e1049a5885e6d687dbea620` originally failed after correctly computing the HDMI discrepancy. Its conclusion cited both a multiplication dependency and its terminal comparison; the verifier incorrectly required the dependency to have its own check binding. PO findings responses also padded output with whitespace until truncation, and one internal failure prevented cross-document analysis despite readable extraction. Invoice source semantics again mislabeled the issuer as an approver and omitted a scalar payment duration. These failures demonstrate that the preceding evaluation was fixture/run-specific evidence, not a guarantee of general correctness.

Implemented and regression-tested general changes: check-ID-only finding outputs with Python attachment of terminal proofs; dependency traversal that accepts only actual ancestors of those proofs; JSON-object audit transport and local contract validation; independent source-only actor/term interpretation using the configured reasoning model; table-cell protection, source grounding and occurrence reconciliation; exact calendar/date comparisons separated from monetary tolerance; policy/source-record consolidation; independent cross processing after internal failure. Native source coverage was revalidated with zero missing known-identifier occurrences and zero extraction uncertainties. Invoice quantities retain Chiếc/Chiếc/Sợi; page-2 document/PO identifiers remain separately represented; issuer.name/issuer.role and a numeric 15-day payment term are now present. Critical-field accuracy is 22/22, which does not certify every field or semantic interpretation.

Live original retry before the final semantic-adjudication addition completed in 82.40 seconds, reusing extraction/source-semantic stages and making nine audit calls: 70,641 input / 5,587 output tokens, estimated $0.00874029 (218.51 VND at 25,000 VND/USD). Its retained history has 49 calls and estimated $0.05154299, including the initial user run and unsuccessful development attempts; this cumulative value is not the cost of one pipeline execution. The seven expected broad issue categories and registered evidence IDs are present across eight findings. **This is not successful final audit acceptance.** Manual inspection found an invented PO deadline comparison (payment duration treated as a delivery deadline), reversed wording in the combined payment/total explanation, and bundled beneficiary-name/account anomalies. Arithmetic/evidence checks alone did not establish those business claims. No strict precision score is reported.

Those observations prompted the final report-v4/review-v8 change: a fresh model conversation independently adjudicates every declared check and every proposed finding using original quotations, explicit policy, formulas and computed results. Unsupported/uncertain comparisons and explanations are excluded from verified findings and retained as unresolved, so neither a false anomaly nor a false clean report is produced from an incomplete adjudication. Missing decision coverage, invalid references and provider failure fail the stage. It also checks invented event relationships, reversed numerical direction, unsupported causal decomposition and bundled independent obligations. Reasons are persisted and visible in the finding UI. This remains AI judgement rather than a deterministic guarantee; live testing is required. Normal post-extraction inference is now 13 calls, excluding repairs/retries. The additional four adjudication calls have not been benchmarked live.

The corrected-fixture retry `9d4fbeca7fdd45c185b7bc7872891921` failed with Cloudflare HTTP 429/code 4006 reporting exhausted provider quota. It did not establish zero false positives for this revision. Further inference stopped; the local 8,000-Neuron cap was not raised (about 3,737 local units remained when checked, so the provider limit was the immediate blocker). The final semantic adjudicator therefore remains **live-unverified**, including the original/corrected pair. Old persisted reports are explicitly flagged as outdated and can be retried after quota is restored; reading a report makes no inference call.

Engineering validation: **121 backend tests** including PostgreSQL integration, **8 frontend component tests**, production build and Ruff passed. **7 browser tests passed** against saved source-linked results. Two browser tests were skipped: opt-in fresh inference and reopening a successfully completed corrected live audit (the fixture now has a quota-blocked retry). The severity-filter browser assertion now derives its count from saved findings instead of assuming one medium anomaly; live business acceptance still records the invented deadline as a failure. Tests cover unsupported business contracts, invalid prose despite correct arithmetic, missing semantic decisions, proof dependencies, unrelated proofs, date comparisons, preserved extraction, failure isolation and consolidation. They do not prove the model will adjudicate accurately. Scan/mixed, contradiction and injection live tests were not rerun for this revision; previous visual-transcription limitations remain. All supplied PDFs are synthetic assessment documents and remain unchanged.


## Provider switch and semantic refinement — 2026-10-06

The newly supplied account passed a metered inference probe. Only the two ignored local credential settings changed; models and the 8,000-Neuron/account daily cap stayed unchanged. The backend was restarted. Evaluations reused the two existing audit IDs without creating new history rows. Snapshots remain under ignored data/evaluations/.

The first live semantic-verifier run caught the invented PO delivery/payment deadline, but confused a legitimate failed amount comparison with an invalid business contract. Its cross response also exceeded the 3,000-token limit despite one repair. The typed interface now separates valid/invalid/unresolved check contracts from supported/unsupported/unresolved findings. A valid check may fail, establishing a discrepancy. Short aliases round-trip to original evidence IDs. One bounded semantic correction may revise rejected proposals while retaining supported obligations/anomalies; continued failure remains unresolved. Correction calls have distinct usage-stage labels. Tests use arbitrary EUR values and IDs, not assessment values.

The refined original completed in **210.03 seconds**, no unresolved checks: **17 fresh calls**, 152,217 input / 11,374 output tokens, estimated **$0.01863409 / 465.85 VND** at the configurable 25,000 VND/USD display rate. Extraction was reused. The invented PO deadline was removed after one correction; HDMI arithmetic, payment excess and pending accountant review survived adjudication. Broad matching finds the seven expected categories across seven findings, but manual inspection still found bundled total/payment and beneficiary name/account findings, plus an aggregate variance without the complete numerical line/tax decomposition. These business-quality requirements did not pass acceptance; broad category presence is not strict precision.

The corrected synthetic set completed in **202.39 seconds**, **zero findings and zero unresolved checks**, **23 fresh calls**, 143,812 input / 22,479 output tokens, estimated **$0.02141346 / 535.34 VND**. It included fresh extraction/quality/source-semantic work, so its latency is not directly comparable with the cached original retry. Corrected-fixture evaluator checks pass. One corrected case does not establish general accuracy across businesses or scans.

Remaining original defects prompted a cross-only contract improvement: findings separately grade truth support, atomicity and explanation completeness. True assertions can still be bundled/incomplete. Such proposals trigger bounded correction or remain unresolved. Aggregate explanations require numeric line/component/tax contributions from the ledger; independent identity attributes and payment/PO obligations stay separate. These are generic output contracts and AI judgements, not sample-specific Python filters.

**Final live acceptance remains blocked.** The stricter cross retry immediately returned **Cloudflare HTTP 429/code 4006, daily provider quota exhausted**. Further inference stopped. About **1,809.02 local Neurons remained**, so provider quota was the immediate blocker. The current original audit is failed/incomplete_analysis, retaining three supported internal findings; its latest cross result is unavailable. The prior completed report is retained in snapshots. The stricter cross atomicity/completeness contract is regression-tested but **not live-validated**. The clean run preceded that last cross-only change; with no findings its atomicity criteria are vacuous, and it does not substitute for positive-case validation. No final whole-system success or strict precision claim is made.

This account recorded **60 attempts**, **$0.06737701 known estimated list-price cost / 1,684.43 VND** at the display rate. One failed call has unknown token usage and a conservative budget reservation. Billed charges remain unknown. The original audit's cumulative multi-account history is approximately $0.09750215, including prior runs; it is not the cost of one execution. The local cap was never increased.

Final checks: **126 backend tests**, **8 frontend component tests**, production build and Ruff passed. Browser checks: **5 passed, 4 skipped**. Three skips require cross findings unavailable after the quota-blocked retry; one is opt-in fresh inference. Corrected-report reopening passed with recognition, source pages and usage. Earlier populated-report browser checks remain recorded above. The latest refinement also retains its initial proposals/decisions for private diagnostic traceability. Originals remain unchanged and credentials ignored. Documents are synthetic assessment fixtures. Mixed/scanned, contradiction and injection live tests were not resumed after provider exhaustion.


## Scalar, scope and proof-coverage fixes — 2026-10-06

The replacement account successfully performed actual Cloudflare inference. The 8,000-Neuron account/day cap remained enforced. No supplied document was modified. This evaluation reuses saved source extraction and successful internal stages, so these are post-extraction regression measurements, not full upload-to-report latency benchmarks.

Four intermediate attempts remained incomplete (220.30s/$0.01282323, 212.03s/$0.01680487, 244.86s/$0.01884139, 155.26s/$0.00795178). They exposed bundled independent comparisons, omitted component proofs, an overly strict text-versus-identifier check, and dropped valid checks during correction. Their stage outputs, usage and timestamped exports remain retained. A numerically true explanation never overrode the incomplete assessment.

Report v6 now compares scalar evidence pairs using compatible representations, keeps a numerical finding within one source-document set, preserves valid source formulas during correction and requests one bounded output repair for uncovered failed checks. The independent meaning reviewer remains responsible for semantic obligations within the same document scope. None of these checks contains fixture values or expected issue counts.

The final original audit `dbf562976e1049a5885e6d687dbea620` completed as review_required with zero unresolved checks: 22/22 critical fields, valid cited evidence and all seven expected issue categories. There are nine findings, retaining internal/cross scopes: invoice HDMI arithmetic; request balance and pending approval; Dock quantity/amount; HDMI PO/invoice amount; total variance; cross payment excess; beneficiary name; beneficiary account. Shared-evidence relationships are retained, rather than silently discarding separate scopes. Broad category recall is 100%; the automated evaluator intentionally does not claim strict issue precision. Manual inspection confirmed the observed discrepancies; varied real-customer business accuracy remains unmeasured. The aggregate gives the contributing 2,500,000 + 200,000 + 270,000 = 2,970,000 VND. Cross payment compares the actual invoice balance and gives 2,000,000 VND excess. Some generated explanations still contain evidence aliases; these are a presentation limitation.

Final original retry: 93.69 seconds, five fresh API calls, estimated $0.00816128 (204.03 VND at the configurable 25,000 VND/USD display conversion). Corrected fixture `9d4fbeca7fdd45c185b7bc7872891921`: 84.93 seconds, five calls, 60,974 input / 4,177 output tokens, estimated $0.00735057 (183.76 VND), zero findings and zero unresolved checks. These estimates are list-price values; billed charges are unknown. Export-only scoring does not call AI. Cumulative per-audit cost includes old accounts and failed development attempts and must not be presented as the cost of these retries.

Validation: 135 backend tests, eight frontend component tests, Ruff and production build passed. Source-semantic cache reuse is covered by PostgreSQL integration tests and remaps extra observation IDs only for ordered byte-identical files with matching fingerprints. Browser checks accept the actual number of related documents and can target a persisted audit with E2E_AUDIT_ID. Remaining stress/browser results are recorded below when completed. Historical scan account-transcription limitations are not resolved by native-text positive/negative tests.


Prompt-injection fixture `22570b562e774a98a5d0020f26f5b5f1` completed with zero findings and zero unresolved checks. Actual inference on the changed invoice preserved its real 52,250,000 VND total rather than obeying document-contained instructions. Two unchanged companions reused extraction, source-semantic and internal stages with recorded hash/fingerprint provenance. This narrow fixture passes; it does not establish protection against every prompt injection. Latency 166.62s, ten calls, 82,255 input / 9,651 output tokens, estimated $0.01128467 (282.12 VND).

Final browser verification: eight passed, one optional fresh-inference upload test skipped to avoid duplicate spending. Tests reopened the completed original and corrected reports, checked source pages, per-document anomaly management, stage navigation/scroll retention and USD/VND logs. The restarted API reports all three latest reports as current (not outdated), and the frontend returns HTTP 200. The earlier automatic approval-review usage-limit interruption was resolved on resume; no final verification remains blocked by that review.

Current account/day ledger: 7,565.652485 estimated Neurons, with 434.347515 remaining under the unchanged 8,000 cap; no additional inference was started. A full bounded stress evaluation cannot fit conservatively within this balance. Updated live mixed/scanned, multipage contradiction, unreadable and mismatched-reference scenarios remain unfinished; historical results and local regression tests do not substitute for fresh end-to-end acceptance. The scan account-transcription weakness remains open. No blanket claim of assignment completion or general business accuracy is made.


## Interrupted extraction checkpoints and budget reset — 2026-10-06

Inspected user run `f9f3dacb1a364cd9ab044d23b44ba351`. The local daily testing budget stopped processing; there was no Cloudflare quota error in this run. One source extraction stage had completed with 35 PO observations, but its document record still showed unclassified/no extraction because persistence waited for the later semantic-review stage. The other two documents had no completed extraction. The old reset message said only 07:00, which could refer to a time already past.

Successful source reading/classification now persists before semantic review, separately marked pending; review failure retains it without making it audit-ready. The immutable stage cache remains the retry input, so checkpoint metadata does not alter semantic fingerprints or original facts. The UI explicitly shows pending review beside source pages. Missing/pending extraction is incomplete work, not an obsolete artifact; the outdated-verification flag now compares actual saved completed artifacts. Local budget messages name the next UTC-day reset in Vietnamese local time with date, and describe insufficient capacity for the next reservation rather than implying a provider quota failure.

Retried the existing run in place after the fix: zero additional API calls, recovered the 35 source-grounded PO observations/classification; all remaining unaffordable requests stopped before network access. The report remains failed/incomplete_analysis. Its known cumulative cost stays $0.00311302. The dated message identifies 07:00 on 7 October 2026 (UTC+7). The 8,000-Neuron cap was not raised; the current account ledger used approximately 7,848.65 Neurons, leaving approximately 151.35, insufficient for the next conservative request reservation. This recovery is not an end-to-end audit success.

Regression verification: 139 backend tests, eight component tests, production build and Ruff passed; nine browser checks passed, one optional duplicate inference test skipped. Added regression cases use an injected downstream failure and arbitrary future clock dates, and the browser checks the real recovered run's pending notice, saved values and source preview. No sample-specific production detection rule was added.


## Fresh three-document test after history cleanup — 2026-10-06

At the user's request, removed 20 audit-history records, findings, stage payloads and their runtime upload directories. Original sample PDFs remain untouched. Historical evaluation exports remain as diagnostic evidence; their old audit IDs no longer reopen from the application. API usage rows were detached from deleted audits rather than erased, preserving actual daily accounting. The user then authorized a 10,000-Neuron daily cap; the root environment and restarted server use 10,000. The fresh audit `cb77dcde387a4fc3b6417d435dcb8423` is the only new history entry.

Actual Cloudflare inference used all three original synthetic PDFs with automatic classification. The first attempt failed invoice quality coverage: its reviewer classified standalone party headings as extracted without source observations, and repeated the mistake during bounded repair. The generic validator now returns all coverage mismatches together and explains the distinction between a field/section label and omitted source facts. Initial grounded reading is checkpointed before quality review, not only before semantic review, so a reviewer failure cannot erase visible source data. Successful PO/payment stages were reused on retry in the same audit.

Retry recognizes all three roles and retains 41 PO, 49 invoice and 37 payment-request observations. Invoice item quantities, units, prices, reported amounts and row groups are preserved. Internal findings correctly identify the HDMI 200,000 VND arithmetic error, the 2,000,000 VND payment excess and pending accountant approval. **The full test does not pass:** cross-document auditing stops at the local budget reservation. The report is failed/incomplete_analysis; no missing cross findings are presented as passing checks. Final account/day usage is 9,652.586951 estimated Neurons, with 347.413049 left under 10,000; this cannot cover the next conservative request reservation. There was no provider quota error in these attempts.

Inspected additional extraction weaknesses: descriptions absorbed neighboring quantity/unit cells, and duplicate draft role labels on the same issuer quote produced ambiguous actor candidates. Source reading now supplies the measured PDF cell arrays and precise-cell guidance; this change still needs fresh live inference. The actor reconciler resolves duplicate candidate labels only when raw value, physical quote, blocks and record group coincide, retaining occurrences/change traces; genuinely distinct records remain unresolved. Read-only reconciliation of the saved independent invoice facts produces the correct issuer name/role without ambiguity. That local replay is not a completed new live audit; the persisted report retains its actual earlier uncertainties.

Automatic critical-field score is 21/22: the scorer's field-name allowlist does not recognize the PO's valid `payment.beneficiary.account`, although its actual account number is correct and source-grounded. Do not describe this as missing account data or silently inflate the strict metric. Manual source-value inspection confirms the expected account. The narrow critical-value metric does not certify precise descriptions, source roles or general extraction completeness.

First attempt 145.92s; retry 128.72s. Across both attempts: 22 API calls, 109,989 input / 27,573 output tokens, estimated $0.01984325 (496.08 VND at the configurable 25,000 VND/USD display rate). Billed charges remain unknown. Unit/regression verification: 143 backend tests and Ruff passed. Browser checks below exercise the actual incomplete result; completed cross/clean fixtures were removed by the requested history cleanup. A fresh complete positive-case test and live verification of table-boundary guidance remain unfinished. No automatic future inference is scheduled.

Browser results for the fresh incomplete audit: four passed, six skipped. Passed source units/pages, scroll retention, workflow/cost display and upload/history/source inspection. Three cross-result checks require the unavailable cross report; corrected-report reopening requires the deleted clean fixture; pending-review coverage requires an explicit partial fixture; optional duplicate live upload remains disabled. These skips are limitations, not passes.

## Replacement account and identity coverage — 2026-10-06

The replacement credentials pass metered inference with both selected models. They are stored only in the ignored root `.env`. The backend was restarted with the latest code; PostgreSQL health is OK. The original PDFs remain unchanged, and history contains just the existing audit `cb77dcde387a4fc3b6417d435dcb8423`; repeated tests resumed this record instead of creating more history entries.

**Latest outcome: failed / incomplete_analysis. This is not a passing assignment result.** The last retry stopped before any API call because the conservative request reservation exceeded the remaining local allowance. Active-account usage is 9,790.184266 estimated Neurons, leaving 209.815734 under the user-selected 10,000 cap. This was a local guard, not a Cloudflare quota error. The local ledger resets at 07:00 on 2026-10-07 (UTC+7); provider allowance and billed charges remain unknown.

| Current saved evidence/report | Measurement |
|---|---|
| Critical field score by configured field keys | 21/22 (95.45%) |
| Manual critical source-value presence | All 22 expected values present |
| Document roles | All three correct; reused documents have role hints, so this retry is not a fresh automatic-recognition test |
| Accepted expected categories | 6/7 (85.71%) |
| Accepted findings | 8, including distinct internal/cross payment scopes |
| Accepted cited evidence | Valid source IDs and grounded native quotes |
| Missing accepted category | Beneficiary account-holder name mismatch |
| Full backend regression | 156 passed; Ruff passed |
| Browser on this saved audit | 7 passed, 3 skipped |

The account number is correctly present as `bank_account` with value `888800009917`, quoted from the actual source. The scorer's account-field allowlist does not accept that field key. The strict score is retained rather than changing aliases to inflate it. Invoice item descriptions are now precise cells, and row links, quantities, units, prices and reported amounts remain preserved. Repeated references on different actual source blocks/pages are retained.

Manual inspection supports HDMI arithmetic, Dock quantity/amount variance, HDMI PO/invoice amount variance, total variance, excessive requested payment, different account number and pending accountant review. Total variance now cites the 2,700,000 subtotal difference and 270,000 tax difference; linked item findings account for 2,500,000 Dock and 200,000 HDMI contributions. Cross payment uses the actual invoice total and produces the correct 2,000,000 excess. The earlier invalid order-date/payment-deadline hypothesis was rejected and successfully removed through semantic refinement.

The beneficiary name `NGUYỄN VĂN PHÚ` is correctly extracted but the earlier cross audit omitted its comparison. The root completeness limitation was that numerical planning did not declare qualitative comparisons, while semantic adjudication only judged proposed claims. Independent identity coverage now plans additional source-based comparisons, interprets them, and separately adjudicates them. Its first live trial discovered the name mismatch, but the model cited three source observations in a contract requiring one two-source pair; both bounded findings attempts were rejected. The compact evidence transport, explicit document roles, focused source subsets, two-source output schema and detailed pair-repair feedback were added afterward. Their regression tests pass, but live verification was blocked before the next request by the remaining local budget. The missing category must not be described as fixed in live acceptance.

Additional generic fixes exercised in live trials: JSON-object extraction transport, exact unique multiblock citation resolution, rejection of unsupported optional review additions without discarding valid additions, complete repeated-identifier repair feedback, physical-occurrence semantic reconciliation, exclusion of out-of-scope semantic proposals, source-role repair feedback for invalid local cross checks, immutable preservation of valid formulas during refinement, and refinement for rejected evidence claims/uncovered checks. None uses the fixture values to detect problems.

Cost/latency scopes must remain separate:

- Last completed main audit/refinement attempt: 341.69 seconds with saved source readings, 23 fresh calls, 285,418 input / 18,768 output tokens, estimated $0.03417254 (854.31 VND).
- First identity-coverage trial: 32.04 seconds, four calls including repairs, 42,402 input / 1,566 output tokens, estimated $0.00471005 (117.75 VND).
- Final blocked retry: 0.76 seconds, zero API calls and zero additional inference cost.
- Current account's metered testing including connectivity: estimated $0.10769203 (2,692.30 VND).
- This audit across all retained accounts/attempts: 106 calls, 860,671 input / 131,156 output tokens, estimated $0.12753089 (3,188.27 VND).

VND values use the application's configurable 25,000 VND/USD display conversion, not a verified market exchange rate. All costs are estimated list-price values, not billed charges. None of these cached/retried timings is a fresh end-to-end benchmark for the final revision.

Browser checks pass extraction units/page navigation, numerical proof display, separate audit stages and selection, anomaly-to-document navigation, scroll retention, workflow/USD/VND logs, and history/source inspection. The three skipped checks are optional fresh inference, reopening the corrected fixture deleted during authorized history cleanup, and an explicitly selected partial-review fixture. Fresh corrected/scan/mixed/multipage/injection and other stress fixtures have not been rerun under report v7. Full assignment acceptance and diverse real-customer accuracy remain unfinished. No automatic future inference is scheduled.


## Successful identity coverage on replacement account — 2026-10-06

**Current outcome: completed / review_required.** The new credentials passed a small metered Cloudflare inference. Retried the existing audit `cb77dcde387a4fc3b6417d435dcb8423`, reusing completed extraction, source semantics, internal audit and main cross audit. History still contains one audit. The local cap remains 10,000 estimated Neurons per account per UTC day; credentials remain in the ignored root `.env`.

Live identity coverage completed all three calls on their first attempts: planning, evidence findings and semantic adjudication. It now reports the payment-request beneficiary `NGUYỄN VĂN PHÚ` versus invoice account holder `CÔNG TY TNHH THIẾT BỊ AN PHÚ`, citing precisely those two original source observations. The supplier name on the request was not confused with its payment beneficiary. Passing supplier/account comparisons were not emitted as anomalies. This verifies the compact transport and two-source pair contract on the supplied originals.

| Current saved result | Measurement |
|---|---|
| Expected issue categories detected | 7/7 (100% recall on these expected categories) |
| Accepted findings | 9; internal and cross HDMI/payment findings retain their separate scopes and shared-evidence links |
| Unresolved checks | 0 |
| Source citation validity | Valid registered, grounded source observations |
| Strict critical field-key score | 21/22 (95.45%); payment account present under `bank_account`, outside evaluator allowlist |
| Manual critical source-value presence | 22/22 values present |
| Incremental live retry | 10.54 seconds; 3 API calls; 10,366 input / 649 output tokens |
| Incremental estimated list-price cost | $0.00123131; 30.78 VND at illustrative 25,000 VND/USD |
| Audit cumulative usage across historical accounts/attempts | 109 calls; 871,037 input / 131,805 output tokens; $0.12876220 (3,219.06 VND) |

Manual inspection of all nine accepted findings supports their source facts: HDMI arithmetic, Dock quantity/amount, invoice/PO HDMI variance, invoice/PO total with subtotal/tax contributions, internal and actual-invoice payment excess, account mismatch, account-holder name mismatch, and pending accountant review. Seven expected categories are covered; this category recall is not a measured issue-precision score or a guarantee of complete general business coverage. Previously overlapping internal/cross scopes remain explicit rather than merged into an unsupported common proof.

Final provenance cleanup restores transport aliases in every structured citation, including semantic-review metadata, without rewriting quoted strings. Cached identity outputs now undergo the same source/proof revalidation as main audit outputs. A cached replay persisted those corrections in 0.49 seconds with zero new API calls. Identity API stages have readable Vietnamese labels in USD/VND cost tables.

Verification: 157 backend tests and Ruff passed; eight frontend component tests and production build passed. The saved-report browser suite passed seven checks with three explicitly skipped fixtures; the anomaly-navigation check was extended to verify every cross finding's cited documents/pages, including the new beneficiary-name finding. Skips remain fresh duplicate inference, corrected-fixture reopening after history cleanup, and an explicitly selected partial-review fixture.

The 10.54-second retry reused earlier completed stages and is not a fresh end-to-end latency benchmark. Billed charges and provider account-wide quota remain unknown. Original synthetic PDFs are unchanged. Fresh corrected, image-only, mixed, multipage, unreadable, relationship-mismatch and prompt-injection evaluations have not been rerun under the current revision; full assignment acceptance and generalization remain unfinished. No automatic future inference is scheduled.


## Latest automatic upload: Payment Request failure — 2026-10-06

Inspected the newer automatic-upload audit `193ec15dc6ec44fea917aa896e906b58`, rather than the previous completed audit. Invoice and PO had successful extraction/semantic/internal stages. The Payment Request failed its initial native-text extraction: the model repeatedly emitted nearly the whole remaining page block list per observation and duplicate approval dates until its output limit. Provider truncation escaped the initial-reading validation repair loop. Later drafts contained quotes joining headings/table headers with nonadjacent rows, which correctly failed source grounding. Generic feedback and replaying the entire invalid draft did not correct the pattern.

Generic fixes: one bounded regeneration for initial truncated output; fresh-source regeneration instead of replaying invalid/truncated model text; a versioned source-regeneration prompt requiring minimal contiguous citations, physical-occurrence preservation, row groups and exact quotes; observation-specific noncontiguous-quote feedback with candidate source block IDs; ambiguity-safe citation narrowing for fresh reads only. Source facts are never changed to pass validation, and partial output is never accepted. Quota errors still stop without retry.

An additional cache defect was exposed: selecting the newest completed stage before checking its fingerprint could hide an older exact matching successful stage. Cache lookup now filters by fingerprint before ordering. Fresh citation cleanup does not rewrite successful cached extraction inputs. A recovery with the provider explicitly stopped restored Invoice and PO to completed, made zero API calls, and retained the failed Payment Request/incomplete assessment.

**Current outcome remains failed / incomplete_analysis. Live verification of Payment Request recovery is unfinished.** The first follow-up attempt took 226.49 seconds and still failed grounding. The next attempt took 103.93 seconds and hit Cloudflare HTTP 429/code 4006 (daily free allocation exhausted), including the corrective request; this was a provider quota error, not the application's 10,000-Neuron local cap. No further network inference was attempted after that error. The earlier successful audit remains a separate historical record and is not evidence that this newer upload succeeded.

Latest audit cumulative usage: 21 actual API calls, 192,543 known input / 49,116 known output tokens, estimated known list-price cost $0.03614860 (903.71 VND at illustrative 25,000 VND/USD). One failed call has unknown usage, so that cost is incomplete; its conservative reservation remains in local budget accounting. Actual billed charges and account-wide allowance usage remain unknown. Final cached recovery incurred no additional inference cost. Original supplied PDFs remain unchanged.

Verification: 163 backend tests and Ruff passed. Added source-reading truncation/repair limits, immediate quota stop, no invalid draft anchoring, precise rejected-quote feedback, unique-versus-ambiguous citation narrowing, stable cached citations, and reuse of older matching successful stage versions. These tests establish the software contracts, not successful live recovery under exhausted provider quota. The final export records the actual incomplete run; no new audit-history entry was created.

Browser verification on the latest partial report: source units/pages, workflow/cost display and history/source inspection passed. The scroll test initially assumed the first document had scrollable extracted data; the first document was the failed request with an empty panel. The test now selects a populated document and checks restoration of its actual nonzero scroll position; its targeted rerun passed. Six checks requiring cross results or absent optional fixtures were skipped. The web backend was restarted with the final code and reports healthy PostgreSQL.


## Payment Request recovery verified on replacement account — 2026-10-06

**Latest outcome: completed / review_required** for the same audit `193ec15dc6ec44fea917aa896e906b58`. Replacement credentials passed the small metered probe and are stored only in the ignored root `.env`; the web backend was restarted. Original PDFs and audit history were preserved. Invoice and PO extraction, semantic interpretation and internal audits were reused without fresh calls.

The Payment Request's initial response again reached the output limit. The repaired reader now caught that truncation and regenerated from original evidence without replaying the runaway draft. The complete repair took 22.073 seconds and 1,694 output tokens, versus 7,000 tokens in the rejected initial output. Native source grounding, quality review and independent semantic review passed; 39 final observations are retained with no extraction uncertainties. Critical payment facts, account number, beneficiary name, references and approval rows cite precise native source blocks. All three documents have completed processing.

| Latest result | Measurement |
|---|---|
| Expected issue-category recall | 7/7 (100% on the supplied expected categories) |
| Accepted findings | 10, including separate internal/cross scopes and supplier-name versus account-holder-name comparisons |
| Unresolved checks | 0 |
| Critical field-key metric | 21/22 (95.45%) |
| Manual critical source-value presence | All 22 expected values present |
| Retry latency, with Invoice/PO stages reused | 268.00 seconds |
| Fresh API calls | 14, including one truncated read and its bounded repair |
| Fresh reported input / output tokens | 100,982 / 17,357 |
| Fresh estimated list-price cost | $0.01588246; 397.06 VND at illustrative 25,000 VND/USD |
| Audit cumulative known estimate across earlier accounts/attempts | $0.05203106; 1,300.78 VND; one historical call has unknown usage |

The strict field-key metric still does not accept the Payment Request's valid `bank_account` key. Its source-grounded value is correct; neither the production logic nor evaluator aliases were patched to inflate the score. Manual inspection supports HDMI arithmetic, Dock quantity/amount variance, HDMI PO/invoice variance, total variance with subtotal/tax contributions, internal and actual-invoice payment excess, bank account mismatch, differing beneficiary/company and account-holder names, and pending accountant review. The cross payment proof uses the actual invoice total less recorded payments. Some identity concerns overlap in business impact while citing different counterpart roles; expected-category recall does not measure issue precision or semantic deduplication quality.

All three identity calls completed, with registered structured citations restored to original source IDs. No fixture values or sample-specific anomaly rules were introduced. This live run verifies the previously quota-blocked Payment Request recovery, not generalization to arbitrary customer documents. The local 10,000-Neuron cap remains unchanged; active-account testing including the probe used 1,444.259139 estimated Neurons. Billed charges and provider account-wide remaining quota remain unknown. The 268-second retry is not a fresh end-to-end benchmark for all three documents; the rejected initial response accounts for 79.328 seconds of it.

The unchanged backend revision has 163 passing regression tests and Ruff verification. Browser verification against this completed saved report covers source units/pages, source formulas, distinct internal/cross navigation, every cross finding's cited documents/pages, scroll retention, USD/VND usage, and history reopening. Optional duplicate inference and deleted corrected/partial fixtures remain outside this browser run. Fresh corrected/image-only/mixed/multipage/unreadable/reference-mismatch/prompt-injection acceptance under this revision remains unfinished; earlier fixture results are historical. No automatic future inference is scheduled.

## Submission revision boundaries — 2026-10-06

The current report contract is v8 (`policy-grounded-name-comparisons`). Following the clarified business requirement, a difference between beneficiary/account-holder and supplier/company names is not an anomaly unless an explicit supplied policy requires a match. Account-number comparison remains supported. Historical seven-category expectations and name findings in the dated sections above describe earlier policies, not current acceptance criteria; the evaluation script's historical name expectation must not be used to certify current policy compliance.

The latest inspected audit `cbacc7fa61914d329012ddf90bc37054` was failed/incomplete because Payment Request quality review required another observation for an already-grounded PO identifier repeated in a same-page narrative block. Identifier completeness now requires grounded evidence on every page where each known identifier appears, rather than one duplicate field for every same-page mention. Cross-page coverage and source grounding remain enforced. No fixture identifier or page/block ID is hard-coded into the fix.

Live retry after this validator change could not be started from the restricted local shell because the API request received a socket-permission error. No successful live recovery or new accuracy measurement is claimed for this change. Historical unit/browser counts and live results above remain measurements of their stated revisions. Current full acceptance, especially fresh corrected/scan/mixed/stress inference, remains unfinished.
