# Practice Product Cases (Spotify-Specific)

5 cases tailored to the ML Platform PM role. Practice each out loud with a 35-min timer.

---

## Case 1: Centralized LLM Observability

**Prompt:** "Spotify has 15+ teams shipping AI-powered features. Each has built ad-hoc logging. You're the PM for AI observability. Design the platform."

### Sample Walkthrough

**Clarify:** "How many LLM calls/day across all teams? Are teams using different LLM providers (OpenAI, fine-tuned Llama, etc.)? Is there existing observability infra I should build on (I assume MLflow is in use from what I know about Honk)?"

**User & Pain:** "My primary persona is the ML engineer building an LLM-powered feature. Today, when the AI DJ generates incorrect commentary, the eng team has to manually search CloudWatch logs, cross-reference deployment timestamps, and reconstruct what happened. Average investigation: 4+ hours. Secondary pain: leadership has no visibility into total LLM spend across the org."

**Metrics:**
- North star: Mean Time to Detect + Resolve AI quality issues
- Adoption: % of LLM-calling services instrumented (target: 80% in 6 months)
- Cost visibility: 100% of LLM spend attributable to teams/features
- Quality: # of undetected production quality incidents per quarter

**Solutions:**
1. **Quick win:** Standardize the logging patterns Honk already uses (MLflow traces + GCP logging) into a reusable library. Low effort, immediate value for teams already close to this pattern.
2. **Medium bet:** Build a spotify-ai-sdk (Python first, since most ML is Python) that auto-instruments any OpenAI/Anthropic/Llama client call. Captures traces, tokens, cost, latency. Ships with a Backstage plugin for discoverability. Add a cost dashboard.
3. **Strategic bet:** Full observability platform with auto-instrumentation + LLM-as-judge quality monitoring + anomaly detection + root-cause analysis workflows. Integrate with CI/CD for regression gating.

**Recommendation:** "I'd frame this as a 6-month bet with two phases. Phase 1 (months 1-3): ship the SDK + cost dashboard. Co-design with the Personalization squad (most models, most pain) and the Honk team (already have tracing patterns we can generalize). Phase 2 (months 4-6): add quality monitoring with LLM-as-judge and the regression testing framework. Measure success via adoption rate and MTTR reduction."

**Adoption plan:** "Golden Path approach -- make the SDK the default for any new LLM project. Add it to the ML Golden Path tutorial in Backstage. For existing teams, provide a migration guide and offer 'white glove' onboarding for the first 5 teams. No mandates -- make the right thing the easy thing."

---

## Case 2: LLM Evaluation Framework

**Prompt:** "Each team at Spotify evaluates their LLM features differently. Some use vibes. Some have basic metrics. Design a centralized evaluation platform."

### Sample Walkthrough

**Clarify:** "Which teams are most advanced in evaluation today? (I'd guess the AI DJ team, since they use golden examples and adversarial testing.) What's the current worst case? (Probably a team shipping LLM features with no evaluation beyond 'it looks good')."

**User & Pain:** Two personas:
1. The ML engineer who wants to know "did my prompt change make things better or worse?" before deploying
2. The PM/lead who wants to know "is the quality of our AI feature improving or degrading over time?"

**Pain points:**
- No consistent quality metrics across AI features
- Deploying prompt changes is a leap of faith -- no regression testing
- Quality incidents are discovered by users, not caught proactively
- Human evaluation doesn't scale (the AI DJ team uses expert annotators, but most teams can't afford that)

**Solutions:**
1. **Quick win:** Define 5 standard evaluation dimensions (faithfulness, relevance, groundedness, toxicity, conciseness) and provide LLM-as-judge prompt templates for each. Teams can use these manually.
2. **Medium bet:** Build an evaluation pipeline service. Teams upload a golden dataset + evaluation criteria, the platform runs LLM-as-judge, returns a quality scorecard. Integrates with CI/CD to gate deployments.
3. **Strategic bet:** Full eval platform with golden dataset management, automated regression testing, production quality monitoring (sample real traffic + evaluate continuously), quality dashboards in Backstage, and A/B testing integration.

**Recommendation:** "Start with the medium bet. The key DIBB: Data -- Spotify's AI DJ team already proved that golden examples + LLM-as-judge evaluation catches 25% of problematic outputs (from the Honk data). Insight -- this pattern works but only the most sophisticated teams do it. Belief -- if we productize it, we can raise the quality bar across all AI features. Bet -- build the evaluation pipeline, pilot with 3 teams in Q1, measure quality incident reduction."

---

## Case 3: LLM Cost Explosion

**Prompt:** "LLM inference costs are growing 40% QoQ. Design a product to give teams visibility and help them optimize."

### Key Spotify-Specific Angles
- Reference that Spotify chose Llama 3.1 8B over larger models specifically for cost/latency -- domain-adapted smaller models are cheaper
- Reference Honk's quota management as an existing pattern
- Reference vLLM as their serving layer -- prompt caching and quantization are levers
- Propose per-team cost attribution tied to DIBB (each team's LLM spend should be justified by a bet with expected ROI)

### Sample Solution Structure
- **Quick win:** Cost attribution dashboard -- tag every LLM call with team/feature, visualize in Backstage
- **Medium bet:** Automated optimization recommendations (e.g., "Feature X uses GPT-4 for classification -- fine-tuned Llama 8B would be 90% cheaper with similar quality")
- **Strategic bet:** Full FinOps platform with budgets, alerts, automated model routing (send simple queries to cheap models, complex to expensive ones), and cost-per-quality optimization

---

## Case 4: AI Feature Quality Regression

**Prompt:** "The AI DJ team deployed a prompt update and quality degraded. Design a system to prevent this across all AI features."

### Key Spotify-Specific Angles
- Reference how the AI DJ team already uses golden examples + adversarial testing
- Reference Honk's LLM-as-judge catching 25% of issues, with 50% course-correction rate
- Propose a "quality gate" in CI/CD: run golden dataset, compare scores to baseline, block deployment if regression detected
- Frame it as extending the Honk team's evaluation patterns to all LLM workloads

### Sample Solution Structure
- **Quick win:** Mandatory golden dataset requirement for any LLM feature (provide templates)
- **Medium bet:** Automated regression testing in CI/CD -- run golden dataset, compare quality scores to baseline, flag regressions before deploy
- **Strategic bet:** Continuous production monitoring -- sample live traffic, run LLM-as-judge evaluation, alert on quality drift even between deployments (model provider changes, data drift, etc.)

---

## Case 5: Instrumenting Agentic Workflows

**Prompt:** "Teams are building AI agents (like Honk) for various internal use cases. Agents are unpredictable -- variable steps, tool calls, cost. Design observability for agents."

### Key Spotify-Specific Angles
- Honk's two-stage architecture (planning agent -> coding agent) as a reference pattern
- MLflow tracing already captures Honk's execution -- generalize this
- Agent-specific challenges: variable-length traces, loop detection, cost circuit breakers
- Reference the MCP integration Honk uses for formatting/linting -- agents calling tools need tool-call tracing
- Propose "agent replay" -- ability to re-run a trace step-by-step for debugging

### Sample Solution Structure
- **Quick win:** Extend existing MLflow tracing to capture tool calls and agent decision points
- **Medium bet:** Agent observability SDK with automatic loop detection, cost circuit breakers, and step-by-step trace visualization
- **Strategic bet:** Agent platform with replay debugging, automated regression testing for agent behaviors, and cross-agent analytics (which patterns lead to success vs. failure)
