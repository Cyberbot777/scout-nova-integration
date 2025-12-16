# Nova Sonic Implementation Comparison

This document compares the two Nova Sonic voice agent implementations for A/B testing and evaluation.

## Summary

| Aspect | Direct Bedrock | Strands BidiAgent |
|--------|---------------|-------------------|
| **Latency** | Lower (direct streaming) | Slightly higher (SDK layer) |
| **Speech Quality** | Smoother | Good |
| **Interruptions** | Instant (native protocol) | Slight delay (event translation) |
| **Tool Handling** | Manual code required | Automatic via SDK |
| **Maintenance** | Higher (manual updates) | Lower (SDK handles updates) |
| **Team Standards** | Does not follow | Follows "Strands first" |
| **Status** | Proven stable | Experimental (beta) |

---

## Architecture Comparison

### Direct Bedrock
```
Frontend → WebSocket → portal_agent.py → Bedrock Nova Sonic API
                       ├─ Manual tool calling
                       ├─ Manual prompt injection  
                       └─ Direct byte forwarding
```

**Layers:** 3 (Frontend → Server → Bedrock)

### Strands BidiAgent
```
Frontend → WebSocket → portal_agent.py → BidiAgent → Nova Sonic
                       ├─ Custom I/O handlers
                       ├─ Event translation
                       └─ SDK abstraction layer
```

**Layers:** 5 (Frontend → Server → Custom I/O → BidiAgent → Nova Sonic)

---

## User Experience Metrics

### Test Scenarios

Track these metrics for both implementations:

| Metric | Direct Bedrock | Strands BidiAgent | Winner |
|--------|---------------|-------------------|--------|
| **Time to First Audio** | ___ ms | ___ ms | |
| **Interruption Response Time** | ___ ms | ___ ms | |
| **Audio Quality (1-10)** | ___ | ___ | |
| **Conversation Naturalness (1-10)** | ___ | ___ | |
| **Tool Call Success Rate** | ___% | ___% | |
| **Tool Call Latency** | ___ ms | ___ ms | |

### User Feedback

Track subjective feedback from brokers:
- Which feels more responsive?
- Which sounds more natural?
- Which interruption feels better?
- Overall preference?

---

## Code Complexity

### Direct Bedrock
```python
# Manual tool handling
tools = await load_gateway_tools()
tool_result = await execute_tool(tool_name, tool_input)

# Manual prompt injection
bedrock_events = inject_system_prompt(events, SYSTEM_PROMPT)

# Manual event forwarding
await ws.send(bedrock_event)
```

**Lines of Code:** ~450  
**Custom Code:** High (all tool/prompt logic)

### Strands BidiAgent  
```python
# Automatic tool handling
agent = BidiAgent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT
)

# Custom I/O bridge
await agent.run(inputs=[ws_input], outputs=[ws_output])
```

**Lines of Code:** ~570  
**Custom Code:** Medium (I/O handlers only)

---

## Engineering Trade-offs

### Direct Bedrock

**Benefits:**
- Lowest possible latency
- Full control over protocol
- Best user experience
- No experimental dependencies

**Costs:**
- Manual tool calling code
- Manual prompt injection
- Protocol updates require manual changes
- Does not follow team standards
- More testing required

### Strands BidiAgent

**Benefits:**
- Follows team "Strands first" standard
- Automatic tool handling
- SDK handles protocol updates
- Cleaner architecture
- Less custom code

**Costs:**
- Additional latency from SDK layer
- Experimental status (potential bugs)
- Less control over protocol
- Slightly degraded UX
- Event translation overhead

---

## Recommendation Decision Framework

### Choose Direct Bedrock If:
1. User experience is top priority
2. Latency/interruption quality is critical
3. Willing to maintain custom code
4. Production stability is essential

### Choose Strands BidiAgent If:
1. Team standards are top priority
2. Automatic tool handling is valuable
3. Long-term maintainability is key
4. Slight UX degradation is acceptable

---

## Test Plan

### Phase 1: Technical Testing (Week 1)
- [ ] Measure latency for both implementations
- [ ] Test interruption response times
- [ ] Verify tool execution accuracy
- [ ] Load testing (concurrent users)

### Phase 2: User Testing (Week 2)
- [ ] A/B test with 5 internal brokers
- [ ] Collect qualitative feedback
- [ ] Measure user preference
- [ ] Document any UX issues

### Phase 3: Decision (Week 3)
- [ ] Review metrics and feedback
- [ ] Make production recommendation
- [ ] Document decision rationale
- [ ] Plan production deployment

---

## Current Status

**Date:** December 16, 2025

**Both implementations:**
- ✅ Voice streaming working
- ✅ Tool integration functional
- ✅ Interruption support implemented
- ⏳ Production deployment pending

**Next Steps:**
1. Run formal A/B testing
2. Collect user feedback
3. Make final implementation choice
4. Deploy to production

---

## Notes

Add observations and learnings here as testing progresses.


