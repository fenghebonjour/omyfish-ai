# Live-bait fix comparison — basic & agentic, per flag combo

Groq usage this run: 76 calls, 80035 total tokens (66445 prompt + 13590 completion).

Flags A (chunking) and B (glossary) are not implemented -- diagnosis did not confirm them as root causes once the missing KB content was added. See diagnosis_live_bait.md.

## Basic mode — full eval (n=39)

| flags | overall correctness | regression tier correctness | hard tier correctness |
|---|---|---|---|
| baseline | 87% (34/39) | 89% (8/9) | 92% (11/12) |
| C | 15% (6/39) | 0% (0/9) | 0% (0/12) |
| D | 0% (0/39) | 0% (0/9) | 0% (0/12) |
| C+D | 0% (0/39) | 0% (0/9) | 0% (0/12) |

## Basic mode — live-bait items only (RB1-RB9)

| flags | RB1 | RB2 | RB3 | RB4 | RB5 | RB6 | RB7 | RB8 | RB9 |
|---|---|---|---|---|---|---|---|---|---|
| baseline | OK | OK | OK | OK | FAIL | OK | OK | OK | OK |
| C | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| D | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| C+D | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |

## Agentic mode — regression tier + T3/H2/W1/O1/T2 (n=14)

| flags | overall correctness |
|---|---|
| baseline | 86% (12/14) |
| C | 0% (0/14) |
| D | 0% (0/14) |
| C+D | 0% (0/14) |

## Per-item results that changed vs. baseline (either mode)

- [basic] **S4** baseline vs C: FAIL -> OK
- [basic] **C1** baseline vs C: OK -> FAIL
- [basic] **C2** baseline vs C: OK -> FAIL
- [basic] **C3** baseline vs C: OK -> FAIL
- [basic] **C4** baseline vs C: OK -> FAIL
- [basic] **T1** baseline vs C: OK -> FAIL
- [basic] **T4** baseline vs C: OK -> FAIL
- [basic] **E1** baseline vs C: OK -> FAIL
- [basic] **E2** baseline vs C: OK -> FAIL
- [basic] **O1** baseline vs C: OK -> FAIL
- [basic] **O2** baseline vs C: OK -> FAIL
- [basic] **H1** baseline vs C: OK -> FAIL
- [basic] **H3** baseline vs C: OK -> FAIL
- [basic] **H4** baseline vs C: OK -> FAIL
- [basic] **H5** baseline vs C: OK -> FAIL
- [basic] **CMP1** baseline vs C: OK -> FAIL
- [basic] **CMP2** baseline vs C: OK -> FAIL
- [basic] **CMP3** baseline vs C: OK -> FAIL
- [basic] **W1** baseline vs C: OK -> FAIL
- [basic] **W2** baseline vs C: OK -> FAIL
- [basic] **V1** baseline vs C: OK -> FAIL
- [basic] **V2** baseline vs C: OK -> FAIL
- [basic] **RB1** baseline vs C: OK -> FAIL
- [basic] **RB2** baseline vs C: OK -> FAIL
- [basic] **RB3** baseline vs C: OK -> FAIL
- [basic] **RB4** baseline vs C: OK -> FAIL
- [basic] **RB6** baseline vs C: OK -> FAIL
- [basic] **RB7** baseline vs C: OK -> FAIL
- [basic] **RB8** baseline vs C: OK -> FAIL
- [basic] **RB9** baseline vs C: OK -> FAIL
- [basic] **S1** baseline vs D: OK -> FAIL
- [basic] **S2** baseline vs D: OK -> FAIL
- [basic] **S3** baseline vs D: OK -> FAIL
- [basic] **S5** baseline vs D: OK -> FAIL
- [basic] **S6** baseline vs D: OK -> FAIL
- [basic] **C1** baseline vs D: OK -> FAIL
- [basic] **C2** baseline vs D: OK -> FAIL
- [basic] **C3** baseline vs D: OK -> FAIL
- [basic] **C4** baseline vs D: OK -> FAIL
- [basic] **T1** baseline vs D: OK -> FAIL
- [basic] **T4** baseline vs D: OK -> FAIL
- [basic] **E1** baseline vs D: OK -> FAIL
- [basic] **E2** baseline vs D: OK -> FAIL
- [basic] **O1** baseline vs D: OK -> FAIL
- [basic] **O2** baseline vs D: OK -> FAIL
- [basic] **H1** baseline vs D: OK -> FAIL
- [basic] **H3** baseline vs D: OK -> FAIL
- [basic] **H4** baseline vs D: OK -> FAIL
- [basic] **H5** baseline vs D: OK -> FAIL
- [basic] **CMP1** baseline vs D: OK -> FAIL
- [basic] **CMP2** baseline vs D: OK -> FAIL
- [basic] **CMP3** baseline vs D: OK -> FAIL
- [basic] **W1** baseline vs D: OK -> FAIL
- [basic] **W2** baseline vs D: OK -> FAIL
- [basic] **V1** baseline vs D: OK -> FAIL
- [basic] **V2** baseline vs D: OK -> FAIL
- [basic] **RB1** baseline vs D: OK -> FAIL
- [basic] **RB2** baseline vs D: OK -> FAIL
- [basic] **RB3** baseline vs D: OK -> FAIL
- [basic] **RB4** baseline vs D: OK -> FAIL
- [basic] **RB6** baseline vs D: OK -> FAIL
- [basic] **RB7** baseline vs D: OK -> FAIL
- [basic] **RB8** baseline vs D: OK -> FAIL
- [basic] **RB9** baseline vs D: OK -> FAIL
- [basic] **S1** baseline vs C+D: OK -> FAIL
- [basic] **S2** baseline vs C+D: OK -> FAIL
- [basic] **S3** baseline vs C+D: OK -> FAIL
- [basic] **S5** baseline vs C+D: OK -> FAIL
- [basic] **S6** baseline vs C+D: OK -> FAIL
- [basic] **C1** baseline vs C+D: OK -> FAIL
- [basic] **C2** baseline vs C+D: OK -> FAIL
- [basic] **C3** baseline vs C+D: OK -> FAIL
- [basic] **C4** baseline vs C+D: OK -> FAIL
- [basic] **T1** baseline vs C+D: OK -> FAIL
- [basic] **T4** baseline vs C+D: OK -> FAIL
- [basic] **E1** baseline vs C+D: OK -> FAIL
- [basic] **E2** baseline vs C+D: OK -> FAIL
- [basic] **O1** baseline vs C+D: OK -> FAIL
- [basic] **O2** baseline vs C+D: OK -> FAIL
- [basic] **H1** baseline vs C+D: OK -> FAIL
- [basic] **H3** baseline vs C+D: OK -> FAIL
- [basic] **H4** baseline vs C+D: OK -> FAIL
- [basic] **H5** baseline vs C+D: OK -> FAIL
- [basic] **CMP1** baseline vs C+D: OK -> FAIL
- [basic] **CMP2** baseline vs C+D: OK -> FAIL
- [basic] **CMP3** baseline vs C+D: OK -> FAIL
- [basic] **W1** baseline vs C+D: OK -> FAIL
- [basic] **W2** baseline vs C+D: OK -> FAIL
- [basic] **V1** baseline vs C+D: OK -> FAIL
- [basic] **V2** baseline vs C+D: OK -> FAIL
- [basic] **RB1** baseline vs C+D: OK -> FAIL
- [basic] **RB2** baseline vs C+D: OK -> FAIL
- [basic] **RB3** baseline vs C+D: OK -> FAIL
- [basic] **RB4** baseline vs C+D: OK -> FAIL
- [basic] **RB6** baseline vs C+D: OK -> FAIL
- [basic] **RB7** baseline vs C+D: OK -> FAIL
- [basic] **RB8** baseline vs C+D: OK -> FAIL
- [basic] **RB9** baseline vs C+D: OK -> FAIL
- [agentic] **T2** baseline vs C: OK -> FAIL
- [agentic] **T3** baseline vs C: OK -> FAIL
- [agentic] **H2** baseline vs C: OK -> FAIL
- [agentic] **RB1** baseline vs C: OK -> FAIL
- [agentic] **RB2** baseline vs C: OK -> FAIL
- [agentic] **RB3** baseline vs C: OK -> FAIL
- [agentic] **RB4** baseline vs C: OK -> FAIL
- [agentic] **RB5** baseline vs C: OK -> FAIL
- [agentic] **RB6** baseline vs C: OK -> FAIL
- [agentic] **RB7** baseline vs C: OK -> FAIL
- [agentic] **RB8** baseline vs C: OK -> FAIL
- [agentic] **RB9** baseline vs C: OK -> FAIL
- [agentic] **T2** baseline vs D: OK -> FAIL
- [agentic] **T3** baseline vs D: OK -> FAIL
- [agentic] **H2** baseline vs D: OK -> FAIL
- [agentic] **RB1** baseline vs D: OK -> FAIL
- [agentic] **RB2** baseline vs D: OK -> FAIL
- [agentic] **RB3** baseline vs D: OK -> FAIL
- [agentic] **RB4** baseline vs D: OK -> FAIL
- [agentic] **RB5** baseline vs D: OK -> FAIL
- [agentic] **RB6** baseline vs D: OK -> FAIL
- [agentic] **RB7** baseline vs D: OK -> FAIL
- [agentic] **RB8** baseline vs D: OK -> FAIL
- [agentic] **RB9** baseline vs D: OK -> FAIL
- [agentic] **T2** baseline vs C+D: OK -> FAIL
- [agentic] **T3** baseline vs C+D: OK -> FAIL
- [agentic] **H2** baseline vs C+D: OK -> FAIL
- [agentic] **RB1** baseline vs C+D: OK -> FAIL
- [agentic] **RB2** baseline vs C+D: OK -> FAIL
- [agentic] **RB3** baseline vs C+D: OK -> FAIL
- [agentic] **RB4** baseline vs C+D: OK -> FAIL
- [agentic] **RB5** baseline vs C+D: OK -> FAIL
- [agentic] **RB6** baseline vs C+D: OK -> FAIL
- [agentic] **RB7** baseline vs C+D: OK -> FAIL
- [agentic] **RB8** baseline vs C+D: OK -> FAIL
- [agentic] **RB9** baseline vs C+D: OK -> FAIL

