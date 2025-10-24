#!/bin/bash
# AppDiscovery Quick Start Script
# Sets up and runs the complete application

set -e

echo "🚀 AppDiscovery Quick Start"
echo "=========================="
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.10+"
    exit 1
fi

echo "✓ Python found: $(python --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q sqlmodel sqlalchemy pydantic pydantic-settings requests typer rich fastapi uvicorn
echo "✓ Dependencies installed"
echo ""

# Initialize database
echo "💾 Initializing database..."
python -m apps.ingest.cli init
echo "✓ Database initialized"
echo ""

# Discover sample apps
echo "🔍 Discovering sample apps..."
python -m apps.ingest.cli discover \
    --store apple \
    --lang en \
    --country US \
    --q "budget" \
    --limit 10
echo "✓ Discovered apps"
echo ""

# Enrich with details and signals
echo "📊 Enriching apps with details and signals..."
python -m apps.ingest.cli enrich \
    --since $(date -d '7 days ago' +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d) \
    --compute-signals
echo "✓ Apps enriched"
echo ""

# Start API in background
echo "🌐 Starting API server..."
python -m apps.api.main &
API_PID=$!
echo "✓ API running on http://localhost:8000 (PID: $API_PID)"
echo ""

# Wait for API to start
sleep 3

# Test API
echo "🧪 Testing API..."
curl -s http://localhost:8000/stats | python -m json.tool | head -20
echo "✓ API responding"
echo ""

# Serve dashboard
echo "🎨 Starting dashboard..."
cd web/static
python -m http.server 3000 &
DASHBOARD_PID=$!
cd ../..
echo "✓ Dashboard running on http://localhost:3000 (PID: $DASHBOARD_PID)"
echo ""

echo "=========================="
echo "✅ AppDiscovery is ready!"
echo ""
echo "📍 Open these URLs:"
echo "   Dashboard:  http://localhost:3000"
echo "   API Docs:   http://localhost:8000/docs"
echo "   API:        http://localhost:8000"
echo ""
echo "🛑 To stop:"
echo "   kill $API_PID $DASHBOARD_PID"
echo ""
echo "Press Ctrl+C to stop both servers..."
wait
