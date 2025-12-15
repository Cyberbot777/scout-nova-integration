# Testing Both Implementations

We now have TWO working servers to compare:

## Server 1: Direct Bedrock (voice_server.py) - Port 8080
**Status:** Working  
**Approach:** Manual Bedrock API handling  
**Start:** `python voice_server.py --port 8080`

## Server 2: Strands BidiAgent (bidi_websocket_server.py) - Port 8081  
**Status:** Ready to test  
**Approach:** Proper Strands SDK  
**Start:** `python bidi_websocket_server.py --port 8081`

---

## Test Plan

### Step 1: Test with Direct Bedrock (Current Working)
1. Ensure `voice_server.py` is running on port 8080
2. Frontend connects to `ws://localhost:8080`
3. Test voice conversation
4. ✅ Should work (we know it does)

### Step 2: Test with Strands BidiAgent
1. Stop `voice_server.py`
2. Start `bidi_websocket_server.py` on port 8081
3. Update frontend VoiceAgent.js line ~240:
   ```javascript
   // Change from:
   this.socket = new WebSocket('ws://localhost:8080');
   // To:
   this.socket = new WebSocket('ws://localhost:8081');
   ```
4. Test voice conversation
5. Compare behavior

### Step 3: Debug if Needed
Both servers are logging heavily. Check terminal output to compare:
- How messages are formatted
- How tools are executed  
- Response timing

---

## Key Differences

| Feature | voice_server.py | bidi_websocket_server.py |
|---------|----------------|--------------------------|
| **Bedrock Integration** | Manual API calls | Strands BidiAgent (managed) |
| **Tool Handling** | Manual execution | Built-in to BidiAgent |
| **Nova Sonic Protocol** | We manage it | BidiAgent manages it |
| **Audio Format** | Expects Nova Sonic events | Extracts raw audio |
| **Maintainability** | We maintain protocol | Strands team maintains |

---

## Expected Outcome

**If Strands works:** Delete `voice_server.py`, use `bidi_websocket_server.py` as the standard.

**If issues found:** Debug and compare with working implementation.

---

**Current Status:**  
- ✅ Both servers running  
- 🔄 Ready to test Strands version  
- 📝 Will document results

**Next:** Change frontend WebSocket URL to 8081 and test!

