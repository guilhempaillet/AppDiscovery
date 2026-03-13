# Stakeholder Influencing Round Prep

This is a role-play where you convince a skeptical stakeholder. Expect pushback -- that's the point.

---

## Scenario 1: "Team Refuses to Adopt Your Platform"

**Setup:** A squad has built their own LLM observability. They say "ours works fine, why should we migrate?"

**Your approach:**
1. **Acknowledge their investment.** "I respect that you've built something that works for your team. That actually shows the need for this kind of tooling."
2. **Don't mandate.** Never say "you have to use our platform."
3. **Show unique value they can't get alone:**
   - Cross-team cost visibility ("Do you know how your LLM spend compares to other teams?")
   - Org-wide quality benchmarks ("How does your quality score trend vs. the AI DJ team?")
   - Maintenance burden ("Who maintains your custom logging when your team has other priorities?")
4. **Offer integration, not replacement.** "What if we built an adapter so your existing logging feeds into the centralized dashboard? You keep what works, we fill the gaps."
5. **Create FOMO.** "Three other teams are already getting value from the cost dashboard. The Personalization squad cut their debugging time by 60%."

---

## Scenario 2: "Leadership Wants You to Ship Faster"

**Setup:** Josh's boss says "We need this for all teams by end of quarter."

**Your approach:**
1. **Use DIBB to show your phased plan is de-risked:**
   - Data: "We have 15 teams with different LLM patterns"
   - Insight: "Rushing to 15 teams without validating with 2-3 means we risk building something nobody adopts"
   - Belief: "A phased approach de-risks adoption and lets us learn from early users"
   - Bet: "3 teams in 6 weeks, then all teams by end of next quarter"
2. **Reference Spotify precedent.** "The Honk team spent months validating their agent patterns before scaling. That's why they have 650+ merged PRs/month -- they built the right thing first."
3. **Offer a compromise.** "What if we ship the SDK to 3 design partner squads by end of month, and I'll have adoption data to show leadership at the all-hands? That gives us a credible story AND a validated product."
4. **Quantify the risk.** "If we ship to 15 teams and adoption is low because the tool doesn't fit their workflow, we lose 3 months AND credibility. If we ship to 3 teams and iterate, we lose 6 weeks but gain certainty."

---

## Scenario 3: "Engineer Disagrees with Your Technical Approach"

**Setup:** The engineer says "OpenTelemetry is overkill, we should just extend our MLflow setup."

**Your approach:**
1. **Explore their reasoning.** "That's a fair point. What's the advantage of staying MLflow-only? Are there integration costs with OTel I'm not seeing?"
2. **Ask a bridging question.** "Are there teams already using OTel for non-ML tracing that we'd want to integrate with?"
3. **Find the shared principle.** Both of you want: minimal friction for ML engineers, reliable trace data, low maintenance.
4. **Propose a synthesis.** "What if we use MLflow for ML-specific metadata and OTel for the trace propagation layer, so we get both? ML engineers interact with MLflow as they already do, and we get cross-service trace correlation through OTel."
5. **Defer gracefully.** "You know the infra better than I do. What's the migration effort for existing MLflow users if we go the OTel route?"

---

## Scenario 4: "PM from Another Team Wants Different Priorities"

**Setup:** The AI DJ PM says "We need custom evaluation metrics for music commentary. Your generic platform doesn't serve us."

**Your approach:**
1. **Validate their need.** "You're right -- music commentary evaluation is domain-specific. Generic metrics won't catch everything."
2. **Separate custom from common.** "I see two layers: (1) the infrastructure for running evaluations at scale, which is common, and (2) the evaluation criteria, which should be team-specific. The platform handles layer 1 so you can focus on layer 2."
3. **Make them the design partner.** "Your team has the most sophisticated evaluation today. I'd love for you to be our first design partner -- you'd shape the platform to serve your needs, and we'd generalize the patterns for other teams."
4. **Show what they gain.** "With the platform, your custom evaluations run automatically in CI/CD, you get regression alerts, and your quality dashboards are in Backstage alongside everyone else's. Without it, you maintain all that infrastructure yourself."

---

## General Tips for the Stakeholder Round

1. **Never get defensive.** Pushback is the test. They want to see you stay calm and collaborative.
2. **Ask questions before answering.** "Help me understand what's driving that concern" is always a good opener.
3. **Use data, not authority.** You can't mandate anything as a platform PM. You have to earn adoption.
4. **Acknowledge tradeoffs.** "You're right that this adds complexity. The question is whether the value justifies it."
5. **Always have a concrete next step.** Don't end with agreement in principle -- end with "Let's schedule a 30-min session next week to map out the integration."
6. **Reference your experience naturally.** "At Bell, I faced a similar situation where distributed Google developers were skeptical of my process. I found that showing concrete time savings in their workflow was more effective than top-down mandates."
