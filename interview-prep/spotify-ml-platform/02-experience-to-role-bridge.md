# Experience-to-Role Bridge

How to reframe your Bell + Agility stories to hit exactly what each interview round is looking for.

---

## Product Case Round -- Stories to Weave In

The product case is about your thinking process, not your past experience. But weaving in relevant examples gives you credibility.

| When the case involves... | Drop this from your experience |
|---|---|
| Choosing what to build first | "At Agility, I shipped 13 features in 8 months by ruthlessly prioritizing by ROI -- I can walk you through how I'd prioritize here" |
| Internal platform adoption | "At Bell, I had to get 4 Google devs + 3 QA testers across time zones to adopt my conversation design process. Adoption is always the hardest part of platform work" |
| Evaluating AI quality | "At Bell, I evaluated chatbot quality across 6 different bots -- self-service rate, agent transfer rate, abandonment. For LLMs the metrics are different but the discipline is the same" |
| Prototyping before scaling | "At Agility, I prototyped our enrichment agent with n8n and Claude MCP, validated the approach, then managed the SpringAI/Python production rebuild. I'd take the same phased approach here" |
| Working with engineers | "I've worked embedded with Google Cloud engineers at Bell and managed a production rebuild at Agility -- I'm used to translating product requirements into technical specs" |

---

## Technical Collaboration Round -- Your Edge

This round pairs you with an engineer to solve a problem together. Your secret weapon: you've actually built agentic systems. Most PM candidates haven't.

### Things you can credibly discuss:
- Multi-step LLM pipelines (your Agility enrichment pipeline with Perplexity + ChatGPT + web scraping)
- Prompt design for structured outputs at scale (you did this for 300K profiles)
- The difference between prototyping (n8n/MCP) and production architecture (SpringAI/Python)
- How context engineering affects output quality (your "prompts and context strategy" at Agility)
- Real-world LLM failure modes (you've seen them firsthand)

### Vocabulary to use naturally (not forced):
- "When I built the enrichment pipeline, the hardest part was making the structured outputs reliable at 300K scale -- we had to iterate on the prompt + context strategy significantly"
- "I'd want to understand the latency budget before choosing between a single large model call vs. chaining smaller calls"
- "At Bell, we learned that the difference between a demo and production was 10x the effort -- I'd want to derisk the hardest technical unknowns first"

### What to avoid:
- Don't pretend to be an engineer. Say "I'd want to discuss with the eng team whether..." rather than making definitive technical claims
- Don't say "I'm not technical" -- you ARE technical for a PM, you just don't write production code daily

---

## Stakeholder Influencing Round -- Your Stories

Prep 3-4 STAR stories from your actual experience:

### Story 1: Getting cross-functional alignment (Bell)
- **S:** 6 chatbots needed alignment across Legal, Marketing, Engineering, Operations
- **T:** Each group had different priorities (Legal: compliance, Marketing: brand voice, Eng: feasibility, Ops: handle time reduction)
- **A:** Created bilingual branding guidelines that gave each stakeholder what they needed -- Legal got compliance guardrails, Marketing got brand consistency, Eng got clear specs, Ops got measurable KPIs
- **R:** Cut wireframe review time 65%, shipped all 6 bots with zero cross-team escalations

### Story 2: Convincing stakeholders to invest in automation (Agility)
- **S:** Manual journalist profile enrichment was costing 10K hours/month but leadership was skeptical of AI automation
- **T:** Needed to prove ROI before getting eng resources for production build
- **A:** Prototyped with no-code tools (n8n + Claude MCP) to show working results fast, then presented concrete data: ~80% time reduction, before requesting the SpringAI/Python production investment
- **R:** Got buy-in, shipped production system, 13 features in 8 months

### Story 3: Platform adoption challenge (Bell)
- **S:** Distributed team of Google developers initially resistant to your conversation design process
- **T:** Get them to follow your product specs without being their manager (influence without authority)
- **A:** (Fill in your specific approach -- did you demo the value? Create documentation? Do pairing sessions?)
- **R:** Shipped 6 bots, 39% reduction in agent transfers

---

## Key Strengths to Emphasize

| Their Requirement | Your Proof Point |
|---|---|
| Ship ML/LLM powered experiences at scale | Bell: 6 chatbots, 3M+ interactions. Agility: 300K profiles enriched |
| Build paved road for instrumenting LLM workflows | Agility: prototyped -> production pipeline pattern. You've done the 0-to-1 |
| Improve evaluation via LLM-as-judge | Bell: built QA processes for chatbot quality. Agility: structured output validation at scale |
| Scale up to meet team goals, then expand | Bell: started with 1 bot, scaled to 6. Agility: 13 features in 8 months |
| Work with 2 teams first, then scale | Your natural approach -- prove value small, then expand |

---

## Gaps to Address Proactively

| Gap | How to Bridge It |
|---|---|
| No explicit observability/evaluation platform experience | Reframe Bell chatbot QA and Agility output validation as proto-evaluation systems. "I've done this manually -- the platform would automate what I did by hand" |
| Platform PM (customer = engineers) vs. Product PM (customer = end users) | Emphasize your Bell experience working WITH Google engineers as your "customer." You understand developer needs |
| Spotify-scale (hundreds of millions of users) | Your Bell work served millions of interactions. Acknowledge the scale difference but show you understand the principles |
