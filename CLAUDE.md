# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack monolithic web application for a "Turtle Soup" (海龟汤) situation puzzle game with real-time chat. Backend is Python/FastAPI, frontend is Vue 3 SPA.

## Commands

**Backend:**
```bash
python main.py                                    # start server (port 8000)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload  # with hot reload
```

**Frontend:**
```bash
cd frontend
npm install          # first time only
npm run dev          # Vite dev server (port 3000), proxies /api and /ws to backend
npm run build        # production build
```

**One-click start (both services):**
```bash
scripts/start_all.bat    # Windows
bash scripts/start_all.sh  # Linux/macOS
```

## Architecture

```
Browser (port 3000)  -->  Vite dev server proxies /api and /ws to backend
                              |
FastAPI Backend (port 8000)
  ├── api/auth.py          /register, /login, /forgot-password
  ├── api/user.py          /profile, /user/nickname, /user/avatar
  ├── api/chat.py          /ws/chat/{token} (WebSocket), /chat/online-users
  ├── api/turtle_soup.py   /turtle-soup/* (game CRUD, questions, answers)
  ├── core/config.py       DB engine (PostgreSQL via SQLAlchemy), JWT config, file paths
  ├── core/security.py     bcrypt password hashing, JWT encode/decode
  ├── core/llm_service.py  LLM service: dual-mode (local Ollama / external OpenAI-compatible API)
  ├── models/db_models.py  User, PublicChatMessage, PrivateChatSession, PrivateChatMessage
                              |
PostgreSQL (fastapi_chat, localhost:5432)    Ollama (port 11434, optional)
```

**Frontend structure:** Vue 3 + Pinia + Vue Router + Vite. Dark minimalist theme (Linear/Vercel style).
- `frontend/src/views/LoginView.vue` — `/` Auth forms (login/register/forgot)
- `frontend/src/views/LobbyView.vue` — `/lobby` Create/join room, room list
- `frontend/src/views/RoomView.vue` — `/room/:id` Game room (delegates to SoupGame or UndercoverGame)
- `frontend/src/stores/auth.js` — Pinia store for JWT token + user profile
- `frontend/src/utils/api.js` — fetch wrapper with Bearer token auth
- `frontend/src/components/common/` — Button, Input, Card, Modal, Avatar
- `frontend/src/components/auth/` — LoginForm, RegisterForm, ForgotPasswordForm
- `frontend/src/components/lobby/` — CreateRoomPanel, JoinRoomPanel, RoomList
- `frontend/src/components/room/` — RoomSidebar, ChatPanel, SoupGame, UndercoverGame

**Game state:** Active games are stored in an in-memory dict (`games_db`) in `api/turtle_soup.py` — lost on restart. Chat messages persist to PostgreSQL.

**LLM integration (`core/llm_service.py`):** Supports two switchable modes via `LLM_MODE` env var:
- `"local"` (default): Ollama with Qwen 3.5:4b, connects to `OLLAMA_HOST` (default `http://localhost:11434`)
- `"external"`: OpenAI-compatible API, requires `LLM_API_KEY` + `LLM_API_URL`

Game logic in `api/turtle_soup.py` only defines prompts and rules. All LLM calls go through `llm_service.chat()`. The system gracefully degrades — if LLM is unavailable, it falls back to preset puzzles and keyword-based judgment.
