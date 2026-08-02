# Question Resolution (em-workflow)

Referenced by every worker contract and phase protocol that can return a
question packet (`references/question-packet-schema.md`). This document is
the SSOT for how the orchestrator turns a packet into answers, in both
interactive and batch runs — phase protocols and contracts point here
instead of restating the procedure. Renders design-input.md 5.9.

The packet and answer object shapes themselves (`gate_id`, `options[].
option_id`, `on_unanswered`, `resolution_note`, etc.) are defined in
`references/question-packet-schema.md`; this document only states the
resolution procedure built on top of those fields. The gate-ID-keyed batch
decisions this procedure looks up live in `references/batch-policies.yaml`.

## Deduplication

Applied in this order, before a question is presented or resolved:

1. The same `question_id` is the same question. If a worker resubmits it
   with a changed body after it has already been answered, that is a
   worker protocol violation.
2. A `supersedes` reference to an existing question ID obsoletes the prior
   question.
3. The same `gate_id`, the same evidence target, and the same affected
   workflow field mark a duplicate candidate.
4. The orchestrator does not judge sameness from prose differences in the
   `prompt` text — it re-dispatches the worker asking it to reuse the
   stable question ID instead of minting a new one.
5. An answered question is never re-presented. If the worker has new
   grounds to invalidate a prior answer, it must mint a new question ID
   and set `supersedes`, not resend the old ID.

## Priority (stable sort)

1. `blocking: true` first.
2. `priority`: critical → high → normal → low.
3. `category`, in this order: feature-identity → business-objective →
   functional-requirement → acceptance-criteria → security →
   technical-requirement → dependency/license → testing →
   user-experience/design → edge-case → other.
4. `question_id`.

A question carrying `depends_on` is withheld from presentation until every
question it depends on has been answered.

## Presentation limits

- At most 3 questions per `AskUserQuestion` call.
- At most 4 options per question.
- A packet may carry up to 32 questions; the limits above mean a large
  packet is presented across several `AskUserQuestion` calls, never as one.

## Batch resolution sequence

1. The worker returns `status: needs_user_input` with a packet.
2. For each question, look up its `gate_id` in
   `references/batch-policies.yaml`.
3. If a policy entry exists, apply its `option_id` or `action`.
4. If the resolved option ID is not present in that question's
   `options[].option_id`, this is a protocol error and the phase aborts —
   label matching is never substituted for the option ID.
5. Build the answer object with `source: batch-decision-table`.
6. Persist every answer to phase-state.
7. Re-dispatch the worker using the same shape used in interactive mode.

## Unlisted-gate fallback

When a question's `gate_id` has no entry in `references/batch-policies.yaml`:

1. Confirm the `gate_id` is genuinely absent from the policy file.
2. Pass the question's `prompt`, `options`, `why_needed`, `evidence`, and
   the worker's tentative position to Codex.
3. Judge whether Codex's suggestion maps onto one of the question's
   existing `option_id`s.
4. If it maps, record the answer with `source: batch-codex-consultation`.
   Codex's output is untrusted here — the orchestrator judges the mapping
   itself and never adopts Codex's text verbatim as the answer.
5. If it does not map, fall through to `on_unanswered`.
6. `record_tbd` → generate a TBD answer.
7. `block` → if the question is a merely preferential choice on a success
   path, take the option with the smallest side effect. **Specification
   change, security, licensing, and irreversible operations abort the
   phase instead.** This replaces the current continue-on-success-path
   rule stated in `references/batch-mode.md` and is an intentional
   behaviour change, not a regression.
8. `use_batch_policy` with no matching policy entry is a schema/policy
   inconsistency — abort.
9. Record the decision basis in the answer's `resolution_note` and in the
   run report, whichever branch above was taken.
