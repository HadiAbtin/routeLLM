#!/bin/bash

# Test script for Anthropic models
# Usage: ./test-anthropic-models.sh

# Configuration
BASE_URL="http://localhost:8000"
EMAIL="admin@example.com"
PASSWORD="Aa123456Aa@"

echo "=== Testing Anthropic Models ==="
echo ""

# Step 0: Check if API is running
echo "0. Checking API health..."
HEALTH_RESPONSE=$(curl -s "${BASE_URL}/health")
if [ $? -ne 0 ] || [ -z "$HEALTH_RESPONSE" ]; then
  echo "❌ API is not running or not accessible at ${BASE_URL}"
  echo "Please make sure the backend is running!"
  exit 1
fi
echo "✅ API is running"
echo ""

# Step 1: Login
echo "1. Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${EMAIL}\",
    \"password\": \"${PASSWORD}\"
  }")

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed!"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Login successful!"
echo "Token: ${TOKEN:0:20}..."
echo ""

# Step 2: Test each model
MODELS=(
  "claude-sonnet-4-5-20250929"
  "claude-haiku-4-5-20251001"
  "claude-opus-4-5-20251101"
)

for MODEL in "${MODELS[@]}"; do
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Testing model: $MODEL"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  RESPONSE=$(curl -s -X POST "${BASE_URL}/v1/llm/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "{
      \"provider\": \"anthropic\",
      \"model\": \"${MODEL}\",
      \"messages\": [
        {
          \"role\": \"user\",
          \"content\": \"You are being tested. Please respond with EXACTLY this format: MODEL_NAME=[your exact model name]. For example, if you are Claude 3.5 Haiku, respond: MODEL_NAME=claude-3-5-haiku-20241022. If you are Claude 3.5 Sonnet, respond: MODEL_NAME=claude-3-5-sonnet-20241022. Be precise and use the exact model identifier.\"
        }
      ]
    }")
  
  echo "Response:"
  echo "$RESPONSE" | jq '.'
  
  # Extract model from response
  RESPONSE_MODEL=$(echo "$RESPONSE" | jq -r '.model // "unknown"')
  CONTENT=$(echo "$RESPONSE" | jq -r '.message.content // "no content"')
  
  echo ""
  echo "📊 Response Model: $RESPONSE_MODEL"
  echo "💬 Content: $CONTENT"
  
  if [ "$RESPONSE_MODEL" == "$MODEL" ]; then
    echo "✅ Model matches!"
  else
    echo "⚠️  Model mismatch! Expected: $MODEL, Got: $RESPONSE_MODEL"
  fi
  
  echo ""
  sleep 1
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All tests completed!"

