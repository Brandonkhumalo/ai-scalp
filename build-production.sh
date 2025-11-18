#!/bin/bash
set -e

echo "🔨 Building ZimAI Trader for production..."

# Build React frontend
echo "📦 Building frontend (React + Vite)..."
npm run build

# Collect Django static files
echo "📁 Collecting Django static files..."
cd backend
python manage.py collectstatic --noinput

echo "✅ Build complete!"
