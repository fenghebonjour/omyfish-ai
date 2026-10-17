# Regs & Tips chatbot — basic vs agentic retrieval (v1)

Agentic hit@3 is scored against the UNION of chunks retrieved across all search_regs calls for a question (up to 3 calls x top-3 each = up to 9 chunks), not a single top-3 pass like basic mode -- the two hit@3 numbers below are not directly comparable; they're reported side by side for visibility, not parity.

- Average tool calls per question (agentic): 1.23
- Average latency per question: basic 4.93s, agentic 13.14s

## Overall

| mode | n | hit@3 | correctness |
|---|---|---|---|
| basic | 30 | 82% (23/28) | 83% (25/30) |
| agentic | 30 | 86% (24/28) | 90% (27/30) |

## By tier

| tier | basic hit@3 | agentic hit@3 | basic correctness | agentic correctness |
|---|---|---|---|---|
| basic | 94% (15/16) | 94% (15/16) | 89% (16/18) | 89% (16/18) |
| hard | 67% (8/12) | 75% (9/12) | 75% (9/12) | 92% (11/12) |

## By category

| category | basic hit@3 | agentic hit@3 | basic correctness | agentic correctness |
|---|---|---|---|---|
| single_fact | 100% (6/6) | 100% (6/6) | 100% (6/6) | 100% (6/6) |
| conversational | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) |
| two_hop | 75% (3/4) | 75% (3/4) | 50% (2/4) | 75% (3/4) |
| exact_term | 100% (2/2) | 100% (2/2) | 100% (2/2) | 100% (2/2) |
| out_of_scope | n/a | n/a | 100% (2/2) | 50% (1/2) |
| compound | 80% (4/5) | 100% (5/5) | 80% (4/5) | 100% (5/5) |
| compare | 100% (3/3) | 100% (3/3) | 100% (3/3) | 100% (3/3) |
| premise_check | 50% (1/2) | 50% (1/2) | 50% (1/2) | 50% (1/2) |
| vague | 0% (0/2) | 0% (0/2) | 50% (1/2) | 100% (2/2) |

## vocab_gap items only

- n=7
- basic:   hit@3 57% (4/7), correctness 71% (5/7)
- agentic: hit@3 71% (5/7), correctness 100% (7/7)

## Questions whose correctness result changed (basic -> agentic)

- **T2** [basic] (two_hop) FAIL -> OK: Are both muskellunge and lake sturgeon restricted to angling-only gear in the tackle notes?
- **O1** [basic] (out_of_scope) OK -> FAIL: What is the current price of a non-resident annual fishing licence in Quebec?
- **H2** [hard] (compound) FAIL -> OK: Does my 9-year-old need a fishing license, and is there a size range I'd have to release a walleye within?
- **V2** [hard] (vague) FAIL -> OK: Can I keep a legal walleye around here?

## Agentic per-question log

### S1 (single_fact) — 1 tool call(s), 15.916s
- Question: What length range does the walleye tackle notes give as an example slot limit, and which zone number is used in that example?
  - search_regs(query='walleye tackle notes example slot limit length range zone number', species='walleye', zone=None) -> ['species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#What a "limit" usually includes', 'regulations_overview.md#Fishing zones']
- Answer: The tackle‑notes example for walleye cites a **slot‑length limit of 37 cm to 53 cm** and uses **Zone 27** for that illustration.  

*Always verify the current regulations for the specific zone you fish in before keeping any walleye.*
- Retrieval (union) passed: True
- Correctness passed: True

### S2 (single_fact) — 1 tool call(s), 14.553s
- Question: According to the regulations overview, at what age does someone need their own Quebec fishing licence?
  - search_regs(query='age requirement for obtaining a personal fishing licence', species=None, zone=None) -> ['regulations_overview.md#Licensing', 'regulations_overview.md#What a "limit" usually includes', 'regulations_overview.md#Fishing zones']
- Answer: A Quebec sport‑fishing licence is required for anyone **12 years of age or older** (with a few limited free‑fishing days as exceptions).  

*Always verify that you have the current licence requirements before you head out, as regulations can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### S3 (single_fact) — 1 tool call(s), 14.014s
- Question: According to the overview, what's the full numeric range of fishing zones Quebec is divided into?
  - search_regs(query='overview of fishing zones numeric range Quebec divided into', species=None, zone=None) -> ['regulations_overview.md#Fishing zones', 'regulations_overview.md#Licensing', 'regulations_overview.md#What a "limit" usually includes']
- Answer: Quebec’s fishing zones are numbered **Zone 1 through Zone 29** (some of these zones are further split into north/south or east/west halves).  

*Always verify the current regulations before heading out, as zone limits, seasons and other rules can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### S4 (single_fact) — 1 tool call(s), 15.163s
- Question: What example daily catch limit does the regulations overview give for walleye and sauger combined?
  - search_regs(query='example daily catch limit walleye and sauger combined', species=None, zone=None) -> ['regulations_overview.md#What a "limit" usually includes', 'species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#Fishing zones']
- Answer: The regulations overview cites an example daily **catch/possession limit of “6 in all” for walleye and sauger combined**【regulations_overview.md#What a "limit" usually includes】.  

*Always confirm the latest limits, seasons, and any size or gear restrictions before you fish.*
- Retrieval (union) passed: True
- Correctness passed: True

### S5 (single_fact) — 1 tool call(s), 13.922s
- Question: Per the tackle notes, how many lake sturgeon can an angler typically keep under most Quebec zones' possession limit?
  - search_regs(query='lake sturgeon possession limit', species='lake sturgeon', zone=None) -> ['species_tackle.md#Lake sturgeon (esturgeon jaune)', 'species_tackle.md#Atlantic salmon & landlocked salmon (saumon atlantique / saumon confiné)', 'species_tackle.md#Lake trout (touladi) & brook trout (omble de fontaine)']
- Answer: According to the tackle notes, most Quebec zones set a very low possession limit for lake sturgeon—usually **one fish per angler**.

*Always double‑check the current regulations before you go fishing, as limits can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### S6 (single_fact) — 1 tool call(s), 14.437s
- Question: What is the name of the dataset the consumption-advisory numbers in this app come from?
  - search_regs(query='dataset name consumption advisory numbers', species=None, zone=None) -> ['regulations_overview.md#Where the numbers in this app come from', 'regulations_overview.md#Consumption advisories are a different question', 'regulations_overview.md#Waterbody-specific exceptions']
- Answer: The consumption‑advisory numbers shown in the app come from the **Données Québec “Guide de consommation du poisson de pêche sportive en eau douce”** dataset.  

*Please verify the current advisory values before eating fish, as guidelines can be updated.*
- Retrieval (union) passed: True
- Correctness passed: True

### C1 (conversational) — 1 tool call(s), 13.163s
- Question: My buddy mentioned there's an example in the app about keeping walleye only within a certain size window -- what's that size range?
  - search_regs(query='walleye minimum size maximum size window', species='walleye', zone=None) -> ['regulations_overview.md#What a "limit" usually includes', 'species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#Consumption advisories are a different question']
- Answer: The example shown in the app uses a **length‑based “slot” limit of 37 cm – 53 cm (inclusive)** for walleye (e.g., Zone 27).  

*Keep only walleye that fall within that size window; fish smaller than 37 cm or larger than 53 cm must be released.*  

**Reminder:** Size limits can vary by zone and may be updated. Always verify the current regulations for the specific waterbody you’re fishing before keeping any walleye.
- Retrieval (union) passed: True
- Correctness passed: True

### C2 (conversational) — 1 tool call(s), 14.751s
- Question: Does my 11-year-old need their own fishing licence to fish with me in Quebec?
  - search_regs(query='licence minor under 12 fishing Quebec', species=None, zone=None) -> ['regulations_overview.md#Licensing', 'species_tackle.md#Yellow perch (perchaude) & black crappie (marigane noire)', 'regulations_overview.md#This is a plain-language summary to help anglers understand how Quebec fishing']
- Answer: In Quebec, a sport‑fishing licence (permit) is required only for anglers **12 years of age or older**. Therefore an 11‑year‑old does **not** need to obtain their own licence to fish with you.

*Remember to verify the current regulations before you head out, especially if you plan to fish on a designated free‑fishing day or in a special zone.*
- Retrieval (union) passed: True
- Correctness passed: True

### C3 (conversational) — 1 tool call(s), 10.544s
- Question: I landed a huge sturgeon in Quebec -- how many of those am I typically allowed to bring home?
  - search_regs(query='catch limit lake sturgeon', species='Lake Sturgeon', zone=None) -> ['species_tackle.md#Lake sturgeon (esturgeon jaune)', 'species_tackle.md#Editorial notes on how anglers commonly target these species in Quebec. This', 'species_tackle.md#Atlantic salmon & landlocked salmon (saumon atlantique / saumon confiné)']
- Answer: In Quebec most zones set the **possession limit for lake sturgeon (esturgeon jaune) at one fish** – you may keep a single sturgeon and must release any additional ones you catch.

*Always double‑check the current zone‑specific regulation before you keep a sturgeon, as limits can vary and may be changed.*
- Retrieval (union) passed: True
- Correctness passed: True

### C4 (conversational) — 2 tool call(s), 20.418s
- Question: Someone told me muskie have a really strict gear rule -- is that actually true?
  - search_regs(query='gear restrictions muskellunge', species='Muskellunge', zone=None) -> ['species_tackle.md#Muskellunge (maskinongé)']
  - search_regs(query='tackle restrictions muskellunge gear', species='Muskellunge', zone=None) -> ['species_tackle.md#Muskellunge (maskinongé)', 'species_tackle.md#Lake sturgeon (esturgeon jaune)']
- Answer: The regulations for **Muskellunge (maskinongé)** do not list a special gear restriction.  The notes mention that muskies are a low‑density, high‑effort target and that they “often carry a low daily limit and an angling‑only restriction in Quebec zones.”  No specific prohibition on lure type, line class, or hook size is stated in the regulation excerpt we retrieved.

*Remember to verify the current regulations (daily limit, possession limits, any zone‑specific rules) before you head out, as rules can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### T1 (two_hop) — 2 tool call(s), 26.228s
- Question: What's the example length range for walleye in the tackle notes, and separately, how many lake sturgeon can I typically keep per those same notes?
  - search_regs(query='example length range walleye tackle notes', species='walleye', zone=None) -> ['species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#What a "limit" usually includes', 'species_tackle.md#Editorial notes on how anglers commonly target these species in Quebec. This']
  - search_regs(query='lake sturgeon tackle notes keep per day', species='lake sturgeon', zone=None) -> ['species_tackle.md#Lake sturgeon (esturgeon jaune)', 'species_tackle.md#Editorial notes on how anglers commonly target these species in Quebec. This', 'species_tackle.md#Atlantic salmon & landlocked salmon (saumon atlantique / saumon confiné)']
- Answer: **Walleye (doré jaune)** – The tackle notes give an example of a length‑based “slot” limit: **37 cm to 53 cm** (illustrated for Zone 27).

**Lake sturgeon (esturgeon jaune)** – The notes state that most Quebec zones impose a very low possession limit, **often just one** lake sturgeon per angler.  

*Remember to verify the current zone‑specific limits and any seasonal or consumption advisories before you fish.*
- Retrieval (union) passed: True
- Correctness passed: True

### T2 (two_hop) — 1 tool call(s), 13.804s
- Question: Are both muskellunge and lake sturgeon restricted to angling-only gear in the tackle notes?
  - search_regs(query='angling only gear', species='Muskellunge', zone=None) -> ['species_tackle.md#Muskellunge (maskinongé)', 'species_tackle.md#Lake sturgeon (esturgeon jaune)', 'regulations_overview.md#What a "limit" usually includes']
- Answer: Yes. In the Quebec tackle notes both **Muskellunge (maskinongé)** and **Lake sturgeon (esturgeon jaune)** are listed with an **angling‑only restriction** (i.e., only rod‑and‑line methods are permitted).

* Muskellunge – “often carry … an angling‑only restriction in Quebec zones.”  
* Lake sturgeon – “most Quebec zones apply … an angling‑only restriction.”

Be sure to check the specific zone’s current regulations before you fish, as limits, possession rules, and any seasonal closures can change. Always verify the latest rules on quebec.ca or within the OMyFish app.
- Retrieval (union) passed: True
- Correctness passed: True

### T3 (two_hop) — 1 tool call(s), 12.316s
- Question: Do I need a licence at age 10, and is a consumption advisory the same thing as a legal catch limit?
  - search_regs(query='minimum age for licence', species=None, zone=None) -> ['regulations_overview.md#Licensing', 'regulations_overview.md#What a "limit" usually includes', 'regulations_overview.md#Fishing zones']
- Answer: **Licence requirement**

- A valid Québec sport‑fishing licence (permit) is required for anyone **12 years of age or older**.  
- Children under 12 (e.g., a 10‑year‑old) may fish without a licence, except on the few **designated free‑fishing days** when anyone may fish licence‑free.

**Consumption advisory vs. legal limit**

- A **consumption advisory** is a health recommendation about how much of a species (or species group) may be safely eaten, based on contaminants or other health concerns.  
- It is **not** a **legal catch/possession limit**. The catch limit tells you how many fish you may keep per day; the consumption advisory tells you how many of those kept fish you should eat.

*Always double‑check the current regulations and any health advisories before you head out, as limits and advisories can change.*
- Retrieval (union) passed: False
- Correctness passed: False — missing: ['separate']

### T4 (two_hop) — 2 tool call(s), 28.606s
- Question: What's the walleye example length range in the tackle notes, and when do largemouth and smallmouth bass typically spawn?
  - search_regs(query='example length range walleye tackle notes', species='walleye', zone=None) -> ['species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#What a "limit" usually includes', 'species_tackle.md#Editorial notes on how anglers commonly target these species in Quebec. This']
  - search_regs(query='spawning period largemouth bass Quebec', species='largemouth bass', zone=None) -> ['species_tackle.md#Largemouth bass (achigan à grande bouche) & smallmouth bass (achigan à petite bouche)', 'regulations_overview.md#What a "limit" usually includes', 'regulations_overview.md#Licensing']
- Answer: **Walleye** – The tackle‑note example of a length‑based “slot” limit is **37 cm to 53 cm** (illustrated for Zone 27).  

**Largemouth and smallmouth bass** – Both species typically spawn in shallow water during **late spring, roughly May – June**, with the exact timing dependent on water temperature.

*Always verify the current zone‑specific limits, seasons and any consumption advisories before you head out.*
- Retrieval (union) passed: True
- Correctness passed: True

### E1 (exact_term) — 1 tool call(s), 13.135s
- Question: What length range applies as an example slot limit for doré jaune in Zone 27?
  - search_regs(query='example slot limit length range yellow walleye zone 27', species='yellow walleye', zone='27') -> ['species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#Fishing zones', 'regulations_overview.md#What a "limit" usually includes']
- Answer: In Zone 27, the example slot‑limit for doré jaune (walleye) is a protected length range of **37 cm to 53 cm** (inclusive).  

*Always double‑check the current regulations before you fish, as limits can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### E2 (exact_term) — 2 tool call(s), 28.373s
- Question: Is northern pike restricted to angling-only gear with a low daily limit, or does that apply to a different toothy predator?
  - search_regs(query='northern pike gear restriction angling only', species='northern pike', zone=None) -> ['species_tackle.md#Northern pike (grand brochet)', 'species_tackle.md#Lake sturgeon (esturgeon jaune)', 'species_tackle.md#Muskellunge (maskinongé)']
  - search_regs(query='northern pike daily limit possession limit gear restriction', species='northern pike', zone=None) -> ['species_tackle.md#Northern pike (grand brochet)', 'species_tackle.md#Lake sturgeon (esturgeon jaune)', 'species_tackle.md#Muskellunge (maskinongé)']
- Answer: Northern pike (grand brochet) are **not** listed with an angling‑only gear restriction or a low daily limit in the regulations. The “low daily limit + angling‑only” rule is applied to other toothy predators, notably **muskellunge (maskinongé)**, which “often carry a low daily limit and an angling‑only restriction in Quebec zones”【3†id=species_tackle.md#Muskellunge (maskinong%C3%A9)】. (Lake sturgeon also have a very low possession limit and an angling‑only rule, but they are not a pike‑type predator.)  

**Bottom line:** the restriction you’re thinking of belongs to muskellunge, not northern pike.  

*Always double‑check the current Quebec regulations before keeping any fish, as limits and gear rules can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### O1 (out_of_scope) — 2 tool call(s), 19.345s
- Question: What is the current price of a non-resident annual fishing licence in Quebec?
  - search_regs(query='non-resident annual fishing licence price', species=None, zone=None) -> ['regulations_overview.md#Licensing', 'regulations_overview.md#Fishing zones', 'regulations_overview.md#What a "limit" usually includes']
  - search_regs(query='annual non-resident sport-fishing licence fee', species=None, zone=None) -> ['regulations_overview.md#Licensing', 'regulations_overview.md#This is a plain-language summary to help anglers understand how Quebec fishing', 'regulations_overview.md#Fishing zones']
- Answer: The regulation database does not list a specific price for a non‑resident annual sport‑fishing licence. It notes that non‑residents pay a different fee than Quebec residents and that the current fee must be obtained from the official Québec government site ( quebec.ca ) or the app’s live Regs lookup.

**Reminder:** Always verify the current licence fee (and any other legal requirements) on the official website before purchasing or fishing.
- Retrieval (union) passed: None
- Correctness passed: False — missing: ['<decline/unknown phrasing>']

### O2 (out_of_scope) — 1 tool call(s), 12.218s
- Question: How many sport-fishing licences were sold in Quebec last year?
  - search_regs(query='number of sport-fishing licences sold last year Quebec', species=None, zone=None) -> ['regulations_overview.md#Licensing', 'regulations_overview.md#This is a plain-language summary to help anglers understand how Quebec fishing', 'regulations_overview.md#Consumption advisories are a different question']
- Answer: I’m sorry—I couldn’t find any information in the regulation database about how many sport‑fishing licences were sold in Quebec last year. For the most accurate and up‑to‑date statistics, please consult the Government of Québec’s official reports or the quebec.ca website. Always verify current regulations before you head out fishing.
- Retrieval (union) passed: None
- Correctness passed: True

### H1 (compound) — 2 tool call(s), 23.593s
- Question: If I hook a big lake trout in summer, how deep should I be fishing, and can I keep more than one lake sturgeon the same day?
  - search_regs(query='depth summer lake trout', species='lake trout', zone=None) -> ['species_tackle.md#Lake trout (touladi) & brook trout (omble de fontaine)', 'species_tackle.md#Atlantic salmon & landlocked salmon (saumon atlantique / saumon confiné)', 'species_tackle.md#Rainbow trout (truite arc-en-ciel)']
  - search_regs(query='lake sturgeon catch limit per day', species='lake sturgeon', zone=None) -> ['species_tackle.md#Lake sturgeon (esturgeon jaune)', 'regulations_overview.md#Fishing zones', 'species_tackle.md#Editorial notes on how anglers commonly target these species in Quebec. This']
- Answer: **Depth for a summer lake‑trout bite**  
In Quebec lakes, lake trout typically hold deep during the warm months, often **15 – 30 m (about 50 – 100 ft) down along the thermocline**. Targeting them with deep‑jigging gear or down‑rigger trolling at those depths gives the best chance of hooking a big specimen.

**Lake‑sturgeon possession limit**  
Most Quebec fishing zones apply a **very low possession limit for lake sturgeon – usually one fish per angler per day** (and sometimes an angling‑only restriction). Therefore, you normally cannot keep more than one lake sturgeon on the same day; the limit may vary by specific zone, so always check the zone‑specific table.

*Reminder: regulations (season dates, depth recommendations, possession limits) can change and may differ by zone. Verify the current rules for the waterbody you’ll fish before heading out.*
- Retrieval (union) passed: True
- Correctness passed: True

### H2 (compound) — 2 tool call(s), 2.194s
- Question: Does my 9-year-old need a fishing license, and is there a size range I'd have to release a walleye within?
  - search_regs(query='licence requirement minor age 9', species=None, zone=None) -> ['regulations_overview.md#Licensing']
  - search_regs(query='walleye release size range', species='walleye', zone=None) -> ['species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#What a "limit" usually includes', 'species_tackle.md#Northern pike (grand brochet)']
- Answer: **Licence for a 9‑year‑old**  
A Quebec sport‑fishing licence (permit) is required for anyone **12 years of age or older**. Children younger than 12 – such as a 9‑year‑old – do not need a licence (except on the few designated free‑fishing days).

**Walleye size‑release rule**  
In many Quebec zones walleye are subject to a **length‑based “slot” limit**. A typical example is a slot of **37 cm – 53 cm** (the fish must be released if its total length falls within that range). The exact slot size varies by zone, so you should check the regulation for the specific zone you’ll be fishing in.

*Always verify the current licence requirements, slot limits and any other regulations for your zone before you head out.*
- Retrieval (union) passed: True
- Correctness passed: True

### H3 (compound) — 2 tool call(s), 3.192s
- Question: What lures should I throw for muskie, and are rainbow trout easier to catch right when the ice goes out?
  - search_regs(query='recommended artificial lures for muskellunge', species='Muskellunge', zone=None) -> ['species_tackle.md#Muskellunge (maskinongé)', 'regulations_overview.md#Licensing', 'regulations_overview.md#What a "limit" usually includes']
  - search_regs(query='rainbow trout activity ice-out period', species='Rainbow trout', zone=None) -> ['species_tackle.md#Rainbow trout (truite arc-en-ciel)', 'species_tackle.md#Lake trout (touladi) & brook trout (omble de fontaine)', 'regulations_overview.md#What a "limit" usually includes']
- Answer: **Muskellunge (muskie)**  
- The regulations note that the most effective artificial baits are **large bucktails, glide baits, and jerkbaits**.  
- Use an **erratic retrieve** – a figure‑eight motion with the lure at the boat’s side on each retrieve – to provoke strikes.

**Rainbow trout**  
- In stocked lakes, rainbow trout are reported to be **more active and bite readily just after ice‑out**. They tend to stay shallow and respond well to **small spoons, spinners, and controlled flies** during this period. As the water warms, they move deeper.

*Remember to check the latest Quebec regulations (season dates, catch/possession limits, and any gear restrictions) before you head out, especially for muskellunge, which often has low daily limits and an “angling‑only” rule in many zones.*
- Retrieval (union) passed: True
- Correctness passed: True

### H4 (compound) — 1 tool call(s), 2.136s
- Question: Is sturgeon fishing just worms on the bottom, and do largemouth bass spawn around the same time as smallmouth?
  - search_regs(query='sturgeon bait method bottom worms', species='sturgeon', zone=None) -> ['species_tackle.md#Lake sturgeon (esturgeon jaune)', 'species_tackle.md#Walleye (doré jaune)', 'species_tackle.md#Largemouth bass (achigan à grande bouche) & smallmouth bass (achigan à petite bouche)']
- Answer: **Sturgeon** – In Quebec, lake sturgeon are classified as bottom‑feeders. Anglers target them with **heavy tackle and bottom‑presented bait such as worms, leeches, or cut bait**, fished directly on the bottom of deep river channels or lake basins. “Sight‑casting” isn’t typical for this species.

**Bass spawning** – Both **largemouth bass (achigan à grande bouche)** and **smallmouth bass (achigan à petite bouche)** spawn in shallow water during **late‑spring (approximately May – June, depending on water temperature)**. Their spawning periods therefore largely overlap.

*Remember to verify the current possession limits, season dates, and any local advisories before you head out, as regulations can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### H5 (compound) — 2 tool call(s), 2.097s
- Question: Do I need to worry about handling lake trout gently in hot weather, and can perch be caught through the ice?
  - search_regs(query='lake trout handling temperature hot weather', species='lake trout', zone=None) -> ['species_tackle.md#Lake trout (touladi) & brook trout (omble de fontaine)', 'species_tackle.md#Rainbow trout (truite arc-en-ciel)', 'species_tackle.md#Atlantic salmon & landlocked salmon (saumon atlantique / saumon confiné)']
  - search_regs(query='perch ice fishing', species='perch', zone=None) -> ['species_tackle.md#Yellow perch (perchaude) & black crappie (marigane noire)', 'regulations_overview.md#Fishing zones', 'regulations_overview.md#Licensing']
- Answer: **Lake trout (touladi)** – The species is a cold‑water specialist. In warm summer water it is especially sensitive to heat stress, so it should be handled gently and released promptly; playing the fish for a long time can increase mortality.

**Perch (perchaude)** – Ice fishing for perch is a common and productive practice in Quebec; the fish remain active and feed under the ice, so they can be caught through the ice.

*Always verify the current regulations, licence requirements and any zone‑specific limits before you head out, especially for catch‑limit or consumption advisories.*
- Retrieval (union) passed: True
- Correctness passed: True

### CMP1 (compare) — 1 tool call(s), 1.349s
- Question: Do largemouth and smallmouth bass like the same kind of cover and water, or are they pretty different?
  - search_regs(query='habitat preferences cover water type', species='largemouth bass', zone=None) -> ['species_tackle.md#Largemouth bass (achigan à grande bouche) & smallmouth bass (achigan à petite bouche)', 'species_tackle.md#Lake trout (touladi) & brook trout (omble de fontaine)', 'species_tackle.md#Rainbow trout (truite arc-en-ciel)']
- Answer: **Habitat & cover**

* **Largemouth bass (achigan à grande bouche)** – Prefer *heavier* cover such as weed beds, docks and fallen timber. They tend to hold in more vegetated, slower‑moving water.

* **Smallmouth bass (achigan à petite bouche)** – Prefer *rockier, clearer* water with some current. They are often found near rocky points, drop‑offs and riffles.

**Bottom line:** Their preferred cover and water types are not the same. Largemouth bass gravitate toward dense, vegetated structure, while smallmouth bass are more associated with rocky, flowing habitats.

*Always verify the current regulations and any seasonal or consumption advisories before you head out.*
- Retrieval (union) passed: True
- Correctness passed: True

### CMP2 (compare) — 1 tool call(s), 11.987s
- Question: Are walleye and northern pike active at the same times of day, or does one bite better at night?
  - search_regs(query='activity period time of day walleye', species='walleye', zone=None) -> ['species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#What a "limit" usually includes', 'species_tackle.md#Northern pike (grand brochet)']
- Answer: **Walleye (doré jaune)** – The species feeds most actively at **dawn, dusk and after dark**. Anglers usually target them during those low‑light periods and they tend to stay deeper and near structure when the sun is high.

**Northern pike (grand brochet)** – Pike are “aggressive and often catchable **through the heat of the day**,” meaning they tend to bite best in bright daylight rather than at night. They are especially active early in the season (right after ice‑out and around spawning), but their peak activity is generally during daytime hours.

**Bottom line**  
- Walleye: best during low‑light (dawn, dusk, night).  
- Northern pike: best during daylight, especially warm midday periods.

*Always verify the current regulations and any seasonal or size limits before you head out, as rules can change.*
- Retrieval (union) passed: True
- Correctness passed: True

### CMP3 (compare) — 1 tool call(s), 1.85s
- Question: Are lake trout and brook trout both the kind of fish that get stressed out if you fight them too long on a hot day?
  - search_regs(query='stress prolonged fight hot day lake trout', species='lake trout', zone=None) -> ['species_tackle.md#Lake trout (touladi) & brook trout (omble de fontaine)', 'species_tackle.md#Rainbow trout (truite arc-en-ciel)', 'species_tackle.md#Atlantic salmon & landlocked salmon (saumon atlantique / saumon confiné)']
- Answer: Yes. Both lake trout (touladi) and brook trout (omble de fontaine) are cold‑water specialists and are noted as being **sensitive to summer heat stress if played (fought) too long before release**.  

*When fishing on a hot day, try to keep the fight brief and release the fish promptly to minimize stress.*

*Always verify the most current regulations and any handling guidelines before you fish.*
- Retrieval (union) passed: True
- Correctness passed: True

### W1 (premise_check) — 1 tool call(s), 2.44s
- Question: Since walleye and pike are basically the same fish, is the slot limit example the same for both?
  - search_regs(query='slot limit walleye', species='walleye', zone=None) -> ['species_tackle.md#Walleye (doré jaune)', 'regulations_overview.md#What a "limit" usually includes', 'species_tackle.md#Northern pike (grand brochet)']
- Answer: The slot‑limit example you saw applies to **walleye** – many Quebec zones (for example Zone 27) use a length‑based “slot” such as 37 cm to 53 cm inclusive【0†L4-L7】.  

**Northern pike** do not have a slot‑limit provision in the excerpts we retrieved; their regulations are described in terms of fishing tactics and season, but no slot‑limit is mentioned【0†L9-L12】.  

Therefore, the slot‑limit example is **not** the same for pike as it is for walleye.  

*Always verify the current regulations for the specific zone you plan to fish, as limits and size requirements can vary.*
- Retrieval (union) passed: True
- Correctness passed: False — missing: ['different species', 'different fish', 'not the same species', 'two different', 'walleye only', 'only walleye', 'specific to walleye', 'mention a slot limit', 'mention any slot limit', 'only for walleye']

### W2 (premise_check) — 1 tool call(s), 2.465s
- Question: Quebec regulations say I can only fish with artificial lures, right? No live bait allowed anywhere?
  - search_regs(query='use of live bait fish prohibited artificial lures only', species=None, zone=None) -> ['species_tackle.md#Lake sturgeon (esturgeon jaune)', 'regulations_overview.md#What a "limit" usually includes', 'regulations_overview.md#Consumption advisories are a different question']
- Answer: No. Quebec’s fishing rules do **not** impose a province‑wide ban on live bait.  

* The regulations are written per‑species and per‑zone, and the “fishing device” clause can either **allow** or **restrict** the use of live bait fish (worms, leeches, cut‑bait, etc.) depending on the target species and the zone.  
* For example, the entry for **lake sturgeon** explicitly states that anglers may use **live bait such as worms, leeches, or cut bait** fished on the bottom — so live bait is permitted for that species in the zones where sturgeon are regulated.  

In many other zones the “fishing device” part simply limits the method (e.g., angling‑only) but does **not** forbid live bait. Only a few specific species or zones may require artificial lures only; you need to check the exact entry for the waterbody and species you intend to target.

**Bottom line:** Live bait is allowed in many Quebec zones; the “artificial lures only” rule applies only where a particular regulation explicitly states that restriction.

*Always verify the current regulations for the specific waterbody, species, and zone before you head out, as limits and device rules can change.*
- Retrieval (union) passed: False
- Correctness passed: True

### V1 (vague) — 0 tool call(s), 0.843s
- Question: What's the catch limit for my favorite fish?
- Answer: I’m happy to help, but I need to know which species you’re asking about. Could you let me know the name of the fish (or the zone you’ll be fishing in) so I can look up the correct catch‑limit information?
- Retrieval (union) passed: False
- Correctness passed: True

### V2 (vague) — 0 tool call(s), 39.206s
- Question: Can I keep a legal walleye around here?
- Answer: I’m sorry—I can’t tell you the walleye possession limit without knowing the specific fishing zone you’re in. The limits (season dates, daily catch limits, size limits, etc.) vary by zone, so please let me know the name or number of the zone you’re fishing in, and I’ll look up the exact regulation for you.

*Always double‑check the current regulations before you fish, as limits can change.*
- Retrieval (union) passed: False
- Correctness passed: True

