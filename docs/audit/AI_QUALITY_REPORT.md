# AiOS AI Quality Report

Audit date: 2026-08-08

## Current architecture

AiOS is primarily deterministic and local, with optional Ollama JSON generation. Rule triage, structured output parsing, planner templates, lexical/vector ranking, and user approval gates remain intentionally conservative.

## Controls now present

- Email sender, subject, snippet, and body are explicitly marked as untrusted content in model prompts.
- Ollama is loopback-only and unsafe URLs fail before network I/O.
- Classifier categories are allow-listed; confidence is finite and clamped to `[0, 1]`.
- AI-generated suggestions do not directly submit forms or external actions; browser submission remains approval-gated.
- `scripts/ai_quality_gate.py` runs a 16-case redacted synthetic corpus in CI and reports category precision/recall/F1, macro F1, actionable precision/recall/F1, expected calibration error, abstention rate, and prompt-injection safety.

## Current gate result

The 2026-08-08 gate passes with macro F1 `1.0000`, actionable F1 `1.0000`, ECE `0.1869`, abstention `0.1250`, and a safe prompt-injection result. The fixture is intentionally synthetic and contains no private mailbox content. It is a deterministic regression gate, not a claim of production accuracy.

## Remaining quality gap

AiOS still needs a consented, locally stored, redacted, user-labeled corpus covering hackathons, placements, NeoPat, deadlines, applied/opening state, interviews, and ignore cases. The release gate should add deadline extraction accuracy, false-notification rate, and drift comparisons over time. The synthetic gate must remain in place even after real labels are added.

Every AI-produced field should retain:

```json
{
  "value": "...",
  "confidence": 0.0,
  "evidence_ids": ["email:123"],
  "source": "rule|ollama|user",
  "needs_review": true
}
```

The model must be allowed to return `unknown` and `needs_review`; a plausible sentence is not evidence of a deadline, application, skill, or company.
