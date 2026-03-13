# Product Case Framework (Platform PM Edition)

Use this exact structure in the interview. Aim for 30-35 min total.

---

## Step 1: CLARIFY (3 min)

Repeat the problem, ask 2-3 questions:
- "Who's the primary user? ML engineers, data scientists, or both?"
- "Are we building from scratch or improving something that exists?"
- "What's the scale -- how many teams would use this?"
- "Is there a specific incident that motivated this?"

State your assumptions: "I'll assume ~50 ML teams, 200+ models in production."

---

## Step 2: USER & PAIN (4 min)

Describe the persona's day-in-the-life:

> "I'll focus on the ML engineer persona. When a model degrades in production, they currently have to manually query multiple dashboards, cross-reference deploy logs, and often page the data engineering team. Average investigation: 4 hours, ~3 per week."

Articulate top 3 pain points. Quantify them.

---

## Step 3: SUCCESS METRICS (3 min)

- **North star:** One metric that captures the whole mission (e.g., "Mean Time to Detect + Resolve AI quality issues")
- **Adoption:** % of teams onboarded, WAU of the platform
- **Efficiency:** Hours saved per investigation
- **Quality:** Reduction in undetected production quality incidents

---

## Step 4: SOLUTIONS (5-7 min)

Brainstorm 3 options at different ambition levels:
1. **Quick win:** Standardized alerting templates on existing infra
2. **Medium bet:** Unified observability dashboard with automated anomaly detection
3. **Strategic bet:** Full-stack AI observability platform with auto root-cause analysis

For each: what it does, key tradeoff, rough effort.

---

## Step 5: PRIORITIZE & RECOMMEND (5 min)

Pick one (or a phased combo). Explain WHY using RICE or impact/effort:

> "I'd start with the medium bet as v1 -- it delivers 80% of value at 40% of cost. We phase in auto root-cause analysis in v2 once we've validated adoption."

Address build vs. buy. Name specific tools in the space (Langfuse, Arize, LangSmith) and explain why building internally might make sense at Spotify's scale.

---

## Step 6: ADOPTION & EXECUTION (4 min)

**This is where most candidates fail for platform roles.** Always include:

- **Design partners:** "We'd co-design v1 with the Personalization squad since they have the most models and the most pain"
- **Migration path:** How do teams move from their current setup?
- **Paved road approach:** Make it the easy default, not a mandate
- **Documentation + developer relations:** Internal evangelism matters

---

## Step 7: SUMMARIZE (1 min)

> "To recap: ML engineers waste X hours/week debugging production AI issues. I'd build a unified observability platform starting with automated quality monitoring, co-designed with the Personalization team, measuring success by adoption rate and MTTR reduction. Phase 1 in Q1, expand to all teams by Q3."

---

## Spotify-Specific Tips for This Framework

### Always use DIBB framing:
- **Data:** "Our ML engineers spend 4 hours per production incident investigation"
- **Insight:** "Most time is spent context-switching between disconnected dashboards"
- **Belief:** "A unified trace view would cut investigation time by 60%"
- **Bet:** "Build v1 of the AI observability dashboard, co-designed with the Personalization squad, measuring MTTR reduction over 3 months"

### Always use Think It / Build It / Ship It / Tweak It phases:
- **Think It** = de-risk at low cost (prototypes, user research)
- **Build It** = MVP that proves something
- **Ship It** = gradual rollout to 100%, measuring and improving
- **Tweak It** = continuous iteration

### Platform-specific language:
- Say "Golden Path" not "best practice documentation"
- Say "design partner squads" not "beta testers"
- Say "Backstage plugin" not "internal tool"
- Say "paved road" not "standard approach"
- Say "bet" not "project" or "initiative"
