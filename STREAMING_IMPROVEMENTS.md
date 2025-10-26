# Streaming Fetch Pattern & Export - Implementation Guide

## Summary
Add these improvements to `opportunities.html` to show results as they arrive, not after all complete.

---

## 1. Streaming Concurrent Fetcher (add to `<script>` section)

```javascript
// Add after the CONCURRENCY constant
const STREAM_POOL_SIZE = 6; // Parallel requests

/**
 * Streaming concurrent task executor with async iterator.
 * Yields results as soon as each task completes, not after all finish.
 */
async function* streamWithConcurrency(tasks, poolSize = STREAM_POOL_SIZE) {
    let taskIndex = 0;
    const running = new Set();
    const results = [];
    let nextResultIndex = 0;

    const startNext = () => {
        if (taskIndex >= tasks.length) return;

        const currentIndex = taskIndex++;
        const promise = tasks[currentIndex]()
            .then(result => ({ index: currentIndex, result }))
            .catch(error => ({ index: currentIndex, error }));

        running.add(promise);

        promise.finally(() => {
            running.delete(promise);
            startNext();
        });
    };

    // Start initial pool
    while (running.size < poolSize && taskIndex < tasks.length) {
        startNext();
    }

    // Yield results as they complete
    while (running.size > 0 || nextResultIndex < tasks.length) {
        if (running.size === 0) break;

        const settled = await Promise.race([...running]);
        results[settled.index] = settled;

        // Yield any completed results in order
        while (results[nextResultIndex]) {
            const item = results[nextResultIndex];
            nextResultIndex++;

            if (item.error) {
                console.error(`Task ${item.index} failed:`, item.error);
                yield { error: item.error, index: item.index };
            } else {
                yield item.result;
            }
        }
    }
}

/**
 * Create a task function for fetching insights for one app.
 * Checks cache first, then calls API if needed.
 */
function makeInsightTask(app) {
    return async () => {
        const key = String(app.id);

        // Check cache first
        const cached = insightsCache.get(key);
        if (cached && Date.now() - cached.fetchedAt < INSIGHTS_TTL_MS) {
            return { app, insights: cached.data, fromCache: true };
        }

        // Fetch from API
        try {
            const response = await fetch(`${API_BASE}/apps/${app.id}/ai-insights`);
            const data = await response.json();
            const insights = data.insights || {};

            // Store in cache
            insightsCache.set(key, {
                data: insights,
                fetchedAt: Date.now()
            });
            saveCacheToSession();

            return { app, insights, fromCache: false };
        } catch (error) {
            console.error(`Failed to fetch insights for app ${app.id}:`, error);
            return { app, insights: null, error };
        }
    };
}
```

---

## 2. Replace `fetchInsightsWithConcurrency()` function

**Find the existing `fetchInsightsWithConcurrency()` function and replace it with:**

```javascript
// Fetch insights with streaming (shows results immediately as they arrive)
async function fetchInsightsWithConcurrency(apps, refresh = false) {
    const results = new Map();

    // If refresh, clear cache for these apps
    if (refresh) {
        apps.forEach(app => insightsCache.delete(String(app.id)));
    }

    // Build tasks
    const tasks = apps.map(makeInsightTask);
    const total = tasks.length;
    let done = 0;
    let fromCacheCount = 0;

    // Show progress bar
    const progressContainer = document.getElementById('progress-container');
    const progressLabel = document.getElementById('progress-label');
    const progressBarFill = document.getElementById('progress-bar-fill');

    progressContainer.classList.add('active');
    progressLabel.textContent = `Fetching insights: 0 / ${total}`;
    progressBarFill.style.width = '0%';

    // Stream results as they arrive
    for await (const item of streamWithConcurrency(tasks, STREAM_POOL_SIZE)) {
        if (item.error) {
            done++;
            continue;
        }

        const { app, insights, fromCache } = item;
        if (fromCache) fromCacheCount++;

        results.set(app.id, insights);
        done++;

        // Update progress
        const percent = Math.round((done / total) * 100);
        progressLabel.textContent = `Fetching insights: ${done} / ${total} (${fromCacheCount} cached)`;
        progressBarFill.style.width = `${percent}%`;

        // IMMEDIATE RENDER: Process and display this app right away
        const includeMedium = document.getElementById('includeMedium').checked;
        const showInconclusive = document.getElementById('showInconclusive').checked;

        const gateResult = passesGates(app, insights, includeMedium, showInconclusive);

        if (gateResult.passed) {
            // Render opportunity card immediately
            const score = calculateOpportunityScore(insights, app.signals);
            renderSingleOpportunityCard(app, insights, score);
        } else {
            // Add to rejected list immediately
            renderSingleRejectedCard(app, insights, gateResult);
        }
    }

    // Hide progress bar when done
    setTimeout(() => {
        progressContainer.classList.remove('active');
    }, 1000);

    console.log(`Streaming fetch complete: ${done} apps, ${fromCacheCount} from cache`);
    return results;
}
```

---

## 3. Add Incremental Rendering Functions

```javascript
/**
 * Render a single opportunity card immediately (don't wait for all)
 */
function renderSingleOpportunityCard(app, insights, score) {
    const container = document.getElementById('app-list');

    // Check if card already exists (for refresh)
    let existingCard = document.querySelector(`[data-app-id="${app.id}"]`);

    const cardHTML = generateOpportunityCardHTML(app, insights, score);

    if (existingCard) {
        existingCard.outerHTML = cardHTML;
    } else {
        // Append new card
        container.insertAdjacentHTML('beforeend', cardHTML);
    }

    // Update stats bar
    updateStatsBar();
}

/**
 * Render a single rejected card in debug section
 */
function renderSingleRejectedCard(app, insights, gateResult) {
    const debugList = document.getElementById('rejected-list');

    // Group by gate
    const gate = gateResult.gate || 'unknown';
    let gateSection = document.querySelector(`[data-gate="${gate}"]`);

    if (!gateSection) {
        // Create gate section if it doesn't exist
        const gateSectionHTML = `
            <div data-gate="${gate}" class="gate-section">
                <strong>${gate.replace(/_/g, ' ').toUpperCase()}</strong>
                <div class="gate-apps" id="gate-${gate}"></div>
            </div>
        `;
        debugList.insertAdjacentHTML('beforeend', gateSectionHTML);
        gateSection = document.querySelector(`[data-gate="${gate}"]`);
    }

    const gateApps = document.getElementById(`gate-${gate}`);
    const cardHTML = generateRejectedCardHTML(app, insights, gateResult);

    gateApps.insertAdjacentHTML('beforeend', cardHTML);
}

// Helper: Generate opportunity card HTML
function generateOpportunityCardHTML(app, insights, score) {
    const mrrLow = insights.mrr_low || 0;
    const mrrMid = insights.mrr_mid || 0;
    const mrrHigh = insights.mrr_high || 0;

    return `
        <div class="app-card" data-app-id="${app.id}">
            <div class="app-header">
                <img src="${app.icon_url || '/placeholder.png'}" alt="${app.title}" class="app-icon">
                <div class="app-info">
                    <div class="app-title">${app.title}</div>
                    <div class="app-developer">${app.developer || 'Unknown'}</div>
                </div>
            </div>

            <div class="chips">
                ${!insights.has_en_locale ? '<span class="chip chip-success">No EN Locale</span>' : ''}
                ${!insights.has_en_equivalent ? '<span class="chip chip-success">No EN Equivalent</span>' : ''}
                <span class="chip chip-primary">${insights.difficulty}</span>
                ${mrrMid >= MIN_MRR ? '<span class="chip chip-warning">≥$5k MRR</span>' : ''}
            </div>

            <div class="opportunity-score">Score: ${score.toFixed(1)}</div>
            <div class="mrr-range">MRR: $${mrrLow.toFixed(0)} - $${mrrMid.toFixed(0)} - $${mrrHigh.toFixed(0)}</div>

            <div class="actions">
                <button class="btn btn-primary" onclick="window.open('https://apps.apple.com/app/id${app.store_app_id}', '_blank')">Open in Store</button>
                <button class="btn btn-secondary" onclick="refreshInsights(${app.id})">🔄 Refresh</button>
            </div>
        </div>
    `;
}

// Helper: Generate rejected card HTML
function generateRejectedCardHTML(app, insights, gateResult) {
    return `
        <div class="rejected-card">
            <strong>${app.title}</strong>
            <div>❌ ${gateResult.reason}</div>
            <a href="https://apps.apple.com/app/id${app.store_app_id}" target="_blank">View</a>
        </div>
    `;
}
```

---

## 4. Add CSV Export Function

```javascript
/**
 * Export opportunities to CSV file
 */
function exportToCSV() {
    const opportunities = []; // This should be populated from your filtered data

    // Collect opportunities that passed all gates
    for (const app of allApps) {
        const insights = enrichedApps.get(app.id);
        if (!insights) continue;

        const includeMedium = document.getElementById('includeMedium').checked;
        const showInconclusive = document.getElementById('showInconclusive').checked;
        const gateResult = passesGates(app, insights, includeMedium, showInconclusive);

        if (gateResult.passed) {
            const score = calculateOpportunityScore(insights, app.signals);
            opportunities.push({
                title: app.title,
                developer: app.developer,
                category: app.category,
                score: score.toFixed(1),
                mrr_low: insights.mrr_low || 0,
                mrr_mid: insights.mrr_mid || 0,
                mrr_high: insights.mrr_high || 0,
                confidence: Math.round((insights.mrr_confidence || 0) * 100),
                difficulty: insights.difficulty || 'Unknown',
                has_en_locale: insights.has_en_locale,
                has_en_equivalent: insights.has_en_equivalent,
                research_stage: insights.research_stage || 'unknown',
                store_url: `https://apps.apple.com/app/id${app.store_app_id}`
            });
        }
    }

    if (opportunities.length === 0) {
        alert('No opportunities to export');
        return;
    }

    // Generate CSV
    const headers = ['Title', 'Developer', 'Category', 'Score', 'MRR Low', 'MRR Mid', 'MRR High', 'Confidence %', 'Difficulty', 'Has EN Locale', 'Has EN Equivalent', 'Research Stage', 'Store URL'];
    const rows = opportunities.map(opp => [
        opp.title,
        opp.developer,
        opp.category,
        opp.score,
        opp.mrr_low,
        opp.mrr_mid,
        opp.mrr_high,
        opp.confidence,
        opp.difficulty,
        opp.has_en_locale,
        opp.has_en_equivalent,
        opp.research_stage,
        opp.store_url
    ]);

    const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `opportunities_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    console.log(`Exported ${opportunities.length} opportunities to CSV`);
}
```

---

## 5. Update `renderOpportunities()` to use streaming

**Replace the existing `renderOpportunities()` function with:**

```javascript
async function renderOpportunities() {
    const includeMedium = document.getElementById('includeMedium').checked;
    const showInconclusive = document.getElementById('showInconclusive').checked;
    const container = document.getElementById('app-list');

    // Clear existing cards
    container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading opportunities...</p></div>';

    // Reset stats
    stats = {
        candidates: 0,
        filteredLocale: 0,
        filteredEquivalent: 0,
        filteredDifficulty: 0,
        filteredMRR: 0
    };

    // Fetch insights with streaming (renders as each arrives)
    if (enrichedApps.size === 0 || needsRefresh) {
        container.innerHTML = ''; // Clear loading message
        enrichedApps = await fetchInsightsWithConcurrency(allApps);
        needsRefresh = false;
    } else {
        // Just re-render from cache
        container.innerHTML = '';
        const opportunities = [];
        const rejected = [];

        for (const app of allApps) {
            const insights = enrichedApps.get(app.id);
            if (!insights) continue;

            const gateResult = passesGates(app, insights, includeMedium, showInconclusive);

            if (gateResult.passed) {
                const score = calculateOpportunityScore(insights, app.signals);
                opportunities.push({ app, insights, score });
            } else {
                rejected.push({ app, insights, ...gateResult });
            }
        }

        // Render all at once (cache hit scenario)
        opportunities.sort((a, b) => b.score - a.score);
        opportunities.forEach(({ app, insights, score }) => {
            renderSingleOpportunityCard(app, insights, score);
        });

        renderDebugSection(rejected, allApps.length, opportunities.length);
    }

    updateStatsBar();
}
```

---

## Usage

1. **Copy the streaming functions** to your `<script>` section in opportunities.html
2. **Replace `fetchInsightsWithConcurrency()`** with the new streaming version
3. **Replace `renderOpportunities()`** with the updated version
4. **Add the export function** `exportToCSV()`
5. **Refresh the page** and click "Refresh All" to see results stream in one-by-one!

---

## Benefits

✅ **Immediate feedback** - See apps as they're analyzed, not after all complete
✅ **Progress indicator** - Shows X/Y completed with percentage bar
✅ **Better UX** - No more waiting 30-120 seconds with no feedback
✅ **Cache-aware** - Shows how many results came from cache
✅ **Export functionality** - Download opportunities as CSV
✅ **Cleaner nav** - Navigation bar to switch between pages
