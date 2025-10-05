# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a RAG (Retrieval-Augmented Generation) chatbot system that answers questions about course materials. It uses a local Phi-4 LLM via SGLang, ChromaDB for vector storage, and a vanilla JavaScript frontend.

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Configure environment (copy .env.example to .env)
cp .env.example .env
```

### Running the Application

**Important**: This system requires TWO servers running simultaneously:

1. **SGLang LLM Server** (port 7501) - Must be started FIRST:
   ```bash
   ./launch_phi-4_server.sh
   # Or manually:
   ~/.venvs/sgl/bin/python -m sglang.launch_server --port 7501 \
     --model-path microsoft/Phi-4-multimodal-instruct --tp 2 \
     --dtype bfloat16 --trust-remote-code 

2. **FastAPI Application Server** (port 8000):
   ```bash
   ./run.sh
   # Or manually:
   cd backend && uv run uvicorn app:app --reload --port 8000
   ```

**Access Points**:
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Port Management

If you get "Address already in use" errors:
- Port 7501 (SGLang): DO NOT KILL - this is the LLM server
- Port 8000 (FastAPI): Kill with `lsof -ti:8000 | xargs kill -9`

## Architecture

### Query Processing Flow

1. **Frontend** (`frontend/script.js`) → User input captured
2. **API Endpoint** (`backend/app.py:56`) → POST `/api/query`
3. **RAG System** (`backend/rag_system.py:102`) → Orchestrates flow
4. **AI Generator** (`backend/ai_generator.py:46`) → Calls Phi-4 with tool definitions
5. **Tool Decision** → AI decides to use `search_course_content` or answer directly
6. **Search Tool** (`backend/search_tools.py:55`) → Executes semantic search on ChromaDB
7. **Vector Store** (`backend/vector_store.py`) → Returns filtered results
8. **AI Synthesis** → Phi-4 generates answer from search results
9. **Response** → Answer + sources returned to frontend

See `query-flow-diagram.md` for detailed visualization.

### Core Components

**Backend Architecture**:
- `rag_system.py`: Main orchestrator - coordinates all components
- `ai_generator.py`: OpenAI-compatible client to SGLang server (Phi-4)
- `search_tools.py`: Tool-calling system with `CourseSearchTool` for semantic search
- `vector_store.py`: ChromaDB wrapper with course/lesson filtering
- `document_processor.py`: Chunks documents (800 chars, 100 overlap)
- `session_manager.py`: Conversation history (max 2 exchanges)
- `app.py`: FastAPI endpoints (`/api/query`, `/api/courses`)

**Frontend Architecture**:
- Vanilla JS (no framework)
- `script.js`: API calls, session management, markdown rendering (marked.js)
- `index.html`: Chat UI with left sidebar (stats + suggested questions)
- `style.css`: Dark theme with CSS variables

### Tool Calling System

The AI uses OpenAI-compatible tool calling:
- Tool: `search_course_content(query, course_name?, lesson_number?)`
- AI decides when to search vs answer from knowledge
- One search per query maximum (enforced in system prompt)
- Sources tracked in `CourseSearchTool.last_sources`

### Configuration (`backend/config.py`)

Key settings:
- `CHUNK_SIZE`: 800 (text chunk size for embeddings)
- `CHUNK_OVERLAP`: 100 (overlap between chunks)
- `MAX_RESULTS`: 5 (top-k search results)
- `MAX_HISTORY`: 2 (conversation exchanges to remember)
- `EMBEDDING_MODEL`: "all-MiniLM-L6-v2"

### Data Storage

- Course documents in `./docs/` (PDF, DOCX, TXT)
- ChromaDB persisted in `./backend/chroma_db/`
- On startup: `app.py:88` loads documents from `../docs`
- Duplicate detection by course title

## Important Patterns

### Adding Course Documents

Documents are auto-loaded on startup from `docs/` folder. The system:
- Extracts course metadata (title, instructor, lessons)
- Chunks content with overlap
- Stores in two ChromaDB collections:
  - `course_metadata`: For semantic course name matching
  - `course_content`: For actual content search

### Session Management

- Sessions created per conversation (`session_id` in requests)
- History format: "User: {query}\nAssistant: {response}\n"
- Limited to `MAX_HISTORY` exchanges to control context size

### Markdown Rendering

Frontend uses `marked.js` to render AI responses. Assistant messages support:
- Headings, lists, code blocks
- Inline code with syntax highlighting
- Blockquotes

### Error Handling

- Frontend shows loading animation during API calls
- Tool errors returned as formatted strings to AI
- Empty search results trigger "No content found" message
- API errors display in chat as error messages

## Key Files Reference

Critical files to understand the system:

- `backend/ai_generator.py:8-30` - System prompt defining AI behavior
- `backend/search_tools.py:27-53` - Tool definition for course search
- `backend/rag_system.py:102-140` - Main query processing logic
- `frontend/script.js:45-96` - User query submission flow
- Always use `uv` not `pip` directly
