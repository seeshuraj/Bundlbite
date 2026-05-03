# 🍱 Bundlbite

> **AI-powered group food ordering copilot** — one chat, five preferences, one budget-safe checkout across Swiggy & Zomato.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MVP Status](https://img.shields.io/badge/status-MVP-orange)](#)
[![Built with](https://img.shields.io/badge/built%20with-FastAPI%20%7C%20Next.js%20%7C%20LangChain-blue)](#tech-stack)

---

## 🧠 What is Bundlbite?

Ordering food for a group is chaos. Everyone has different cravings, someone is on a budget, and no one wants to switch between five apps.

**Bundlbite** solves this with a single conversational interface:

1. Members describe what they want in plain text (e.g. *"Rahul wants biryani, Sneha wants dosa, keep it under ₹1200"*)
2. The AI parses preferences, calls Swiggy + Zomato APIs via MCP connectors
3. It generates budget-optimised baskets, ranked by rating and most-ordered dishes
4. The group confirms, pays, and tracks — all in one place

---

## ✨ MVP Features

- 💬 **Natural language group intake** — type preferences in plain English
- 🔄 **Dual-provider comparison** — Swiggy vs Zomato real-time price & ETA
- 💰 **Budget optimisation engine** — fits all preferences within a group cap
- ⭐ **Rating-weighted ranking** — best dishes surfaced from most-ordered data
- 🧾 **Split summary** — per-person cost breakdown before checkout
- 🚚 **Order tracking** — live status updates piped back into the chat
- 🧠 **RAG personalisation layer** *(v2)* — learns from past group orders

---

## 🗂️ Project Structure

```
bundlbite/
├── mvp/                        # Static MVP prototype (HTML/CSS/JS)
│   ├── index.html              # Main chatbot UI
│   ├── style.css               # Design system (Nexus tokens)
│   └── app.js                  # Mock interaction logic
│
├── backend/                    # FastAPI backend (Phase 2)
│   ├── main.py
│   ├── routers/
│   │   ├── chat.py             # LangChain conversation handler
│   │   ├── orders.py           # Provider MCP connector calls
│   │   └── budget.py           # Basket optimisation logic
│   ├── services/
│   │   ├── swiggy_mcp.py       # Swiggy MCP client
│   │   ├── zomato_mcp.py       # Zomato MCP client
│   │   └── rag_engine.py       # RAG retrieval (order history)
│   └── models/
│       ├── group_order.py
│       └── basket.py
│
├── frontend/                   # Next.js app (Phase 2)
│   ├── app/
│   ├── components/
│   └── lib/
│
├── docs/
│   ├── ARCHITECTURE.md         # System design deep-dive
│   └── ROADMAP.md              # Phase-by-phase build plan
│
├── .env.example                # Required environment variables
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start (MVP)

No backend needed. Run the static MVP locally:

```bash
git clone https://github.com/seeshuraj/Bundlbite.git
cd Bundlbite/mvp
open index.html   # or use Live Server in VS Code
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend MVP** | HTML / CSS / Vanilla JS | Zero-dependency chatbot UI prototype |
| **Frontend v2** | Next.js 14 (App Router) | Production SPA with streaming chat |
| **Backend** | FastAPI (Python) | REST + WebSocket API server |
| **AI Orchestration** | LangChain + LangGraph | Multi-step group order agent |
| **LLM** | Claude 3.5 Sonnet / GPT-4o | Natural language understanding |
| **Provider Connectors** | Swiggy MCP + Zomato MCP | Real-time menu, pricing, order placement |
| **RAG Store** | Supabase (pgvector) | Past order embeddings for personalisation |
| **Auth** | Clerk / Supabase Auth | Group session management |
| **Deployment** | Vercel (frontend) + Render (backend) | Zero-DevOps cloud deploy |

---

## 🗺️ Roadmap

### Phase 1 — MVP (Now)
- [x] Repo scaffold and project structure
- [x] Static chatbot UI with mock data
- [ ] Natural language parser (LangChain)
- [ ] Swiggy MCP connector (menu + pricing)
- [ ] Zomato MCP connector (menu + pricing)
- [ ] Budget optimisation algorithm
- [ ] Basic frontend (Next.js)

### Phase 2 — Beta
- [ ] User accounts and saved groups
- [ ] Live order placement via MCP
- [ ] Real-time delivery tracking in chat
- [ ] Per-person UPI payment split

### Phase 3 — Growth
- [ ] RAG personalisation from order history
- [ ] Fine-tuned model on Indian cuisine data
- [ ] Multi-city restaurant coverage
- [ ] Referral and group savings features

### Phase 4 — Revenue
- [ ] Commission model on placed orders
- [ ] B2B plan for offices and hostels
- [ ] White-label API for corporate canteens
- [ ] Partner dashboard for restaurants

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for detailed milestones.

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# LLM
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Provider MCP Servers
SWIGGY_MCP_ENDPOINT=
SWIGGY_API_KEY=
ZOMATO_MCP_ENDPOINT=
ZOMATO_API_KEY=

# Database
SUPABASE_URL=
SUPABASE_ANON_KEY=

# Auth
CLERK_SECRET_KEY=
```

---

## 🤝 Contributing

This project is in active MVP development. Contributions, feedback, and issue reports are welcome.

1. Fork the repo
2. Create your feature branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m 'feat: add your feature'`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ to solve the most underrated engineering problem — group hunger.
</p>
