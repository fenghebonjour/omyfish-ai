# Regs & Tips chatbot — baseline eval

- Overall hit@3: 94%
- Overall answer correctness: 94%

## By category

| category | n | hit@3 | correctness |
|---|---|---|---|
| single_fact | 6 | 6/6 | 6/6 |
| conversational | 4 | 4/4 | 4/4 |
| two_hop | 4 | 3/4 | 3/4 |
| exact_term | 2 | 2/2 | 2/2 |
| out_of_scope | 2 | n/a | 2/2 |

## Failures

### T3 (two_hop)
- Question: Do I need a licence at age 10, and is a consumption advisory the same thing as a legal catch limit?
- Answer: No, a consumption advisory is **not** the same as a legal catch limit.  
The advisory deals only with health guidance (e.g., how many meals per month are safe to eat) and is separate from the province’s fishing rules that set daily limits, size limits, seasons, etc.

The reference material does not specify whether a licence is required for a 10‑year‑old. You’ll need to check the official licence requirements on [quebec.ca](https://www.quebec.ca) or in the OMyFish app’s Regs lookup.

*Always verify the current licence rules, catch limits and any consumption advisories before you head out.*
- Retrieval miss — retrieved: [('regulations_overview.md', 'Consumption advisories are a different question'), ('regulations_overview.md', 'Fishing zones'), ('regulations_overview.md', 'This is a plain-language summary to help anglers understand how Quebec fishing')]
- Correctness miss — missing facts: ['12']

