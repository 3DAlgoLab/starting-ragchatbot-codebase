# Fallback Implementation for Phi-4 Tool Calling Limitations

## Problem Discovery

### Initial Issue
Source citations were not appearing in the chat interface despite the backend code being correctly structured to extract and return them.

### Investigation Process

1. **Checked the data flow** (backend → frontend):
   - ✅ `vector_store.py:249` - `get_lesson_link()` correctly retrieves lesson links
   - ✅ `search_tools.py:112-119` - `_format_results()` creates source objects with links
   - ✅ `app.py:46` - API response type supports `List[Dict[str, Any]]` for sources
   - ✅ `script.js:126-130` - Frontend renders links as clickable `<a>` tags
   - ✅ `style.css:249-258` - CSS styling makes links invisible but clickable

2. **Added debug logging** to trace the issue:
   ```python
   # rag_system.py
   print(f"[DEBUG] Sources retrieved: {sources}")

   # search_tools.py
   print(f"[DEBUG] Stored {len(sources)} sources in search tool")

   # ai_generator.py
   print(f"[DEBUG] Sending {len(tools)} tools to model")
   print(f"[DEBUG] Model response has tool_calls: {hasattr(...)}")
   ```

3. **Root cause identified**:
   ```
   [DEBUG] Sending 1 tools to model
   [DEBUG] Model response has tool_calls: False
   [DEBUG] Sources retrieved: []
   ```

   **The AI was not using the search tool at all**, so no sources were being generated.

### Why Tool Calling Failed

Tested Phi-4 directly via SGLang server:
```bash
curl -X POST http://localhost:7501/v1/chat/completions \
  -d '{
    "tools": [...],
    "tool_choice": "required"
  }'
```

Response showed `"tool_calls": null` even with `"required"` setting.

**Conclusion**: Phi-4 multimodal-instruct model via SGLang does not reliably support OpenAI-style tool calling, despite accepting the API parameters.

## Solution: Automatic Search Fallback

### Architecture Change

**Before (Tool-Based):**
```
User Query → AI decides whether to search → Tool execution → AI synthesizes
```

**After (Always-Search):**
```
User Query → Automatic search → Provide context to AI → AI synthesizes
```

### Implementation Details

#### 1. Modified `rag_system.py` Query Method

```python
def query(self, query: str, session_id: Optional[str] = None):
    # FALLBACK: Phi-4 doesn't support tool calling reliably
    # Always search first and provide context to AI

    # 1. Perform automatic search
    search_results = self.vector_store.search(query=query)

    # 2. Extract sources with links
    sources = []
    context_text = ""

    if not search_results.is_empty() and not search_results.error:
        for doc, meta in zip(search_results.documents, search_results.metadata):
            course_title = meta.get('course_title')
            lesson_num = meta.get('lesson_number')

            # Build source text
            source_text = course_title
            if lesson_num is not None:
                source_text += f" - Lesson {lesson_num}"

            # Get lesson link from vector store
            lesson_link = None
            if lesson_num is not None:
                lesson_link = self.vector_store.get_lesson_link(
                    course_title, lesson_num
                )

            # Store source object
            source_obj = {"text": source_text}
            if lesson_link:
                source_obj["link"] = lesson_link
            sources.append(source_obj)

            # Build context for AI
            context_parts.append(f"[{source_text}]\n{doc}")

        context_text = "\n\n".join(context_parts)

    # 3. Create enhanced prompt with search results
    if context_text:
        prompt = f"""Use the following course content to answer the question.

Course Content:
{context_text}

Question: {query}"""
    else:
        prompt = f"""Answer this question. If it's about course materials
and no relevant content was found, say so briefly.

Question: {query}"""

    # 4. Generate response WITHOUT tools
    response = self.ai_generator.generate_response(
        query=prompt,
        conversation_history=history,
        tools=None,  # Disable tools
        tool_manager=None
    )

    # 5. Return response with sources
    return response, sources
```

#### 2. Source Data Structure

Sources are now returned as dictionaries with optional link field:

```python
# Without link
{"text": "Course Name - Lesson 1"}

# With link
{
    "text": "Course Name - Lesson 1",
    "link": "https://learn.deeplearning.ai/courses/..."
}
```

#### 3. Frontend Rendering

```javascript
// script.js - Format sources with clickable links
const formattedSources = sources.map(source => {
    if (source.link) {
        return `<a href="${source.link}" target="_blank" class="source-link">
                ${source.text}</a>`;
    }
    return source.text;
}).join(', ');
```

```css
/* style.css - Invisible but clickable links */
.source-link {
    color: inherit;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.2s ease;
}

.source-link:hover {
    opacity: 0.7;
}
```

## Benefits of This Approach

### Advantages
1. **Reliability**: No dependency on unstable tool calling support
2. **Simplicity**: Straightforward control flow, easier to debug
3. **Performance**: No extra LLM round-trips for tool decisions
4. **Consistency**: Every query gets searched, ensuring sources always appear

### Trade-offs
1. **Over-searching**: Searches even for general knowledge questions
2. **Context window usage**: Search results always included in prompt
3. **Less flexible**: Can't dynamically choose whether to search

## Alternative Approaches Considered

### 1. Prompt Engineering for Tool Usage
Tried making system prompt more aggressive:
```python
SYSTEM_PROMPT = "**ALWAYS use the search tool for ANY question...**"
```
**Result**: Still didn't work reliably with Phi-4.

### 2. Force Tool Choice
Tried setting `tool_choice: "required"`:
```python
api_params["tool_choice"] = "required"
```
**Result**: Model still returned `tool_calls: null`.

### 3. ReAct Pattern
Could implement explicit "Thought → Action → Observation" prompting.
**Not pursued**: More complex, still relies on model following format.

### 4. Function Calling Parsers
Could parse structured output formats like JSON function calls.
**Not pursued**: Phi-4 not fine-tuned for this, unreliable.

## Testing Results

### Before Fix
```json
{
  "answer": "MCP stands for Master of Computer Science...",
  "sources": [],
  "session_id": "session_1"
}
```

### After Fix
```json
{
  "answer": "MCP servers are data stores that can be used for various applications...",
  "sources": [
    {
      "text": "MCP: Build Rich-Context AI Apps with Anthropic - Lesson 8",
      "link": "https://learn.deeplearning.ai/courses/mcp-build-rich-context-ai-apps-with-anthropic/lesson/l8ms0/configuring-servers-for-claude-desktop"
    },
    {
      "text": "MCP: Build Rich-Context AI Apps with Anthropic - Lesson 1",
      "link": "https://learn.deeplearning.ai/courses/mcp-build-rich-context-ai-apps-with-anthropic/lesson/ccsd0/why-mcp"
    }
  ],
  "session_id": "session_1"
}
```

## Lessons Learned

### Key Takeaways

1. **Model capabilities vary widely**: Not all models support all OpenAI API features, even if they accept the parameters.

2. **Test assumptions early**: Direct API testing revealed the issue quickly:
   ```bash
   curl → model → check tool_calls field
   ```

3. **Fallback patterns are valuable**: When advanced features fail, simple approaches often work better.

4. **Debug logging is essential**: Strategic print statements pinpointed exactly where the flow broke:
   ```
   Tools sent ✓ → Tool calls received ✗ → Sources empty ✗
   ```

5. **User experience over architecture**: The "always search" approach may be architecturally simpler, but it works reliably.

### When to Use Tool Calling vs. Always-Search

**Use Tool Calling When:**
- Model reliably supports it (GPT-4, Claude, etc.)
- Need dynamic decisions (search vs. calculate vs. query database)
- Want to minimize unnecessary operations
- Context window is limited

**Use Always-Search When:**
- Model has poor tool calling support
- Search is cheap/fast
- Most queries need search anyway
- Simplicity is more important than optimization

## Future Improvements

### Potential Enhancements

1. **Smart pre-filtering**: Detect obvious non-course questions before searching
   ```python
   if is_procedural_question(query):
       return answer_without_search(query)
   ```

2. **Cache search results**: Avoid re-searching similar queries
   ```python
   cache_key = hash(query)
   if cache_key in search_cache:
       return cached_results
   ```

3. **Hybrid approach**: Try tool calling, fallback to always-search
   ```python
   if model_supports_tools():
       result = try_tool_calling()
   else:
       result = always_search()
   ```

4. **Model upgrade**: Switch to a model with better tool support
   - Claude 3.5 Sonnet (excellent tool calling)
   - GPT-4 Turbo (reliable function calling)
   - Llama 3.1 405B (improved tool use)

## References

### Related Files
- `backend/rag_system.py:102-184` - Main query processing logic
- `backend/vector_store.py:249-267` - Lesson link retrieval
- `backend/search_tools.py:91-127` - Source formatting (legacy, kept for compatibility)
- `frontend/script.js:123-139` - Source rendering with links
- `frontend/style.css:249-258` - Clickable link styling

### Debugging Commands
```bash
# Test search directly
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are MCP servers?"}'

# Check SGLang tool support
curl -X POST http://localhost:7501/v1/chat/completions \
  -d '{"tools": [...], "tool_choice": "required"}'

# Monitor server logs
tail -f /tmp/server.log | grep -E "DEBUG|tool"
```

### Documentation
- OpenAI Tool Calling: https://platform.openai.com/docs/guides/function-calling
- SGLang Documentation: https://sgl-project.github.io/
- Phi-4 Model Card: https://huggingface.co/microsoft/Phi-4-multimodal-instruct
