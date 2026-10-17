# Regs & Tips chatbot — baseline eval v2 (basic + hard tiers)

- Overall hit@3: 82% (23/28)
- Overall answer correctness: 93% (28/30)

## By tier

| tier | n | hit@3 | correctness |
|---|---|---|---|
| basic | 18 | 94% (15/16) | 94% (17/18) |
| hard | 12 | 67% (8/12) | 92% (11/12) |

## By category

| category | n | hit@3 | correctness |
|---|---|---|---|
| single_fact | 6 | 100% (6/6) | 100% (6/6) |
| conversational | 4 | 100% (4/4) | 100% (4/4) |
| two_hop | 4 | 75% (3/4) | 75% (3/4) |
| exact_term | 2 | 100% (2/2) | 100% (2/2) |
| out_of_scope | 2 | n/a | 100% (2/2) |
| compound | 5 | 80% (4/5) | 80% (4/5) |
| compare | 3 | 100% (3/3) | 100% (3/3) |
| premise_check | 2 | 50% (1/2) | 100% (2/2) |
| vague | 2 | 0% (0/2) | 100% (2/2) |

## vocab_gap items only (casual phrasing, differs from KB wording)

- n=7, hit@3: 57% (4/7), correctness: 86% (6/7)

## Failures

### T3 [basic] (two_hop)
- Question: Do I need a licence at age 10, and is a consumption advisory the same thing as a legal catch limit?
- Answer: No, a consumption advisory is **not** the same as a legal catch / possession limit. The advisory only gives health guidance about how many meals you should eat, based on mercury or other contaminants; it does not dictate how many fish you may legally catch or keep.

The reference material does not mention the age at which a sport‑fishing licence is required, so I can’t answer that from the provided context. Please check the official Québec website (quebec.ca) or the OMyFish app’s Regs lookup for the licence‑age rules.

*Always verify the current licence requirements, catch limits, seasons and any consumption advisories before you head out.*
- Retrieval miss — retrieved: [('regulations_overview.md', 'Consumption advisories are a different question'), ('regulations_overview.md', 'Fishing zones'), ('regulations_overview.md', 'This is a plain-language summary to help anglers understand how Quebec fishing')]
- Correctness miss — missing facts: ['12', 'separate']

### H2 [hard vocab_gap] (compound)
- Question: Does my 9-year-old need a fishing license, and is there a size range I'd have to release a walleye within?
- Answer: The reference material doesn’t specify whether a 9‑year‑old must have a fishing licence – you’ll need to check the official licence rules on quebec.ca or in the OMyFish app’s licence‑lookup section.

For walleye, many zones use a length‑based “slot” limit. For example, Zone 27 requires you to release any walleye that measures **37 cm to 53 cm inclusive**. Because the exact slot can vary from zone to zone, you’ll need to look up the specific limit for the zone you’ll be fishing in.

*Always verify the current licence requirements and size limits before you head out, and check any consumption advisories if you plan to eat the fish.*
- Retrieval miss — retrieved: [('regulations_overview.md', 'What a "limit" usually includes'), ('species_tackle.md', 'Walleye (doré jaune)'), ('regulations_overview.md', 'Fishing zones')]
- Correctness miss — missing facts: ['12']

### W2 [hard vocab_gap] (premise_check)
- Question: Quebec regulations say I can only fish with artificial lures, right? No live bait allowed anywhere?
- Answer: The reference material doesn’t say that Quebec has a blanket rule requiring only artificial lures. In fact, it notes that lake‑sturgeon anglers often use **live bait** such as worms, leeches, or cut bait, while other species (like lake‑trout or brook‑trout) are commonly fished with lures.  

Because catch limits, seasons, permitted gear – including whether live bait is allowed – are set **per zone and per species**, you need to consult the specific regulations for the zone you’ll be fishing in.

**Tip:** Check the zone‑specific Regs lookup in the app or visit quebec.ca to confirm the current rules for your target species and area. Always verify the latest regulations before you head out.
- Retrieval miss — retrieved: [('regulations_overview.md', 'Fishing zones'), ('species_tackle.md', 'Lake sturgeon (esturgeon jaune)'), ('species_tackle.md', 'Editorial notes on how anglers commonly target these species in Quebec. This')]

### V1 [hard] (vague)
- Question: What's the catch limit for my favorite fish?
- Answer: I’m sorry—I don’t have the specific catch limit for the fish you’re thinking of. The reference only notes that muskellunge “often carry a low daily limit,” but it doesn’t give an exact number, and no other species are detailed.

Please check the official [quebec.ca](https://www.quebec.ca/en/tourism-and-recreation/sporting-and-outdoor-activities/sport-fishing) site or use the OMyFish app’s Regs lookup for the current catch/possession limit for your favorite species.  

**Reminder:** Always verify the latest regulations (limits, seasons, size rules, and any consumption advisories) before you go fishing.
- Retrieval miss — retrieved: [('regulations_overview.md', 'Consumption advisories are a different question'), ('regulations_overview.md', 'This is a plain-language summary to help anglers understand how Quebec fishing'), ('regulations_overview.md', 'What a "limit" usually includes')]

### V2 [hard vocab_gap] (vague)
- Question: Can I keep a legal walleye around here?
- Answer: Walleye in Quebec are often subject to a length‑based “slot” limit. In many zones (for example, Zone 27 the protected slot is 37 – 53 cm), you may only keep a walleye that is **outside** that size range and that you do not exceed the daily possession limit or any seasonal restriction.

So, before you decide to keep a walleye you’ve caught, verify:

* the exact slot dimensions for the zone you’re fishing in,  
* the daily catch/possession limit for walleye (or walleye + sauger combined), and  
* that you are within the open season for the species.

If the fish’s length falls outside the protected slot and you are within those other limits, it can be kept legally.  

**Reminder:** Always double‑check the current regulations (quebec.ca or the OMyFish app’s Regs lookup) before you keep or release a fish, and remember that consumption advisories are a separate health guideline.
- Retrieval miss — retrieved: [('species_tackle.md', 'Walleye (doré jaune)'), ('species_tackle.md', 'Lake sturgeon (esturgeon jaune)'), ('regulations_overview.md', 'Consumption advisories are a different question')]

