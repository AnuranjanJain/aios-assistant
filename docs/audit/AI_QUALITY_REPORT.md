# AiOS AI Quality Report

Audit date: 2026-08-08

## Current architecture

AiOS is primarily deterministic and local, with optional Ollama JSON generation. Rule triage, structured output parsing, planner templates, lexical/vector ranking, and user approval gates remain intentionally conservative.

## Controls now present

- Email sender, subject, snippet, and body are explicitly marked as untrusted content in model prompts.
- Ollama is loopback-only and unsafe URLs fail before network I/O.
- Classifier categories are allow-listed; confidence is finite and clamped to `[0, 1]`.
- AI-generated suggestions do not directly submit forms or external actions; browser submission remains approval-gated.
- `scripts/ai_quality_gate.py` runs deterministic personal-interview, job-alert, and prompt-injection cases in CI.

## Remaining quality gap

The smoke gate is not a calibrated evaluation. AiOS still needs a locally stored, redacted, user-labeled corpus covering hackathons, placements, NeoPat, deadlines, applied/opening state, interviews, and ignore cases. The release gate should track per-class precision, recall, F1, deadline extraction accuracy, false-notification rate, calibration error, and abstention rate.

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
