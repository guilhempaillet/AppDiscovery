# Technical Collaboration Round Prep

What to expect: You'll work with a Spotify engineer to solve a technical product problem. It's collaborative, not adversarial. They want to see you can hold a technical conversation and make good product-technical tradeoffs.

---

## Spotify-Native Vocabulary

| Instead of saying... | Say this (Spotify-native) |
|---|---|
| "We'd build a monitoring dashboard" | "We'd add an observability plugin in Backstage so teams can discover it on the Golden Path" |
| "We'd create an SDK" | "We'd extend the ML platform SDK -- Python first since that's where most ML practitioners live" |
| "We'd use open-source tools" | "We'd build on OpenTelemetry for vendor-neutral instrumentation, similar to how Honk uses MLflow for tracing" |
| "We'd evaluate quality" | "We'd use LLM-as-judge evaluation, starting with the patterns the Honk team validated -- their judge catches 25% of issues" |
| "We'd deploy to the cloud" | "We'd deploy on GKE, store traces in BigQuery for analysis, logs in GCP" |
| "We'd build a prototype" | "In Think It, we'd prototype with 1-2 design partner squads, then move to Build It with an MVP" |
| "We'd create documentation" | "We'd add it to TechDocs, discoverable through Backstage, part of the Golden Path tutorial" |
| "We'd do a pilot" | "We'd co-design with a design partner squad -- probably Personalization since they have the most models" |

---

## How to Handle "I Don't Know"

Don't fake it. Say:

> "I'm not deeply familiar with [specific implementation detail], but my instinct would be [reasonable guess]. How does your team think about this?"

Then listen and build on their answer. This is what good PM-eng collaboration looks like.

---

## Common Technical Questions You Might Face

### "How would you decide between building our own eval framework vs. using Langfuse/Arize?"

**Your answer framework:**
- "At Spotify's scale, the question is whether off-the-shelf tools can handle the volume and integrate with our existing stack"
- "Build makes sense when: (1) the tool needs deep integration with internal systems like MLflow and Backstage, (2) we need custom eval dimensions specific to Spotify use cases, (3) vendor lock-in risk is high"
- "Buy makes sense when: (1) the problem is well-understood and commoditized, (2) we want to move fast and validate before investing in a custom build"
- "I'd propose: start with an open-source foundation (like OpenTelemetry for tracing) and build the Spotify-specific layer on top"

### "How would you handle teams that don't want to adopt the platform?"

**Your answer framework:**
- "I'd start by understanding WHY. Are they happy with their current setup? Do they have unique requirements?"
- "Golden Path philosophy: make the right thing the easy thing, but don't mandate"
- "Show value: 'Your team spent 12 hours debugging last week's incident. With the platform, that would have been 2 hours'"
- "If a team has genuinely different needs, learn from that -- it might inform the next version of the platform"

### "What's the architecture of this system?"

**Don't try to draw a system architecture diagram.** Instead:
- Describe the user journey: "An ML engineer deploys a new prompt. The SDK auto-captures a trace. If quality drops below threshold, the dashboard alerts the team."
- Name the components at the right abstraction level: "We'd need an instrumentation layer, a storage layer, an analysis layer, and a presentation layer"
- Defer to the engineer: "I'd think of it as these four components -- what's your instinct on the storage layer? BigQuery for traces, or something more specialized?"

---

## Your Credibility Moves

Things you can say that most PM candidates can't:

1. **"I've built an agentic pipeline myself"** -- Most PMs haven't. Your Agility enrichment agent with multi-API integration gives you real credibility in discussions about agent observability.

2. **"I've seen structured outputs fail at scale"** -- Your 300K journalist profiles work means you understand real-world LLM reliability challenges.

3. **"I've done the prototype-to-production transition"** -- n8n/MCP prototype -> SpringAI/Python production. You understand why production is 10x harder.

4. **"I've managed distributed eng teams on AI products"** -- 4 Google devs + 3 QA testers across time zones at Bell.

---

## Practice Exercise

**Scenario:** An engineer says "We want to add tracing to all LLM calls. But teams use different LLM providers -- OpenAI, Anthropic, our fine-tuned Llama via vLLM. How do we instrument all of them consistently?"

**Your response approach:**
1. Acknowledge the challenge: "Right, provider fragmentation makes consistent instrumentation harder"
2. Propose a layer: "What if the SDK wraps the common LLM client libraries with auto-instrumentation? Similar to how OpenTelemetry instruments HTTP clients transparently"
3. Ask a good question: "Are most teams using a shared internal LLM client, or does each team call providers directly?"
4. Suggest a phased approach: "We could start with the most common provider (probably OpenAI) and add others based on adoption data"
5. Connect to their context: "Honk already does this for its Claude integration via the Agent SDK -- can we generalize that pattern?"
