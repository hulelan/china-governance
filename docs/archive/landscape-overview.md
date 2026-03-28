# Landscape Overview: Who Else Is Working on Chinese Governance Data

*Strategic research notes from early project scoping.*

## Background

> My daughter graduated from Yale College with a BS in economy and math in 2024. She has been working with a big hedge fund company, focusing on using AI supporting investment. Part-time she is working on a project herself. She wants to retrieve information from provincial governments of mainland China. She is an American but grew up in Shanghai. She found most Americans have very limited knowledge and understanding of the political system of mainland China. Ex. most may believe Xi or the central government makes commands and then everyone down the chain execute accordingly. She also thinks Chinese political system may provide valuable experience or lesson for US. Using Claude she retrieved thousands PDFs from Shenzhen local government's public website.

## Three Groups Working in This Space

### A. Academic & Think Tank Projects

- **CSIS Open Source Analysis Project:** Uses AI to scrape and translate primary source documents to track how local implementation differs from Beijing's rhetoric.
- **The China Open Source Observatory:** Focuses on "digitizing and translating" local materials hidden behind clunky government websites.
- **Stanford's DigiChina:** Analyzes specific policy "funnels" — tracing an idea from a local pilot program in a place like Shenzhen all the way to national law.

### B. "China-Tech" Intelligence Platforms

- **Peking University's Chinalawinfo (北大法宝):** Gold standard for legal and policy data. Researchers use AI to perform Topic Modeling (LDA analysis) on these documents to see which provinces are prioritizing what (e.g., "Smart Manufacturing" vs. "Green Energy").
- **Trivium China:** A commercial firm that essentially does what this project attempts — they parse massive amounts of local data to explain to Western investors how the "sausage is made" in Chinese local government.

## Is the Current Approach "Cutting Edge"?

Retrieving thousands of PDFs is a great start (the "Data Acquisition" phase), but the cutting edge has moved toward **Relational Analysis** and **Semantic Mapping**.

- **Semantic Search:** Instead of just keywords, researchers use RAG (Retrieval-Augmented Generation) to ask their database questions like, "How does Shenzhen's definition of 'AI Ethics' differ from the State Council's 2023 draft?"
- **Comparative Analysis:** The most valuable insights often come from comparing two cities (e.g., Shenzhen vs. Hangzhou). This reveals the "competition" between local governments.
- **Named Entity Recognition (NER):** Using AI to extract the names of specific local officials or companies mentioned in documents to see who is actually "winning" government contracts.

## Potential User Groups

| User Group | Key Requirement | Value Proposition |
|---|---|---|
| Multinational Corps (MNCs) | Regulatory Compliance | Helping US companies in China predict new local regulations before they become "hard law" |
| US Policy Makers | Comparative Governance | Distilling "best practices" from China (e.g., how Shenzhen sped up EV charging infrastructure) for US policy lessons |
| Hedge Funds/Investors | Alpha Generation | Tracking "Government Guidance Funds" at the provincial level to see which industries are about to receive massive state capital |

## Suggested Next Steps

1. **Narrow the Scope:** Instead of "all provincial information," focus on a high-stakes vertical like "Local AI Investment Incentives" or "Data Privacy Enforcement."
2. **Use LLM-Agents:** Build a multi-agent system where one agent scrapes, one summarizes, and a third identifies "policy contradictions" between the local and central government.
3. **Engage with the OSINT community:** Follow researchers on Substack/X who specialize in Chinese OSINT for a peer group.
