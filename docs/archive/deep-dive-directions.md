# Deep Dive: Existing Efforts, Gaps, and Strategic Directions

*Detailed landscape analysis and project direction options.*

## What Already Exists (and Where the Gaps Are)

### Databases of Chinese Government Documents

- **China Horizons (Copenhagen Business School / MERICS consortium)** — the closest direct comparable. Free database of central-level policy documents from the State Council, Central Committee, and their general offices, covering 2018-2025. But it's *central-level only* — doesn't cover provincial/prefecture/county documents, doesn't include news releases or speeches, and doesn't editorialize about what matters. It's a catalogue, not a curated guide.
- **DigiChina (Stanford)** — translates and analyzes Chinese tech policy documents specifically. Very focused on digital governance, AI, data privacy. High quality but narrow.
- **ChinaLawTranslate.com** — crowdsourced translations of legal texts. Narrow: law only.
- **ChinaFile's "State of Surveillance"** — a model of systematic data-driven work: they scraped ~76,000 government procurement notices and did quantitative analysis on surveillance spending patterns across regions. This is the kind of "systematic + humanistic" synthesis that's missing elsewhere.
- **Peking University's Chinalawinfo (北大法宝)** — most comprehensive Chinese legal database but primarily in Chinese, expensive, and oriented toward legal professionals.

### The Newsletter/Commentary Ecosystem

**Tier 1 (institutional influence):**
- Bill Bishop's *Sinocism* (400K+ subscribers, $20/month, the "presidential daily brief for China hands")
- Jordan Schneider's *ChinaTalk* (podcast + newsletter, tech/policy focus)
- CSIS *Pekingology* podcast (Henrietta Levin, formerly Jude Blanchette)

**Tier 2 (analyst-driven):**
- Zichen Wang's *Pekingnology* (translates and contextualizes Chinese-language sources, view closer to Beijing's perspective)
- Asia Society's *Center for China Analysis* newsletter
- Drew Thompson's Substack (security/Taiwan focus)
- Sarah Cook's *UnderReported China* (human rights/censorship)

**Tier 3 (topical/cultural):**
- Lauren Teixeira (culture/society)
- Jeremy Goldkorn's *The China Week* (media/business)
- *What's Happening in China* (weekly brief)
- Fred Gao's *Inside China* (youth culture/society)

### Critical Observation

MERICS published a report specifically about how the online availability of key information on contemporary China is under threat. The government is becoming less forthcoming in sharing information while requiring third-party data providers to restrict foreign access. Policy transparency from the State Council peaked around 2015 and has been declining systematically since, falling from about 88 to 68 percent publication of top-level documents by 2022. This information drought is pushing the field toward narrative journalism by necessity — fewer data points means less systematic analysis is possible.

### Academic Side

There IS a quantitative political science literature on Chinese governance, but it's quite specialized:
- **David Yang et al.** (*Journal of Political Economy*, 2025): Collected 19,812 government documents on policy experimentation in China between 1980 and 2020. Constructed a database of 633 policy experiments initiated by 98 central ministries.
- **Sebastian Heilmann**: "Experimentation under hierarchy" framework for understanding Chinese policy-making.
- **Gunter Schubert and Anna Lisa Ahlers** (Tübingen/Oslo): Local policy implementation fieldwork.
- **Kevin O'Brien** (Berkeley): Local governance.

This work is mostly published in academic journals and almost never reaches the newsletter/Substack audience.

---

## Four Strategic Directions

### Direction 1: "The Economist Intelligence Unit for Chinese Domestic Policy, but open-source and opinionated"

- **Audience:** Policy professionals, think tank analysts, business strategists who need to track what Chinese government priorities actually are at a level of specificity beyond "Xi said tech is important." People at MERICS, CSIS, Brookings, corporate government affairs teams at multinationals operating in China.
- **What it does:** Takes the raw document flow and adds editorial layers — what's signal vs. noise, what's a real policy shift vs. boilerplate, how does a provincial directive relate to the central document it's implementing? The opinionated curation is the key differentiator. China Horizons catalogs; we would *interpret*.
- **Why it matters now:** As MERICS documents, transparency is declining. Archiving and contextualizing what IS published becomes more valuable as the window narrows.
- **Risk:** Competes with Sinocism, which already does curated daily links with commentary. Differentiation would need to be the *database structure* (searchable, relational, cross-referencing across levels of government) rather than just commentary.

### Direction 2: "Vertical-to-horizontal translator" — making the multi-level structure of Chinese governance legible

- **Audience:** Political scientists, comparative politics scholars, grad students, and the "China-curious" policy wonk who doesn't read Chinese but wants to understand *how* China governs, not just *what* it says.
- **What it does:** The unique structural contribution of the database — showing connections between layers (central -> provincial -> prefecture -> county) and across regions at the same layer — is something nobody does well. When the State Council issues a directive, how does implementation vary across Guangdong vs. Gansu? The database could make this visible.
- **Why it's underserved:** The Yang et al. paper shows the academic appetite — they manually linked 19,812 documents across administrative levels. That's the kind of thing a well-structured database would make dramatically easier. Schubert and Ahlers do fieldwork-based studies of local implementation but explicitly note how hard it is to systematically compare across regions.
- **Concrete product:** Pick 3-5 specific policy domains (education, environmental regulation, tech subsidies, housing) and build the vertical chain for each.

### Direction 3: "Humanizing China" for a general American audience

- **Audience:** Educated non-specialists who consume *The Atlantic*, *Vox*, podcasts like *ChinaTalk* or *Ezra Klein*. People who know China matters but whose mental model is either "authoritarian surveillance state" or "economic miracle" with nothing in between.
- **What it does:** Uses government documents as entry points for human stories. A county health department's announcement about rural clinic consolidation becomes a lens into rural healthcare access. A prefecture's vocational education initiative becomes a story about what young people outside tier-1 cities actually do.
- **Why it matters:** Government documents from lower-level administrations reveal what *officials in Zunyi or Baoding* care about, which is often mundane governance — road maintenance, school nutrition, elderly care — and that mundanity is itself the humanizing force.
- **Risk:** Hardest to monetize. The audience is large but diffuse and not accustomed to paying for this kind of content.

### Direction 4: "Policy evaluation infrastructure" for academic researchers

- **Audience:** Quantitative social scientists who study Chinese governance, development economists.
- **What it does:** Rather than producing analysis, produces *infrastructure* — a structured, searchable, tagged database that researchers can query. Think of it like WRDS or FRED but for Chinese government activity. If a researcher wants to study how environmental enforcement varies by province, they could query the database for environmental policy documents across regions and time.
- **Why it's needed:** The Yang et al. paper took enormous effort to build their dataset manually. If this database existed, their data collection phase collapses from years to weeks. The Becker Friedman Institute summary emphasizes that the dataset construction itself was a major contribution — which tells you there's demand for the infrastructure.
- **Risk:** Building to academic standards requires comprehensive coverage and careful metadata, which is expensive and slow. But if done right, it becomes a cited resource that sustains itself.

---

## Key People at the Cutting Edge

- **Jessica Batke** (ChinaFile, now GPPi): Did the systematic, data-driven approach to Chinese government documents (surveillance procurement project). Methodological model.
- **Nis Grunberg** (MERICS): Lead analyst on Chinese governance/party-state politics. Co-authored the piece on disappearing Chinese data.
- **Kasper Ingeman Beck** (Copenhagen Business School): Built the China Horizons policy documents database. Literally the closest existing project.
- **David Yang** (Harvard Economics): Most prominent quantitative researcher using Chinese government documents as data for political economy research.
- **Sebastian Heilmann** (Trier University, formerly MERICS): Coined "experimentation under hierarchy." His work is the theoretical backbone for why a database like this is useful.
- **Gunter Schubert** (Tubingen): Does granular, multi-level fieldwork on local policy implementation that a systematic database would complement.
- **Emily Hannum** (Penn): Did rigorous quantitative work on school consolidation using village-level data — a model for what becomes possible with good sub-national data.

---

## Recommended Focus

Start with **Direction 2 as content, with Direction 4 as the long-term structural aspiration**. Concretely: pick one policy domain, build out the vertical chain from central to county for a few provinces, write it up as a series, and use that as the proof of concept that demonstrates what the database *could* be. That gives:

1. Something publishable quickly
2. Something the academic community would notice
3. A concrete artifact to show people when explaining the larger vision

The person to talk to: **Kasper Ingeman Beck at CBS** — he's built the closest thing to this and would know exactly where the pain points and opportunities are.
