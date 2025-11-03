#!/bin/bash

echo "🚀 Starting Job Search Crawler..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env with your settings before continuing."
    exit 1
fi

# Start services
echo "🐳 Starting Docker containers..."
docker-compose up -d

echo "⏳ Waiting for services to start..."
sleep 10

# Check if Ollama model exists
echo "🤖 Checking Ollama model..."
docker exec job-crawler-ollama ollama list | grep llama2 || {
    echo "📥 Downloading Ollama model (this may take a few minutes)..."
    docker exec job-crawler-ollama ollama pull llama2
}

echo ""
echo "✅ Job Search Crawler is running!"
echo ""
echo "📊 Dashboard: http://localhost:8001/static/index.html"
echo "🤖 OpenWebUI: http://localhost:3000"
echo "📚 API Docs: http://localhost:8001/docs"
echo ""
echo "To view logs: docker-compose logs -f job-crawler"
echo "To stop: docker-compose down"
echo ""
