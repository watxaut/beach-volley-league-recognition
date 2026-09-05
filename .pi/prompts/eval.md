---
description: Run test suite + evaluate.py and check for regressions
argument-hint: "[video stem(s)]"
---
Run the verification battery and report regressions:

1. `pytest tests/ -v` — the suite was 220 green at the last STATUS.md entry; flag any count change or failure.
2. `python scripts/evaluate.py --predictions output/<stem>/ --ground-truth ground_truth/` for ${@:-every entreno stem that has an output dir}.
3. Compare every metric against the values recorded in STATUS.md. A delta without a mechanism that explains it is a red flag, not a win.
