# Bundlbite — System Architecture

## Overview

Bundlbite is a conversational group food ordering platform. The system takes natural language input from a group, resolves individual preferences into optimised restaurant baskets across multiple delivery providers, and places the consolidated order on behalf of the group.

---

## High-Level Architecture

```
┌─────────────────────────────────────────┐
│              Client (Browser)            │
│   Next.js 14 App Router + Streaming UI  │
└────────────────┬────────────────────────┘
                 │ HTTPS / WebSocket
┌────────────────▼────────────────────────┐
│           FastAPI Backend               │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  Chat API   │  │   Orders API     │  │
│  │ LangChain   │  │  Budget Engine   │  │
│  └──────┬──────┘  └────────┬─────────┘  │
│         │                  │            │
│  ┌──────▼──────────────────▼─────────┐  │
│  │       LangGraph Agent             │  │
│  │  Parse → Fetch → Rank → Confirm   │  │
│  └──────┬──────────────┬─────────────┘  │
└─────────┼──────────────┼────────────────┘
          │              │
  ┌───────▼──────┐ ┌─────▼────────┐
  │  Swiggy MCP  │ │  Zomato MCP  │
  │  Connector   │ │  Connector   │
  └──────────────┘ └──────────────┘
          │
  ┌───────▼──────────────────────────┐
  │   Supabase (pgvector)            │
  │   Past order embeddings (RAG)    │
  └──────────────────────────────────┘
```

---

## Component Breakdown

### 1. Frontend (Next.js 14)
- Streaming chat UI using `useChat` from Vercel AI SDK
- Group session management (group invite link)
- Per-member preference cards
- Basket comparison table (Swiggy vs Zomato)
- Checkout and payment split (UPI deep-link)

### 2. Backend (FastAPI)
- `/chat` — streaming LLM responses via LangChain
- `/orders/search` — queries both MCP connectors in parallel
- `/orders/optimise` — budget-fit basket generation
- `/orders/place` — forwards confirmed basket to provider
- `/track/{order_id}` — WebSocket status updates

### 3. LangGraph Agent
Multi-step agent pipeline:
1. **Parse** — extract members, cuisines, budget from natural language
2. **Fetch** — parallel tool calls to Swiggy MCP + Zomato MCP
3. **Rank** — score by rating, price, ETA, and RAG preference match
4. **Confirm** — present top 2 baskets and await group confirmation
5. **Place** — submit order, return tracking ID

### 4. MCP Connectors
- Swiggy MCP: restaurant search, menu fetch, cart creation, order placement
- Zomato MCP: same interface for consistent comparison

### 5. RAG Layer (v2)
- Store order history as embeddings in Supabase pgvector
- On each new order, retrieve top-k past orders by semantic similarity
- Bias ranking toward dishes with high user ratings in history

---

## Data Flow

1. User sends group order text to `/chat`
2. LangGraph agent parses members + preferences + budget
3. Agent calls Swiggy MCP and Zomato MCP in parallel
4. Budget engine filters and ranks restaurants by fit score
5. RAG engine adds personalisation signal (v2)
6. Top 2 baskets returned to UI
7. Group confirms basket → order placed via provider MCP
8. Tracking status streamed back via WebSocket

---

## Tech Decisions

| Decision | Rationale |
|---|---|
| FastAPI over Express | Async-first, Python ecosystem for AI/ML, Pydantic models |
| LangGraph over vanilla chains | Explicit state machine for multi-step order flow |
| Supabase over Firebase | pgvector support for RAG, SQL predictability |
| Vercel + Render | Zero-DevOps, auto-scaling, generous free tiers for MVP |
| MCP over REST scraping | Official provider protocol, future-proof |
