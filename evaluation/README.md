# Phase 9B Evaluation Boundary

`ground-truth/` is evaluation-only. It is excluded by the root `.dockerignore`, is never copied into
the backend or frontend runtime images, and is not mounted by Docker Compose. Runtime seeding reads
only `fixtures/evaluation/phase-9b/manifest.json`, whose schema requires
`contains_ground_truth: false`.

The standard-library evaluator accepts a completed runtime seed/result receipt, then reads the
separate truth document. It has no application import and does not write to PostgreSQL. Run it only
after runtime output exists:

```text
python evaluation/evaluate_phase9b.py --receipt <runtime-receipt.json>
```

On the clean VM, invoke it from a disposable Python container rather than installing host Python.
