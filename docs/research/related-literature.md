# Related Literature

Reference list of recent working papers, preprints, and landmark articles on Chinese governance. The emphasis is methods our corpus could replicate, extend, or provide a China comparison to. Our corpus: ~319,000 Chinese government documents, central through district, 2000 to 2026, with a resolved citation graph (~280k edges; 287,607 resolved on 2026-10-01, corrected from "~248k"), document dates, admin levels, issuers, and genre/doc-type tags.

House rules for this file. Every row carries its citation. Papers listed were found via web search on 2026-10-01. Where a claim is uncertain it is marked. The literature below is a working bibliography, not an endorsement of each paper's findings.

"Corpus fit" ratings: **A = run a real replication or novel China-at-scale version now** (our data is the same shape or better); **B = strong extension or comparison**; **C = framework or method we borrow, data differs**.

---

## 1. Text-as-data on policy documents at scale (the direct comparators)

These are the papers whose data is the same shape as ours. Two of them built corpora of 3+ million policy documents across central, provincial, and city levels. That is the exact object we hold, at a comparable scale, with the addition of a resolved citation graph and district-level depth.

| Paper | Venue / no. | Year | Question + method | Corpus fit |
|---|---|---|---|---|
| **Laboratories of Autocracy: Landscape of Central-Local Dynamics in China's Policy Universe** (Luo, Wang, Yang) | NBER w34219 | 2025 | Did Chinese policymaking centralize? Builds a corpus of 3.7M policy documents and government work reports over ~20 years, identifies 115,679 distinct policies, and tracks initiation and diffusion. Finds a shift from decentralized to centralized after ~2013 (bottom-up innovation no longer rewarded). [nber.org/papers/w34219](https://www.nber.org/papers/w34219) | **A** |
| **Decoding China's Industrial Policies** (Fang, Li, Lu) | NBER w33814 | 2025, rev. 2026 | Classifies industrial policy 2000-2022 from 3.3M central/provincial/city documents using LLMs with multistage extraction and verification. Extracts targeted industries, policy tone (supportive vs regulatory), and tools. Identifies a 2013 recentralization turning point. [nber.org/papers/w33814](https://www.nber.org/papers/w33814) | **A** |
| **Policy Experimentation in China: the Political Economy of Policy Learning** (Wang, Yang) | NBER w29402 / JPE 2025 | 2021 | Assembles a comprehensive dataset of Chinese policy experiments since 1980. Finds >80% of experiments have positive sample selection on local development, and that strategic local effort is not replicable at national rollout, distorting policy learning. [nber.org/papers/w29402](https://www.nber.org/papers/w29402) | **B** |
| **Text as Data: A New Framework for Machine Learning and the Social Sciences** (Grimmer, Roberts, Stewart); earlier **Text as Data** (Grimmer, Stewart, Political Analysis 2013) | Princeton UP; Political Analysis 21:267 | 2022; 2013 | The reference method text for discovery, measurement, and causal inference from political documents. [semanticscholar.org](https://www.semanticscholar.org/paper/Text-as-Data:-The-Promise-and-Pitfalls-of-Automatic-Grimmer-Stewart/b9921fb4d1448058642897797e77bdaf8f444404) | **C** |
| **Text as Data** (Gentzkow, Kelly, Taddy) | J. Economic Literature 57(3):535 | 2019 | Survey of text methods for economics (dictionary, supervised, topic models, embeddings). Companion method: **Measuring Group Differences in High-Dimensional Choices** (Gentzkow, Shapiro, Taddy, Econometrica 2019) for partisan/issuer separation of speech. [aeaweb.org](https://www.aeaweb.org/articles?id=10.1257%2Fjel.20181020) | **C** |

Note on uniqueness. Luo-Wang-Yang and Fang-Li-Lu infer central-local linkage mostly from text similarity and co-occurrence. Our corpus carries an explicit resolved citation graph, so we can measure the directed "who cites whom" edge that they approximate. That is the single largest data advantage we hold over the direct comparators.

---

## 2. Policy diffusion (central to local) and citation networks

These papers operationalize diffusion with exactly the primitives our corpus exposes: document dates, issuer level, and inter-document references. They are typically built on a few thousand to ~34k documents from PKULaw or the China Legal Retrieval System. Our ~319k documents and ~280k resolved edges are an order of magnitude larger and go down to the district tier.

| Paper | Venue | Year | Question + method | Corpus fit |
|---|---|---|---|---|
| **Understanding China's Information Technology Policy System Through Policy Citation Networks** | Systems (MDPI) 14(8):957 | 2026 | Builds a policy citation network from 33,702 IT policy documents and 3,150 citation links from PKULaw. Spatio-temporal diffusion analysis. Citations recovered by matching quotation marks in body text. [mdpi.com](https://www.mdpi.com/2079-8954/14/8/957) | **A** |
| **A citation-based research framework for exploring policy diffusion: evidence from China's new energy policies** | Technological Forecasting & Social Change | 2022 | Constructs a policy citation network and defines diffusion indicators (speed, long-term and short-term impact). [sciencedirect.com](https://www.sciencedirect.com/science/article/abs/pii/S0040162522007946) | **A** |
| **Measuring policy diffusion intensity: a text-driven analysis of government documents** | Information Processing & Management | 2025 | A two-dimensional indicator (hierarchical effectiveness plus textual intensity), panel of 9,091 low-carbon policy documents 2007-2022. [sciencedirect.com](https://www.sciencedirect.com/science/article/abs/pii/S0306457325003243) | **A** |
| **Top-down pressure and bottom-up responses: provincial adoption and textual reproduction of sports industry policies** | (PMC open access) | 2025 | Word Embedding plus Word Mover's Distance to quantify how faithfully provinces reproduce central policy text. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC12672445/) | **B** |
| **AI policy in action: the Chinese experience in global perspective** | Journal of Policy Studies 40(2) | 2026 | Text mining and topic modeling of AI policy from the China Legal Retrieval System, May 2016 through 2024, read through central-local relations. [e-jps.org](https://www.e-jps.org/archive/view_article?pid=jps-40-2-1) | **B** |

---

## 3. Bureaucratic attention and agenda-setting

These papers measure what the state is paying attention to from official text, then test whether lower levels track higher-level signals. Our genre tags separate work reports, meeting readouts, and directives, and our dates plus admin levels let us build the same attention panels at far finer resolution.

| Paper | Venue | Year | Question + method | Corpus fit |
|---|---|---|---|---|
| **Aligning Agendas in Public-Activity Reports: Provincial Leaders and Central Signals in China, 2016-2022** | Journal of Chinese Political Science | 2026 | Topic models over 71,460 official public-activity releases to build shared issue agendas. Finds provincial issue shares track the General Secretary more than the Premier, and party secretaries respond to central directives more than governors. [link.springer.com](https://link.springer.com/article/10.1007/s11366-026-09946-9) | **A** |
| **The Rhythm of Government: Attention in China's Central- and Provincial-Level Executive Meetings** | Issues & Studies (Airiti) | 2024 | Distribution, stability, and transmission of attention across 2,840 executive meetings. An extra central mention of a policy area predicts more provincial mentions. [airitilibrary.com](https://www.airitilibrary.com/Article/Detail/P20181114001-N202403070013-00004) | **A** |
| **Impacts of government attention on achieving Sustainable Development Goals: evidence from China** | (ScienceDirect) | 2024 | Attention intensity, text similarity, and tone from Government Work Reports 2010-2020 by panel regression. [sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S2666683924000853) | **B** |

---

## 4. Central-local relations and fiscal/institutional frameworks

Framework pieces that define the central-local object. We cannot replicate their firm-level fiscal data, but our document corpus can test the textual predictions these frameworks imply (where authority sits, how it shifts).

- **The Fundamental Institutions of China's Reforms and Development** (Xu Chenggang), Journal of Economic Literature 49(4):1076, 2011. Defines China as a "regionally decentralized authoritarian" system: the center controls personnel, sub-national governments run the economy and initiate, implement, divert, and resist policy. [aeaweb.org](https://www.aeaweb.org/articles?id=10.1257%2Fjel.49.4.1076). Corpus fit **C** (framework; our data can show where document authority and citation flow actually sit).
- **Special Deals with Chinese Characteristics** (Bai, Hsieh, Song), NBER w25839 / NBER Macro Annual 2019. Local governments grant firm-specific "special deals"; competition limits predation. [nber.org/papers/w25839](https://www.nber.org/papers/w25839). Corpus fit **C**.

---

## 5. Policy experimentation and campaign-style governance

| Work | Venue | Year | Question + method | Corpus fit |
|---|---|---|---|---|
| **Experimentation under Hierarchy** (Heilmann) and **From Local Experiments to National Policy** | Studies in Comparative International Development; China Quarterly | 2008 | The mechanism of local trial "points" observed by the center and generalized if successful. Objectives stay central; instruments are experimental. [hks.harvard.edu](https://www.hks.harvard.edu/sites/default/files/centers/cid/files/publications/faculty-working-papers/172.pdf) | **B** |
| **Policy Experimentation under Pressure in Contemporary China** | China Quarterly | 2022 | Argues experimentation is now more hierarchized and centralized under Xi: trials must follow central guidelines and high-level approval. [cambridge.org](https://www.cambridge.org/core/journals/china-quarterly/article/policy-experimentation-under-pressure-in-contemporary-china/893EDDFDC60160404A1D2BEC0957E9C3) | **B** |
| **The Logic of Governance in China: An Organizational Approach** (Zhou Xueguang) | Cambridge UP | 2022 | Theory of oscillation between routine bureaucratic governance and campaign-style mobilization (suspension of normal rules, top-down directives, resource concentration). [cambridge.org](https://www.cambridge.org/core/books/abs/logic-of-governance-in-china/campaignstyle-mobilization-as-a-mechanism-of-governance/14B3F39038A21CAB82F5011EEB4C78E5) | **B** |

Corpus angle. Campaigns should show up as sharp, synchronized bursts in document volume and genre (directive, notice, action plan) across many issuers at once. Our dated, admin-tagged, genre-tagged corpus can detect campaign signatures and date their onset and decay directly.

---

## 6. Cadre incentives, promotion, and factions

These use digitized official biographies, not documents. Our corpus does not replicate them, but it can supply the policy-output side of the incentive story (what connected or tournament-pressured officials actually issue).

- **Political Turnover and Economic Performance: the Incentive Role of Personnel Control in China** (Li, Zhou), Journal of Public Economics, 2005. The GDP promotion tournament: provincial leaders' promotion rises with growth. [ralfmeisenzahl.com (PDF)](http://www.ralfmeisenzahl.com/uploads/7/6/8/1/76818505/li_zhou_incentive.pdf). Fit **C**.
- **Making Bureaucracy Work: Patronage Networks, Performance Incentives, and Economic Development in China** (Jiang), AJPS 62(4):982, 2018. Digitized resumes of 4,000+ officials; infers patron-client ties from who promoted whom; connected city leaders deliver better growth. [onlinelibrary.wiley.com](https://onlinelibrary.wiley.com/doi/abs/10.1111/ajps.12394). Fit **B** (we can join promotion ties to document output).
- **Getting Ahead in the Communist Party** (Shih, Adolph, Liu), APSR 106(1):166, 2012. Faction and patron ties predict Central Committee advancement more than GDP. [researchgate.net](https://www.researchgate.net/publication/259419739). Fit **C**.
- **Factions in Nondemocracies: Theory and Evidence from the Chinese Communist Party** (Francesco Trebbi and co-authors), NBER w22775 / Econometrica 91(2):565, 2023. Formal model plus elite biographical data on factional balancing. [nber.org (PDF)](https://www.nber.org/system/files/working_papers/w22775/w22775.pdf). Fit **C**.

---

## 7. Authoritarian responsiveness and consultation

- **Sources of Authoritarian Responsiveness: a Field Experiment in China** (Chen, Pan, Xu), AJPS 60(2), 2016. Online field experiment across 2,103 counties: threats of collective action and of tattling upward raise responsiveness; party loyalty signals do not. [onlinelibrary.wiley.com](https://onlinelibrary.wiley.com/doi/abs/10.1111/ajps.12207). Fit **C** (experimental; our corpus is observational).
- **Consultative Authoritarianism and Its Limits** (Truex), Comparative Political Studies 50(3):329, 2017, and **Making Autocracy Work** (Truex), Cambridge UP, 2016. "Representation within bounds" in the NPC. [rorytruex.com (PDF)](https://www.rorytruex.com/s/Truex-2017-Comparative-Political-Studies-Consultative-Authoritarianism-and-Its-Limits.pdf). Fit **C**.

---

## 8. Censorship, propaganda, and signaling

Mostly social-media and experimental data, but the signaling logic is testable on official text (tone, volume, synchronization).

- **How Censorship in China Allows Government Criticism but Silences Collective Expression** (King, Pan, Roberts), APSR, 2013, and **How the Chinese Government Fabricates Social Media Posts for Strategic Distraction** (same authors), APSR, 2017. Censorship targets collective-action potential, not criticism; the "50 cent" output distracts rather than argues. [ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2104894). Fit **C**.
- **Propaganda as Signaling** (Huang), 2015, and **The Pathology of Hard Propaganda** (Huang), Journal of Politics, 2018. Propaganda signals state strength and deters dissent rather than persuading. [almendron.com (PDF)](https://www.almendron.com/tribuna/wp-content/uploads/2020/03/propaganda-as-signaling.pdf). Fit **C** (our media subcorpus plus official text can test synchronization).
- **How Soft Propaganda Persuades** (Mattingly, Yao), Comparative Political Studies, 2022, and **The Art of Political Control in China** (Mattingly), Cambridge UP, 2019. Experiments on 6,800+ respondents with real propaganda video. [campuspress.yale.edu (PDF)](https://bpb-us-w2.wpmucdn.com/campuspress.yale.edu/dist/3/4318/files/2025/10/Mattingly_Yao_Soft_Propaganda.pdf). Fit **C**.

---

## 9. Fragmented authoritarianism and inter-agency coordination

- **Fragmented Authoritarianism 2.0: Political Pluralization in the Chinese Policy Process** (Mertha), China Quarterly, 2009. The state is not monolithic; inter-ministerial competition and lowered barriers let peripheral actors enter the policy process. [cambridge.org](https://www.cambridge.org/core/journals/china-quarterly/article/abs/fragmented-authoritarianism-20-political-pluralization-in-the-chinese-policy-process/EA5E4FE9316DA47EB53C777C879DCA29). Fit **B**. Corpus angle: co-issuance of documents by multiple ministries is a direct, measurable proxy for inter-agency coordination and its growth over time. We hold issuer fields, so co-issuer networks are buildable now.

---

## 10. AI and technology governance (the volume's spine)

| Paper | Venue / no. | Year | Question + method | Corpus fit |
|---|---|---|---|---|
| **AI-tocracy** (Beraja, Kao, Yang, Yuchtman) | NBER w29466 / QJE 2023 | 2021 | Facial-recognition AI firms, state procurement, and protest data. Local unrest triggers AI procurement, which suppresses later unrest and stimulates firm innovation. [nber.org/papers/w29466](https://www.nber.org/papers/w29466) | **B** |
| **Data-intensive Innovation and the State: Evidence from AI Firms in China** (Beraja, Yang, Yuchtman) | NBER w27723 / RES | 2020 | Public-security procurement contracts give AI firms access to government data, stimulating commercial innovation. [nber.org/papers/w27723](https://www.nber.org/papers/w27723) | **B** |
| **Exporting the Surveillance State via Trade in AI** (Beraja, Kao, Yang, Yuchtman) | NBER w31676 | 2023 | China has comparative advantage in surveillance AI exports; autocracies import more in unrest years. [nber.org/papers/w31676](https://www.nber.org/papers/w31676) | **C** |
| **Government as Venture Capitalists in AI** (Beraja, Peng, Yang, Yuchtman) | NBER w32701 | 2024 | Government guidance funds and state VC shaping AI innovation. [nber.org (PDF)](https://www.nber.org/system/files/working_papers/w32701/w32701.pdf) | **C** |
| **China: Autocracy 2.0** (Yang) | NBER w32993 | 2024 | Framework essay: modern China as an economically robust, tech-enabled autocracy that manages incentives and information with advanced bureaucratic and technological tools. [nber.org/papers/w32993](https://www.nber.org/papers/w32993) | **C** |
| **Geoeconomic Pressure** (Clayton, Coppola, Maggiori, Schreger) | NBER w34020 | 2025 | Uses LLMs over large textual corpora to find episodes where governments use existing economic relationships to pressure other countries, classifying sender, target, instrument and the firms and products involved; finds tariff-hit firms adjust prices while export-control-hit firms raise R&D, and quantifies its own classification uncertainty across open-weight models and prompt variants. [nber.org/papers/w34020](https://www.nber.org/papers/w34020) | **A** |
| **A Theory of Economic Coercion and Fragmentation** (Clayton, Maggiori, Schreger) | NBER w33309 | 2024, rev. 2026 | Theory companion: hegemons pressure others by threatening to disrupt trade or financial ties; estimates US leverage rests mainly on finance and Chinese leverage mainly on manufacturing. [nber.org/papers/w33309](https://www.nber.org/papers/w33309) | **C** (theory) |
| **The Ins & Outs of Chinese Monetary Policy Transmission** (Miranda-Agrippino, Nenova, Rey) | NBER w34626 | 2026 | Builds a **novel indicator of the PBOC's monetary policy stance** and estimates a policy rule for a **dual price-stability mandate — domestic inflation AND the exchange rate** — allowing for the evolution of the operating framework; finds domestic transmission largely textbook except where the renminbi and the financial account are actively managed, and strong international spillovers to commodities, production and trade. The abstract does not state how the indicator is constructed. [nber.org/papers/w34626](https://www.nber.org/papers/w34626) | **A** |
| **Monetary Policy in Mandarin Capitalism** (Chang, Xiong) | NBER w35562 | 2026 | Asks why China's repeated credit booms produce no lasting inflation, and argues the regime is oriented to PRODUCTION: credit sustains output and firm balance sheets rather than final demand, so policy preserves productive capacity instead of managing demand. [nber.org/papers/w35562](https://www.nber.org/papers/w35562) | **B** |
| **China's AI Regulations and How They Get Made** (Sheehan) | Carnegie Endowment | 2023 | Institutional account of the 2021 recommendation-algorithm, 2022 deep-synthesis, and 2023 generative-AI rules, the algorithm registry, and who drafts them. [carnegieendowment.org](https://carnegieendowment.org/research/2023/07/chinas-ai-regulations-and-how-they-get-made) | **B** |

Corpus angle. The Beraja-Yang-Yuchtman program measures AI through firms and procurement. The complement they do not hold is the policy-document side: the central AI rules and their cascade into provincial and municipal implementing documents. That is precisely our corpus (AI relevance scores, CAC/MIIT/MOST issuers, dates, citations). We can supply the regulatory-diffusion half of the AI-tocracy story.

---

## Highest corpus fit (run now)

Seven papers where we could run a real replication or a novel China-at-scale version immediately, flagged for prioritization.

1. **Laboratories of Autocracy** (Luo, Wang, Yang, NBER w34219, 2025). Same object (millions of policy documents, central to local, ~20 years). We can replicate the centralization-over-time finding and improve on it: they infer central-local linkage from text similarity, we hold the explicit resolved citation graph and district-level depth.
2. **Decoding China's Industrial Policies** (Fang, Li, Lu, NBER w33814, 2025). Our LLM classification pipeline already extracts doc_type, policy significance, and references. We can rebuild their industry-targeting-and-tone extraction and extend it to non-industrial domains (AI, environment, consumption) with our citation links as a diffusion tracer.
3. **Understanding China's IT Policy System Through Policy Citation Networks** (Systems, 2026). Our citation graph (~280k resolved edges) dwarfs their 3,150 links and spans all domains and tiers. A direct order-of-magnitude extension.
4. **Measuring policy diffusion intensity** (Information Processing & Management, 2025). Their hierarchical-effectiveness plus textual-intensity index is directly computable on our admin levels and dates, across the whole corpus rather than one policy domain.
5. **Aligning Agendas in Public-Activity Reports** (Journal of Chinese Political Science, 2026). Our genre tags isolate reports and readouts; our dates and admin levels let us rebuild the central-signal-tracking test at finer granularity, including the municipal and district tiers they did not reach.
6. **Policy Experimentation in China** (Wang, Yang, NBER w29402 / JPE 2025). We can detect experimental "point" documents (试点) by genre and title, map where they originate, and test whether successful trials get cited upward into central documents, measuring the generalization mechanism directly.
7. **AI-tocracy / Data-intensive Innovation** (Beraja, Kao, Yang, Yuchtman, NBER w29466 and w27723). We hold the policy-document half they lack. A China-at-scale regulatory-diffusion study of the AI rules complements their firm-and-procurement work.

Data we uniquely improve on: sub-national depth (province, municipality, district, departments), an explicit resolved citation graph rather than inferred similarity, recency through 2026, and genre/issuer tags that let campaign bursts and co-issuance networks be measured directly.

---

## Three concrete study ideas for our corpus

1. **A central-to-local diffusion atlas.** For every central policy, measure the lag in days until the first provincial, municipal, and district echo, matched by title and by citation edge. Break the lag down by issuer, genre, and domain. This generalizes the existing consumption-diffusion worked proof (以旧换新, GD +20 days, ~49-day median lag) to the whole corpus and produces the attention-cascade object that Luo-Wang-Yang and the attention papers approximate from text similarity alone. Our citation edges make the "echo" directed and explicit.

2. **Did authority recentralize, measured on the citation graph.** Both NBER crown-jewel papers date a 2013 recentralization from text. We can test it structurally: compute, by year, the share of policy initiations that originate sub-nationally versus centrally, and the rate at which sub-national documents are cited upward into central ones (bottom-up uptake). A falling upward-citation rate after 2013 would be a graph-native confirmation that bottom-up innovation stopped being rewarded, independent of their text-similarity method.

3. **The AI regulatory web.** Trace the citation lineage of the three central AI rules (recommendation algorithms 2021, deep synthesis 2022, generative AI 2023, per Sheehan) through their provincial and municipal implementing documents. Quantify speed of reproduction and textual fidelity (Word Mover's Distance to the central text). This is a China-at-scale regulatory-diffusion study that supplies the policy-document half missing from the AI-tocracy program, and it maps directly onto the volume's AI-through-the-tech-revolution thesis.

---

## Outcomes (2026-10-01): what each replication found on our corpus

Added after the first wave of replications. Paper → our memo → the headline, so the "where is
the NBER stuff" question maps directly to results. Full synthesis: `findings-synthesis.md`.

| Paper | Our memo | Headline on our corpus |
|---|---|---|
| Luo/Wang/Yang, Laboratories of Autocracy (NBER w34219) — diffusion | `diffusion-atlas.md` | Province-before-city holds corpus-wide (68-76% vs 50% null); breadth belongs to State Council 条例, speed to campaigns; diffusion has not accelerated on a fixed panel, central output grew and the fast-echo share fell 50%→~20%. |
| Luo/Wang/Yang — the 2013 recentralization claim | `recentralization-experimentation.md` | Upward-citation share steps up 7-11 pts at exactly 2013, holds to 2017, reverts by 2023-26; horizontal/downward flat. A 2013-17 rise in authority-borrowing, not a collapse of peer learning. |
| Wang/Yang, Policy Experimentation (NBER w29402) | `experimentation-wang-yang.md` | 1,592 central pilot guidelines (vs their 633); designation flows down (pilots cited by 833 local docs) but generalization barely flows up (0.4-1.2% reach a visible national instrument). Their GDP/incentive causal tests need external data we lack. *(2026-10-06: `successor-detector.md` lifts the visible rate to 5.9% / 6.9% ex-mid-flight, median lag 564 d; 9 of 12 mature substantive no-successor pilots scaled under a renamed instrument, so the gap to 53.9% is mostly renaming. `site-selection-gdp.md` replicates positive site selection descriptively at province grain: named provinces at the 0.705 GDP percentile, Spearman 0.625.)* |
| Fang/Li/Lu, Decoding China's Industrial Policies (NBER w33814) | `industrial-policy-targeting.md` | Targeting broadened (sector HHI fell by half+); money concentrates in chips/new-energy/NEV/biopharma, legacy sectors get rules; place-based sectors see local pile-on, network-rule sectors stay central. *(2026-10-07: level claims re-based on `doc_identity`; agriculture flips to local, "AI evenly spread" and "future industries local from the start" withdrawn.)* |
| Baumgartner-Jones punctuated equilibrium; campaign governance | `attention-campaigns.md` | Attention punctuated at topic level (Party 2020-21, Health 2020, Credit 2018) but not fat-tailed pooled; the campaign label moved UP the hierarchy (central 0.21%→0.99%), opposite the devolution expectation. |
| IT-policy citation-network method (Systems 2026, 3,150 links) | `citation-network-structure.md` | On ~280k edges (279,409 at build; 287,607 live 2026-10-01): top 1% of nodes hold 54.5% of inbound; genre source/sink holds under age control; bridges are procedural law. Found the resolver proxy-target bug (27% of edges); the exact-title class is fixed, containment proxies without an exact-title copy persist (`consistency-review.md` H1). |
| Fidelity of diffusion (agenda Q6) | `diffusion-fidelity.md`, `fidelity-provincial.md` | 88% elaboration corpus-wide, not bimodal; and the province is the translation layer: in 92.8% of C→P→M chains the city copies the province, not the center. *(2026-10-07: replicated on Jiangsu, `fidelity-jiangsu.md`, 89.9% of 89 chains, on one city; the citation-only relay figures are floors by ~5% of relays, `pair-channels.md`.)* |
| Fragmented authority / joint issuance (Q7) | `joint-issuance.md` | Joint issuance rising at the center (17%→43% on the policy-genre, fixed-site robustness set gov/ndrc/mof/mee; pooled 2020-26 = 34%; on an all-central-docs, any-genre denominator the share falls 23%→15% because single-issuer news and explainers exploded after 2020), coalitions growing (2.4→3.9), core shifted from an MOF-tax dyad to an NDRC hub; only 5+ coalitions are echoed more often and sooner. |
| Sheehan's CAC rules; AI-tocracy line | `ai-governance-diffusion.md`, `ai-regulatory-web.md`, `ai-plus-fidelity.md` | Two faces: AI regulation is a CAC monopoly that self-extends at the center; the promotional AI+ program diffuses and is elaborated into local sector plans. |
| Beraja/Peng/Yang/Yuchtman, Government as Venture Capitalists in AI (NBER w32701) | `patient-capital-cascade.md` | **Started 2026-10-08, lexical half only.** We hold the authorizing-instrument side they lack: 1,769 docs mention 引导基金, 298 政府引导基金, 1,081 产业投资基金, 267 docs whose TITLE is a fund instrument (1998-2026, ~5/yr → ~18/yr at 2016). The memo's finding is that the *justification* for long-horizon state capital (耐心资本) was built sub-nationally in one city's technology-park finance reforms and ratified centrally 5y5m later — a fund-level panel dates the instrument, only the document record dates the argument. The fund/firm-side causal work still needs data we do not hold. |
| Clayton/Coppola/Maggiori/Schreger, Geoeconomic Pressure (NBER w34020) | `geoeconomic-pressure-instruments.md` | **Complement, not replication, and said so.** Their unit — sender, target, instrument, named firms — is what this corpus holds for one principal, as PRIMARY instruments rather than LLM-classified news, so their classifier variance is absent and a different limit applies: an instrument is not an economic effect. **The corpus records pressure in BOTH directions** and that is the design point — a naive extractor reports 278 US *and* 196 Chinese *and* 220 Japanese entities because China also RECORDS foreign measures against it. Classifying the sender first: **57 outbound instruments vs 10 inbound, but 37 of 49 inbound documents are spokesperson justifications** — the issuing state's archive holds its own actions as documents and others' as commentary. **338 entities across 28 distinct outbound instruments** (454 before 文号 dedup), 美国 151 / 日本 120 / 欧盟 49, i.e. 81% US-plus-Japan, consistent with w34020's mutual-pressure finding and adding Japan as a clear second target. The UEL justification is **simultaneous**: 17 of 22 instruments pair within 21 d, median lag **0**, 71% same-day or next-day. |
| Miranda-Agrippino/Nenova/Rey, Ins & Outs of Chinese Monetary Policy Transmission (NBER w34626) | `pbc-stance-series.md` | **Tests their premise rather than replicating their estimate.** They *assume* a dual inflation-and-exchange-rate mandate and build an econometric stance indicator whose construction the abstract does not state. The corpus now holds the committee's own words: **70 quarterly MPC readouts, 2009-04 to 2026-09, all with body text** (31 PBC documents before the 2026-10-09 backfill). **The dual mandate is ASYMMETRIC in the committee's language**: the exchange-rate leg is invariant — 合理均衡 in **60 of 70** readouts continuously from 2010-12 through the 2025 reversal, 双向浮动 in 33 — while the domestic stance leg is the only thing that moves, and it moved exactly **twice** in sixteen years (适度宽松→稳健 at 2010-12, 稳健→适度宽松 at 2025-03), each preceded by a single OVERLAP quarter carrying both words. That also gives their regime changes an external, public date. Needs no panel control — fixed institution, fixed cadence, fixed genre. And the negative result sharpened into a genre boundary: **以我为主 never appears in a readout** but does appear in **35 PBC documents** — spokesperson Q&A, press conferences, governor speeches — so the autonomy claim is made where a human takes questions, never in the committee's formal text. |
| — (no paper; our own question) | `rmb-coverage.md` | The monetary apparatus is the corpus's biggest institutional hole: PBC 31 docs, SAFE 22, no NFRA, against MOF 3,395 and chinatax 5,018. Reachable from NYC — the PBC crawler walks page 1 only, so this is a dialect fix not a vantage problem. On a fixed 17-site panel the 美元:人民币 ratio halves 2013→2017 and sits flat for eight years; uncontrolled it *rises*, because 2026 holds 3× 2024's documents. RMB internationalization reaches the record as zone-and-plan policy (大湾区纲要 365 citers), not monetary regulation. |

---

## Still unreplicated from the "run now" seven (status 2026-10-08)

Five of the seven above have memos. **Two do not**, and both are directly computable on what we
already hold:

- ~~**#4 Measuring policy diffusion intensity**~~ — **DONE 2026-10-08,
  `diffusion-intensity-index.md`.** 12,211 explicit adoption events, 796 anchors, 20 policy areas.
  Their two dimensions ARE independent (Spearman −0.085, and the sign flips to +0.128 under a
  stricter spec, i.e. noise around zero), so the composite earns its second axis — a test their
  single domain could not run, and it comes out in their favour. But summed over adopters,
  "hierarchical effectiveness" correlates with the plain adopter COUNT at +0.957: use the
  per-adopter mean, which points the other way (−0.271). New: breadth costs both authority
  (2.67 → 2.46) and elaboration (0.99 → **0.81**) across adopter-count quintiles.
- ~~**#5 Aligning Agendas in Public-Activity Reports**~~ — **DONE 2026-10-08,
  `authority-invocation.md`**, reframed rather than reproduced. Their design is unavailable and the
  reason is a finding: the Party hierarchy is nearly absent as an ISSUER here (104 provincial
  party-committee documents vs 19,015 government ones) because 政府信息公开 obliges administrative
  organs, not the Party — so the party-secretary-vs-governor half cannot be run on this corpus at
  any crawl depth. But the Party channel is highly visible as INVOKED authority. On a fixed 18-site
  panel the General-Secretary channel goes 0.0% (2012) → 30-43% (2024) while the Premier channel
  sits at 0.0-1.0% at every level in every year — so their central claim is not a ratio but an
  **absence**. Two things the level dimension adds: the gradient **inverts** (2016 central 8.0% >
  municipal 7.0%; 2024 municipal **42.9%** > central 31.7%), and institutional invocation (党中央)
  keeps the **opposite** gradient throughout (2024: 33.0 / 22.0 / 14.6). It also disagrees with
  `recentralization-experimentation.md`: authority-borrowing by NAME did not revert after 2017,
  while borrowing by CITATION did.

**Two papers added to the map 2026-10-09** (searched for work postdating this list rather than
re-checking it):

- **Bureaucratic Incentives and Effectiveness of the One Child Policy in China** (Li, Meng, Miller,
  Yang), **NBER w33741**, May 2025. Built on the **一票否决 "One Vote Veto"** rule — promotion
  strictly barred for missing a target — arguing that enforcement, not the policy's content, is what
  made it bite. **Corpus fit: A, and feasibility is measured.** 一票否决 appears in **1,019**
  documents, inside a dense accountability lexicon: 责任追究 6,101, 绩效考核 5,598, 问责 4,266,
  目标责任 3,109, 挂牌督办 1,520, 党政同责 1,408, 考核问责 400, 终身追责 100, 军令状 94. The paper
  studies the veto's effect on **one** policy; the document record can ask the complementary
  question — **which targets carry a veto, from when, and at what level** — i.e. how a
  promotion-blocking device spread across policy domains. That is the same shape as the
  `local-legislative-devolution` and 出口管制 findings: a named institutional device with a
  documentary footprint. **Started the same day: `one-vote-veto.md`** — the device's full life-cycle,
  with the paper's own domain (计划生育) going from the plurality at 40.6% of veto documents to
  **exactly 0.0%**, a level inversion from municipal 67% to central 31% and back out, and a retreat
  whose cause is **not in the documents we hold** (the obvious 基层减负 explanation fails: 2.6%
  co-occurrence, and 减负 grows hardest *after* the veto has already declined).
- **Mining Chinese Historical Sources At Scale: A Machine-Learning Approach to Qing State Capacity**
  (Keller, Shiue, Yan), **NBER w32982**, 2024. **Method comparator, not a replication target** — its
  corpus is Qing-era and ours begins in the 1980s. Kept because its measurement question is
  identical to ours (can state capacity be read off the documentary record at scale?) and because it
  is the only NBER entry here whose method is text-as-data on Chinese *sources* rather than on
  firm or trade panels.

**All seven "run now" items now have memos.**

NBER papers in §10 never attempted, with the blocker for each: **w29466 AI-tocracy** and
**w27723 Data-intensive Innovation** need procurement contracts and protest data (we hold the
policy half only — `ai-governance-diffusion.md` is the complement, not the replication);

> **Feasibility checked properly, 2026-10-09, rather than asserted.** The AI-tocracy *causal chain*
> (unrest → AI procurement → suppression + firm innovation) is out of reach: our procurement
> documents overlap surveillance only thinly — 政府采购 ∩ 视频监控 **285** documents (2.9% of 9,664),
> ∩ 人脸识别 **52**, ∩ 雪亮工程 **29** — and none carry contract values or vendor names, which is
> the paper's unit of analysis. No protest data at all.
>
> But the **deployment programs are nameable and datable**, which the regulation memos do not cover:
> 视频监控 **2,116** documents, 智慧城市 2,391, 技防 911 *(2 chars — segmented index; a trigram query
> reports 0)*, 社会治安防控 644, 人脸识别 578, 雪亮工程 **173**, 公共安全视频 171, 智慧警务 82, and
> 天网工程 / 平安城市 / 监控探头 in single or double digits. So a **surveillance-deployment diffusion
> study** is available where the causal replication is not — distinct from the three AI memos, which
> are about *regulating* AI rather than deploying it.
>
> 雪亮工程 looks traceable and has a suggestive shape: 3 documents in 2017 (the first central mention
> is in passing, in 国务院办公厅关于县域创新驱动发展的若干意见, forwarded by Heilongjiang ten days
> later), then a local burst in 2018 (12 municipal, 4 district), a level **inversion** by 2021
> (1 central / 10 district), a peak of 43 in 2022, and decline to 7-12 since.
>
> **That shape is NOT reported as a finding, deliberately.** 173 documents across a handful of
> sites is too thin for the fixed-site panel that every series on this corpus needs
> (`rmb-coverage.md` §4 trap 3, where an uncontrolled series reversed a trend's sign), and the
> post-2022 decline has at least two readings that the counts cannot separate — the programme
> winding down, versus the programme maturing past the stage that generates policy documents. It is
> recorded here as **a reachable study with its n stated**, so that whoever runs it starts with the
> panel rather than the headline.
>
> **Panel verdict, 2026-10-09 (`panel.py`): the headline would have had the WRONG SIGN.** On the
> default 18-site panel 视频监控 is a **SIGN_FLIP** — raw rho **+0.791** against panel-share rho
> **−0.549**, n=647. The raw count rises; the SHARE of panel attention peaks at 2.07% in 2017 and
> falls to 0.57% by 2025. So "surveillance policy is growing" is a statement about our crawl
> schedule, and the composition-free reading is that video-surveillance deployment has been
> losing share of sub-national policy attention since 2017. 雪亮工程 separately comes back
> **THIN at n=58**, which is the tool enforcing the refusal made by hand above. Both are now
> measured rather than warned about; a surveillance-deployment memo should open from the share
> series, not the counts.
**w31676 Exporting the Surveillance State** needs trade data; **w32993 Autocracy 2.0** is a
framework essay with no single replicable estimate.

> **w31676 feasibility measured 2026-10-09, and the blocker is sharper than "trade data".** The
> paper's object is surveillance-AI export *flows* to autocracies. Our holdings have essentially
> nothing on that specific intersection: **出口管制 ∩ 视频监控 = 1 document.** One. So this is not
> a thin-data problem to work around; the object is absent.
>
> **The export-CONTROL regime, by contrast, is well covered** — 出口管制 **1,071** documents,
> 出口许可 767, 两用物项 412, 技术出口 328, 管制清单 211, 境外投资 1,521 — and the instrument stream
> is current, with the MOFCOM 公告 series held through 2026 (drone two-use controls on the US,
> 2026-08; strategic-mineral reporting rules, 2026-06). **人工智能 appears in 192 of the 出口管制
> documents** and 算法 in 47, so AI is inside the regime rather than outside it.
>
> The central series steps at **2021**: 7 · 4 · 5 · 3 · 5 · 15 · **90** · 52 · **125** · 101 · 114
> (2015→2025, central-level documents only), which brackets the 出口管制法 taking effect
> **2020-12-01**. That is the same shape as `local-legislative-devolution.md` — a dated statute with
> a documentary step — and it is **a candidate, not a claim**: it needs the fixed-site panel, and
> the 2026 total of 395 is **304 media documents**, so the raw series is media-driven at the end
> exactly where it looks most dramatic.
>
> **So the honest statement is a swap, not a workaround:** AI-tocracy's export question is
> unreachable, and a *technology-export-control* study is reachable with AI as one controlled
> domain. Those are different papers, and calling the second a replication of the first would be
> the kind of relabelling `consistency-review.md` exists to catch.
>
> **The swap was RUN, 2026-10-09: `export-control-regime.md`.** The 2021 step survives a fixed
> central panel. *(Figures CORRECTED the same day: the panel was keyed on `date_written`, which
> whole institutions never populate — pbc 6,099/6,099, chinatax 5,018/5,018 — so it was missing
> most of the central government. On the corrected 8-site panel, 出口管制 goes 0.08 / 0.13 /
> 0.39% → **2.84%** in 2021 and then keeps CLIMBING to **4.45%** by 2025, ρ share **+0.952**.
> The "steps and holds" reading is withdrawn; it is a statute followed by continuing
> escalation.)*
> Two things make it a finding rather than a series. First an internal control: 出口许可 —
> pre-existing licensing machinery rather than the statute's own vocabulary — only roughly
> doubles where 出口管制 and 两用物项 step ~12x and ~11x, so the step is the law's vocabulary
> entering the record and not a general rise in trade-restriction attention. Second the genre
> check that could have killed it: in 2021 on the panel the step is 76 mofcom `other` + 8
> `promulgation` + 4 cac/mee documents and **1 news document**; the regime's 367 news documents
> live on guancha (253) and ifeng (73), which the panel excludes — which is exactly why raw 2026
> reads 357 against a panel 43. AI sits INSIDE the regime (半导体 217, 芯片 202, 人工智能 192,
> 算力 73, 算法 48), which is the honest form of the AI-export question.
>
> It also surfaced two data defects that bounded it. 166 of the 1,071 documents (15.5%) carry
> `date_written = 0` and are absent from every series — 73 on `gov`, including
> **两用物项出口管制条例** (107 inbound), 稀土管理条例 and 商用密码管理条例, so the regime's second
> anchor instrument cannot appear in its own time series. And **725 mofcom titles were stored as
> literal `?`** (every CJK character 0x3f, served that way by the listing endpoint while the
> article pages are clean), making the ministry that holds 500 of these documents invisible to
> both FTS indexes, to citation targeting and to `title_reissue` — recovered by
> `scripts/rnd/backfill/repair_mofcom_titles.py`. A corpus can hold a document and still not
> have it.

**w32701** is now started (above) and is the
only one of the five whose missing half we actually hold.

