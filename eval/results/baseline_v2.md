# Regs & Tips chatbot — baseline eval v2 (basic + hard tiers)

- Overall hit@3: 84% (31/37)
- Overall answer correctness: 95% (37/39)

## By tier

| tier | n | hit@3 | correctness |
|---|---|---|---|
| basic | 18 | 94% (15/16) | 94% (17/18) |
| hard | 12 | 58% (7/12) | 92% (11/12) |
| regression | 9 | 100% (9/9) | 100% (9/9) |

## By category

| category | n | hit@3 | correctness |
|---|---|---|---|
| single_fact | 8 | 100% (8/8) | 100% (8/8) |
| conversational | 4 | 100% (4/4) | 100% (4/4) |
| two_hop | 4 | 75% (3/4) | 75% (3/4) |
| exact_term | 2 | 100% (2/2) | 100% (2/2) |
| out_of_scope | 2 | n/a | 100% (2/2) |
| compound | 5 | 80% (4/5) | 100% (5/5) |
| compare | 3 | 67% (2/3) | 100% (3/3) |
| premise_check | 3 | 67% (2/3) | 67% (2/3) |
| vague | 2 | 0% (0/2) | 100% (2/2) |
| legality | 6 | 100% (6/6) | 100% (6/6) |

## vocab_gap items only (casual phrasing, differs from KB wording)

- n=13, hit@3: 77% (10/13), correctness: 100% (13/13)

## Failures

### T2 [basic] (two_hop)
- Question: Are both muskellunge and lake sturgeon restricted to angling-only gear in the tackle notes?
- Answer: Yes. Both the lake‑sturgeon and the muskellunge entries note an “angling‑only restriction.” Be sure to verify the current regulations before you fish, as limits and rules can change.
- Correctness miss — missing facts: ['lake sturgeon']

### T3 [basic] (two_hop)
- Question: Do I need a licence at age 10, and is a consumption advisory the same thing as a legal catch limit?
- Answer: - **Licence requirement:** No. A Quebec sport‑fishing licence is required only for people **12 years old or older** (with a few special free‑fishing days). At age 10 you are not required to have a licence.  

- **Consumption advisory vs. legal limit:** No. A consumption advisory is a health guideline about how many meals you should eat, based on mercury or other contaminants. It is **separate** from the legal daily catch‑and‑keep limit, which is set by the province.

*Always double‑check the current regulations and any advisories on quebec.ca or in the OMyFish app before you head out.*
- Retrieval miss — retrieved: [('regulations_overview.md', 'Consumption advisories are a different question'), ('regulations_overview.md', 'Fishing zones'), ('regulations_overview.md', 'This is a plain-language summary to help anglers understand how Quebec fishing')]

### H2 [hard vocab_gap] (compound)
- Question: Does my 9-year-old need a fishing license, and is there a size range I'd have to release a walleye within?
- Answer: **License:** No. In Quebec a sport‑fishing licence is required only for anglers 12 years old or older, so a 9‑year‑old does not need one.

**Walleye size limit:** Walleye are subject to a length‑based “slot” limit in many zones. For example, Zone 27 uses a 37 cm – 53 cm slot, meaning fish that fall inside that range must be released. The exact slot varies by zone, so you’ll need to check the regulation for the specific zone you’ll be fishing in.

*Always verify the current licence requirement, zone‑specific slot limits, and any other rules before you head out.*
- Retrieval miss — retrieved: [('regulations_overview.md', 'What a "limit" usually includes'), ('species_tackle.md', 'Walleye (doré jaune)'), ('regulations_overview.md', 'Fishing zones')]

### CMP2 [hard vocab_gap] (compare)
- Question: Are walleye and northern pike active at the same times of day, or does one bite better at night?
- Answer: Northern pike tend to bite most actively **during the heat of the day**, while walleye are strongest **at dawn, dusk, and after dark**. So their peak activity periods differ, with walleye generally providing better night‑time action.  

*Remember to verify current regulations (licensing, slot limits, bait rules, etc.) before you head out.*
- Retrieval miss — retrieved: [('species_tackle.md', 'Northern pike (grand brochet)'), ('regulations_overview.md', 'Consumption advisories are a different question'), ('species_tackle.md', 'Yellow perch (perchaude) & black crappie (marigane noire)')]

### W1 [hard] (premise_check)
- Question: Since walleye and pike are basically the same fish, is the slot limit example the same for both?
- Answer: The context only mentions a length‑based “slot” limit for walleye (e.g., Zone 27’s 37–53 cm range). It does not provide any slot‑limit information for northern pike, so we can’t confirm that the same example applies to pike.

Please check the current regulations for pike on quebec.ca or in the app’s Regs lookup to be sure. Remember to verify the latest limits and any consumption advisories before you fish.
- Retrieval miss — retrieved: [('species_tackle.md', 'Northern pike (grand brochet)'), ('regulations_overview.md', 'Consumption advisories are a different question'), ('regulations_overview.md', 'This is a plain-language summary to help anglers understand how Quebec fishing')]
- Correctness miss — missing facts: ['different species', 'different fish', 'not the same species', 'two different', 'walleye only', 'only walleye', 'specific to walleye', 'mention a slot limit', 'mention any slot limit', 'only for walleye']

### V1 [hard] (vague)
- Question: What's the catch limit for my favorite fish?
- Answer: I’m sorry—I don’t have a specific catch limit for the fish you’re thinking of in the provided information. Please check the detailed zone‑specific regulations on [quebec.ca](https://www.quebec.ca/en/tourism-and-recreation/sporting-and-outdoor-activities/sport-fishing) or use the app’s Regs lookup to get the exact limit for that species.  

*Always verify the current regulations before you fish.*
- Retrieval miss — retrieved: [('regulations_overview.md', 'Consumption advisories are a different question'), ('regulations_overview.md', 'This is a plain-language summary to help anglers understand how Quebec fishing'), ('regulations_overview.md', 'What a "limit" usually includes')]

### V2 [hard vocab_gap] (vague)
- Question: Can I keep a legal walleye around here?
- Answer: The answer depends on the specific zone you’re fishing in. In many Quebec zones walleye are subject to a length‑based “slot” limit (for example, Zone 27 protects fish 37 cm – 53 cm). You may keep a walleye only if it falls **outside** that protected size range and you stay within any daily catch/possession limits that apply to your zone, and you have a valid sport‑fishing licence (required for anyone 12 years or older).

Because the exact slot limits and daily limits vary by zone, the answer can’t be confirmed without knowing your location. Check the zone‑specific regulation sheet (or the app’s Regs lookup) for the precise limits before keeping the fish.  

*Always verify the current regulations and any consumption advisories before you fish.*
- Retrieval miss — retrieved: [('species_tackle.md', 'Walleye (doré jaune)'), ('species_tackle.md', 'Lake sturgeon (esturgeon jaune)'), ('regulations_overview.md', 'Consumption advisories are a different question')]

