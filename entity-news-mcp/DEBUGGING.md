# Debugging Timeout Issues

## Where Timeouts Can Occur

### 1. **OpenAI Agent Builder Side** (Client)
- **Default timeout**: Usually 60-120 seconds
- **No configurable timeout**: OpenAI doesn't expose timeout settings in Agent Builder UI
- **What happens**: If your server takes longer than their timeout, the connection is closed
- **Error you'll see**: "Connection closed before response could be fully read" or "unexpected EOF"

### 2. **ngrok Side** (Tunnel)
- **Free tier timeout**: ~60 seconds for request processing
- **Connection timeout**: Varies, but typically 2-5 minutes for idle connections
- **What happens**: ngrok closes the connection if request takes too long
- **Error you'll see**: "502 Bad Gateway" or connection reset

### 3. **Your Server Side** (Uvicorn/FastAPI)
- **Current settings**:
  - `timeout_keep_alive`: 300 seconds (5 minutes)
  - API call timeout: 30 seconds per API
  - Total fetch timeout: 60 seconds
- **What happens**: Server keeps connection alive, but if processing takes too long, client may timeout first

### 4. **External APIs** (NewsAPI, GNews)
- **NewsAPI timeout**: 30 seconds (we set this)
- **GNews timeout**: 30 seconds (we set this)
- **What happens**: If APIs are slow, your server waits, causing overall request to be slow

## How to Debug

### Step 1: Check Server Logs

When a timeout occurs, check your server terminal. You should see logs like:

```
[abc123] POST /sse - START
Starting async news fetch for: Apple
Fetching from NewsAPI for: Apple
Fetching from GNews for: Apple
NewsAPI completed in 2.345s, returned 10 articles
GNews completed in 1.234s, returned 10 articles
Async news fetch COMPLETE: 2.456s (parallel) - 20 total articles
[abc123] POST /sse - COMPLETE in 2.567s (Status: 200)
```

**Look for:**
- How long each API call takes
- If any API times out
- Total request processing time
- Any "SLOW REQUEST" or "VERY SLOW REQUEST" warnings

### Step 2: Check ngrok Dashboard

1. Open http://127.0.0.1:4040
2. Look at the "Requests" tab
3. Find the failed request
4. Check:
   - Request duration
   - Response status
   - Any error messages
   - Request/Response body size

**What to look for:**
- If request shows "0 bytes captured" → Connection closed before response sent
- If duration > 60s → Likely ngrok timeout
- If status is 502 → ngrok couldn't reach your server

### Step 3: Test Manually

Test your server directly (bypassing ngrok):

```bash
# Test locally
curl -X POST http://localhost:8000/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_entity_news","arguments":{"entity_name":"Apple"}},"id":1}' \
  -w "\nTime: %{time_total}s\n"

# Test via ngrok
curl -X POST https://your-ngrok-url.ngrok-free.app/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_entity_news","arguments":{"entity_name":"Apple"}},"id":1}' \
  -w "\nTime: %{time_total}s\n"
```

Compare the times. If ngrok is much slower, that's the bottleneck.

### Step 4: Monitor Real-Time

Watch your server logs while Agent Builder makes requests:

```bash
# In terminal where server is running, you'll see:
[abc123] POST /sse - START
Starting async news fetch for: Tesla
Fetching from NewsAPI for: Tesla
Fetching from GNews for: Tesla
NewsAPI completed in 3.456s, returned 10 articles
GNews completed in 2.123s, returned 10 articles
Async news fetch COMPLETE: 3.567s (parallel) - 20 total articles
[abc123] POST /sse - COMPLETE in 3.678s (Status: 200)
```

If you see "COMPLETE" but Agent Builder still times out, the issue is on OpenAI's side.

## Common Scenarios

### Scenario 1: Server completes but client times out
**Symptoms:**
- Server logs show "COMPLETE" with reasonable time (< 30s)
- ngrok shows successful response
- Agent Builder still shows timeout

**Cause:** OpenAI's timeout is shorter than your response time

**Solution:**
- Optimize API calls (already using async/parallel)
- Consider caching results
- Reduce number of articles returned

### Scenario 2: ngrok timeout
**Symptoms:**
- Server logs show request started but never completed
- ngrok shows "502 Bad Gateway" or "Connection closed"
- Request duration > 60s in ngrok

**Cause:** ngrok free tier timeout

**Solution:**
- Upgrade to ngrok paid plan (longer timeouts)
- Optimize to respond faster
- Use a different tunnel service (Cloudflare Tunnel, etc.)

### Scenario 3: External API timeout
**Symptoms:**
- Server logs show "NewsAPI TIMEOUT" or "GNews TIMEOUT"
- Request takes > 30s

**Cause:** External APIs are slow or down

**Solution:**
- Already handled - returns empty list for that source
- Consider adding retry logic
- Use fallback APIs

### Scenario 4: Intermittent timeouts
**Symptoms:**
- Works sometimes, fails other times
- No pattern to failures

**Cause:** Network issues, API rate limits, or OpenAI's timeout varies

**Solution:**
- Check for rate limiting in logs
- Monitor network stability
- Add retry logic in Agent Builder instructions

## Quick Debugging Checklist

- [ ] Check server logs for request timing
- [ ] Check ngrok dashboard for request status
- [ ] Test manually with curl to isolate issue
- [ ] Check if external APIs are responding
- [ ] Monitor server resource usage (CPU, memory)
- [ ] Check for rate limiting errors
- [ ] Verify ngrok tunnel is still active

## Monitoring Endpoint

Access `/metrics` to check server status:

```bash
curl http://localhost:8000/metrics
```

Returns:
- Server uptime
- Memory usage
- CPU usage
- Timeout configurations

## Next Steps

If timeouts persist:

1. **Reduce response time**: Limit number of articles, add caching
2. **Upgrade ngrok**: Paid plan has longer timeouts
3. **Deploy to cloud**: Use a service with better timeout handling
4. **Add retry logic**: Handle transient failures gracefully
5. **Contact OpenAI**: If their timeout is too short, they may need to adjust

