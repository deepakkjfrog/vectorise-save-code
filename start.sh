#!/bin/bash

echo "🚀 Code Vectorizer - Quick Start"
echo "================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file and add your OpenAI API key!"
    echo "   You can get one from: https://platform.openai.com/api-keys"
    echo ""
    echo "Press Enter when you've added your API key..."
    read
fi

# Check if OpenAI API key is set
if ! grep -q "your_openai_api_key_here" .env; then
    echo "✅ OpenAI API key found in .env"
else
    echo "❌ Please add your OpenAI API key to .env file"
    echo "   Edit .env and replace 'your_openai_api_key_here' with your actual key"
    exit 1
fi

echo "🐳 Starting Code Vectorizer services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

echo ""
echo "✅ Code Vectorizer is ready!"
echo ""
echo "🌐 Services:"
echo "   • API Server: http://localhost:8000"
echo "   • API Docs:   http://localhost:8000/docs"
echo "   • pgAdmin:    http://localhost:8080 (admin@vectorize.com / admin123)"
echo ""
echo "📖 Quick Examples:"
echo "   • Vectorize a repo: curl -X POST http://localhost:8000/api/vectorize -H 'Content-Type: application/json' -d '{\"repo_url\":\"https://github.com/username/repo\",\"username\":\"test_user\"}'"
echo "   • Search code: curl -X POST http://localhost:8000/api/search -H 'Content-Type: application/json' -d '{\"query\":\"function to parse JSON\",\"username\":\"test_user\"}'"
echo ""
echo "🛑 To stop: docker-compose down" 