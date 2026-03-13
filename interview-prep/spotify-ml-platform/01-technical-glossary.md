# Technical Glossary - Spotify ML Platform PM Role

Quick-reference cheat sheet. For each term: what it is, a Bell/Agility analogy from YOUR experience, and a Spotify example.

---

## AI/ML Observability

**What it is:** Monitoring and debugging AI systems. Like regular software monitoring (uptime, errors) but for AI-specific problems: bad answers, hallucinations, cost spikes, quality drift.

**Your analogy:** At Bell, when a chatbot gave a wrong answer, how did you find out? You probably checked conversation logs manually. AI observability automates that at scale -- dashboards showing quality scores, alerts when quality drops.

**Spotify context:** Dozens of teams ship AI features (DJ, playlist generation, podcast summaries). Without centralized observability, each team builds ad-hoc logging. The platform provides one unified system.

---

## LLM-as-a-Judge

**What it is:** Using one LLM to grade the output of another LLM. Instead of having humans read 100M outputs, you ask a "judge" model: "Rate this answer 1-5 for accuracy and relevance."

**Your analogy:** At Agility, when your enrichment agent generated journalist profiles, how did you know the output was good? Probably spot-checking. LLM-as-a-Judge is like building an automated QA agent that checks every single output.

**Spotify context:** The AI DJ generates millions of commentary scripts daily. You can't human-review them all. An LLM judge evaluates each one for accuracy ("did it name the right artist?"), tone, and relevance.

---

## Traces and Spans

**What it is:** A trace = the full journey of one user request through all systems. A span = one step within that journey. Think of a trace as a receipt showing every department your order passed through.

**Your analogy:** Your Agility enrichment pipeline: User triggers enrichment -> Perplexity call -> ChatGPT call -> web scraping -> database write. That whole sequence = one trace. Each API call = one span.

**Spotify context:** User asks AI DJ something -> speech-to-text (span 1) -> LLM intent understanding (span 2) -> recommendation query (span 3) -> LLM generates commentary (span 4) -> text-to-speech (span 5). All connected in one trace.

---

## RAG (Retrieval-Augmented Generation)

**What it is:** Instead of relying on what the LLM memorized during training, you fetch relevant data from your own database and inject it into the prompt. Like giving someone a cheat sheet before asking them a question.

**Your analogy:** Your Agility agent does this already! It retrieves journalist data from media databases, then feeds that context to the LLM to generate enriched profiles. That's RAG.

**Spotify context:** "Tell me about this artist" -> system retrieves artist bio, genre tags, listening stats from Spotify's catalog -> injects into prompt -> LLM generates a natural language answer grounded in Spotify's actual data.

---

## Agentic Workflows

**What it is:** AI systems that can make decisions, call tools, and loop until a goal is met. Unlike a simple prompt-response, an agent decides what to do next at each step.

**Your analogy:** This is literally what you built at Agility. Your enrichment agent decides: do I need to search Perplexity? Do I need to scrape a website? Is the data complete or do I need another pass? That's an agent.

**Spotify context:** A "Music Research Agent" that investigates why recommendations are underperforming -- it queries data, pulls A/B test results, checks model metrics, and synthesizes a report. Each run might take a different path.

---

## Data Contracts

**What it is:** Formal agreements between teams about what data looks like: what fields, what types, what quality standards. A "promise" that data won't change format without warning.

**Your analogy:** Imagine if the media database you scrape at Agility suddenly changed its API response format. Your whole pipeline breaks silently. A data contract would catch that before it reaches your agent.

**Spotify context:** The recommendation team changes how "user engagement score" is calculated from 0-100 to 0-1 scale. Without a data contract, every downstream ML model silently breaks. With one, the schema violation is flagged immediately.

---

## Golden Datasets

**What it is:** A curated set of test cases with known-good answers. Your "unit tests" for AI. Run these before every deployment to catch regressions.

**Your analogy:** At Bell, you probably had test conversations you'd run through the chatbot after every update to make sure nothing broke. That's a golden dataset.

**Spotify context:** 500 curated AI DJ examples across categories (new artist intros, genre transitions, seasonal commentary, edge cases). Before deploying a new prompt version, run all 500 and compare quality scores.

---

## Cost Anomaly Detection

**What it is:** Real-time monitoring of LLM spending with alerts when costs spike unexpectedly. LLMs charge per token (roughly per word), so a bad prompt or stuck agent can burn thousands of dollars in minutes.

**Your analogy:** If your Agility agent got stuck in a loop calling Perplexity API 1000 times for one journalist, that's a cost anomaly.

**Spotify context:** A new feature launches, 10M users try it, and the RAG pipeline accidentally retrieves full artist biographies instead of summaries. Token usage (and cost) spikes 15x overnight.

---

## OpenTelemetry (OTel)

**What it is:** An open-source standard for collecting observability data (traces, metrics, logs). Like a universal power adapter -- instrument your code once, send data to any monitoring backend.

**Why it matters:** Spotify's platform team would build on OTel so they're not locked into one vendor. Any team using any LLM provider produces consistent, standardized telemetry.

---

## Faithfulness / Relevance / Groundedness (the eval metrics trio)

- **Faithfulness:** Did the AI only say things supported by the source material? (No hallucinations)
- **Relevance:** Did the AI actually answer the question that was asked?
- **Groundedness:** Is the answer based on the retrieved context, not the LLM's training data?

**Your analogy:** Your Agility enrichment agent generates journalist profiles. Faithfulness = did it only include info from verified sources? Relevance = does the profile answer what the researcher needs? Groundedness = is it using the media database data you retrieved, not making up facts from training?
