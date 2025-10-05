# User Query Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Vanilla JS)                          │
└─────────────────────────────────────────────────────────────────────────────┘

    User types question
           │
           ▼
    ┌──────────────────┐
    │  sendMessage()   │ ← script.js:45
    │  (script.js)     │
    └──────────────────┘
           │
           ├─► Display user message
           ├─► Show loading animation
           │
           ▼
    POST /api/query
    {
      query: "user question",
      session_id: "abc123"
    }
           │
           │
           ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND API (FastAPI)                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────┐
    │  /api/query endpoint │ ← app.py:56
    │  (app.py)            │
    └──────────────────────┘
           │
           ├─► Get/Create session_id
           │
           ▼
    ┌────────────────────────┐
    │  rag_system.query()    │ ← rag_system.py:102
    │  (rag_system.py)       │
    └────────────────────────┘
           │
           ├─► Get conversation history (if session exists)
           │   └─► session_manager.get_conversation_history()
           │
           ▼
    ┌─────────────────────────────────────┐
    │  ai_generator.generate_response()   │ ← ai_generator.py:46
    │  (ai_generator.py)                  │
    └─────────────────────────────────────┘
           │
           ├─► Build messages array:
           │   • System prompt + conversation history
           │   • User query
           │
           ├─► Add tool definitions:
           │   • search_course_content tool
           │
           ▼
    ┌──────────────────────────────┐
    │  OpenAI API Call to SGLang   │ ← Port 7501 (Local Phi-4)
    │  (temperature=0)             │
    └──────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │              AI DECIDES: Use Tool or Direct Answer      │
    └─────────────────────────────────────────────────────────┘
           │
           ├──────────────────┬────────────────────────┐
           │                  │                        │
           ▼                  ▼                        ▼
    Direct Answer      Tool Call Required      No Tool Needed
                             │
                             ▼
                    ┌─────────────────────────────┐
                    │  tool_manager.execute_tool  │ ← search_tools.py:139
                    │  "search_course_content"    │
                    └─────────────────────────────┘
                             │
                             ├─► Parse tool arguments:
                             │   • query
                             │   • course_name (optional)
                             │   • lesson_number (optional)
                             │
                             ▼
                    ┌─────────────────────────────┐
                    │  CourseSearchTool.execute() │ ← search_tools.py:55
                    └─────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────────────────┐
                    │  vector_store.search()      │ ← vector_store.py
                    │  (ChromaDB)                 │
                    └─────────────────────────────┘
                             │
                             ├─► Semantic search with filters
                             ├─► Get top N results
                             │
                             ▼
                    ┌─────────────────────────────┐
                    │  Format Results             │
                    │  [Course - Lesson X]        │
                    │  content...                 │
                    └─────────────────────────────┘
                             │
                             ├─► Track sources
                             │
                             ▼
                    ┌─────────────────────────────┐
                    │  Return tool results to AI  │
                    └─────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────────────────┐
                    │  AI Synthesizes Answer      │ ← ai_generator.py:158
                    │  from search results        │
                    └─────────────────────────────┘
                             │
                             │
           ┌─────────────────┴─────────────────────┐
           │                                       │
           ▼                                       ▼
    ┌──────────────────┐              ┌──────────────────────┐
    │  Final Response  │              │  Get Sources         │
    └──────────────────┘              │  from tool_manager   │
           │                          └──────────────────────┘
           │                                       │
           ▼                                       ▼
    ┌────────────────────────────────────────────────────┐
    │  Update Conversation History                       │ ← session_manager.add_exchange()
    │  (query + response stored in session)              │
    └────────────────────────────────────────────────────┘
           │
           ▼
    ┌────────────────────────────────────────────────────┐
    │  Return Response                                   │
    │  {                                                 │
    │    answer: "...",                                  │
    │    sources: ["Course - Lesson 1", ...],            │
    │    session_id: "abc123"                            │
    │  }                                                 │
    └────────────────────────────────────────────────────┘
           │
           │
           ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Vanilla JS)                           │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────┐
    │  Receive Response    │
    └──────────────────────┘
           │
           ├─► Remove loading animation
           ├─► Render answer (markdown → HTML via marked.js)
           ├─► Display sources (collapsible section)
           ├─► Update session_id if new
           │
           ▼
    ┌──────────────────────┐
    │  Display to User     │
    └──────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

KEY COMPONENTS:

📱 Frontend (script.js)
   - Captures user input
   - Manages UI states (loading, messages)
   - Renders markdown responses

🔌 API Layer (app.py)
   - FastAPI endpoint /api/query
   - Session management
   - Request/response handling

🧠 RAG System (rag_system.py)
   - Orchestrates the query flow
   - Manages conversation context
   - Coordinates AI and tools

🤖 AI Generator (ai_generator.py)
   - Calls local Phi-4 LLM (port 7501)
   - Handles tool calling logic
   - Manages multi-turn conversations

🔍 Search Tools (search_tools.py)
   - CourseSearchTool: semantic search
   - ToolManager: tool execution
   - Source tracking

💾 Vector Store (vector_store.py)
   - ChromaDB for embeddings
   - Semantic search with filters
   - Course/lesson metadata

📝 Session Manager
   - Tracks conversation history
   - Per-session context maintenance

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE FLOW:

User asks: "What is covered in lesson 5 of the MCP course?"

1. Frontend sends POST to /api/query
2. RAG system retrieves conversation history
3. AI Generator calls Phi-4 with tool definitions
4. Phi-4 decides to use search_course_content tool with:
   - query: "lesson 5 content"
   - course_name: "MCP"
   - lesson_number: 5
5. CourseSearchTool searches ChromaDB with filters
6. Results formatted: "[MCP: Build Rich-Context AI Apps - Lesson 5]\n content..."
7. Results sent back to Phi-4
8. Phi-4 synthesizes answer from search results
9. Answer + sources returned to frontend
10. Frontend renders markdown answer with collapsible sources
