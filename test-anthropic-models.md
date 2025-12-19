# دستورات curl برای تست مدل‌های Anthropic

## 1. لاگین

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "Admin123!"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "must_change_password": true
}
```

---

## 2. تست مدل Claude Sonnet 4.5

```bash
curl -X POST "http://localhost:8000/v1/llm/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "provider": "anthropic",
    "model": "claude-sonnet-4-5-20250929",
    "messages": [
      {
        "role": "user",
        "content": "Hello! Please tell me which model you are. Just say: I am [model name]."
      }
    ]
  }'
```

---

## 3. تست مدل Claude Haiku 4.5

```bash
curl -X POST "http://localhost:8000/v1/llm/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001",
    "messages": [
      {
        "role": "user",
        "content": "Hello! Please tell me which model you are. Just say: I am [model name]."
      }
    ]
  }'
```

---

## 4. تست مدل Claude Opus 4.5

```bash
curl -X POST "http://localhost:8000/v1/llm/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "provider": "anthropic",
    "model": "claude-opus-4-5-20251101",
    "messages": [
      {
        "role": "user",
        "content": "Hello! Please tell me which model you are. Just say: I am [model name]."
      }
    ]
  }'
```

---

## Response Format

هر response شامل فیلد `model` است که مشخص می‌کند با کدام مدل پاسخ داده شده:

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "message": {
    "role": "assistant",
    "content": "I am claude-sonnet-4-5-20250929."
  },
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 8,
    "total_tokens": 23
  }
}
```

---

## استفاده از Script

برای تست خودکار همه مدل‌ها:

```bash
chmod +x test-anthropic-models.sh
./test-anthropic-models.sh
```

---

## نکات مهم

1. **Token**: بعد از لاگین، `access_token` را از response کپی کنید و در دستورات بعدی استفاده کنید.
2. **Base URL**: اگر API در پورت دیگری اجرا می‌شود، `localhost:8000` را تغییر دهید.
3. **Model Field**: فیلد `model` در response همیشه نشان می‌دهد که با کدام مدل پاسخ داده شده است.
4. **Provider**: حتماً `"provider": "anthropic"` را در request مشخص کنید.

