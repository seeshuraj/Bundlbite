# Bundlbite — Product Roadmap

## Vision

Become the default group ordering layer on top of all food delivery platforms in India — starting with AI-assisted basket building and growing into a social, budget-aware ordering network.

---

## Phase 1 — MVP (Weeks 1–6)

**Goal:** Prove the core UX works end-to-end with mock data.

- [x] Repo scaffold + project structure
- [x] Static chatbot UI (HTML/CSS/JS)
- [x] Design system (Nexus tokens)
- [ ] LangChain natural language parser
- [ ] Swiggy MCP connector (menu fetch)
- [ ] Zomato MCP connector (menu fetch)
- [ ] Budget optimisation algorithm (v1 — greedy)
- [ ] Basic Next.js frontend
- [ ] FastAPI backend with `/chat` and `/orders/search`

**Success metric:** 5 internal test orders placed end-to-end.

---

## Phase 2 — Beta (Weeks 7–14)

**Goal:** Real orders placed for small groups.

- [ ] Swiggy MCP order placement
- [ ] Zomato MCP order placement
- [ ] Real-time delivery tracking (WebSocket)
- [ ] Group session sharing (invite link)
- [ ] Per-person UPI payment split
- [ ] User accounts (Clerk auth)
- [ ] Mobile-responsive Next.js UI

**Success metric:** 50 real orders, NPS > 7.

---

## Phase 3 — Growth (Months 4–9)

**Goal:** Personalisation and retention.

- [ ] RAG personalisation from order history
- [ ] Fine-tuned model on Indian cuisine preferences
- [ ] Multi-city restaurant coverage
- [ ] Saved groups (office, friends, family)
- [ ] Push notifications for group order status
- [ ] Referral programme

**Success metric:** 30% repeat orders within 30 days.

---

## Phase 4 — Revenue (Month 10+)

**Goal:** Sustainable business model.

- [ ] Commission model on placed orders (0.5–1.5%)
- [ ] B2B plan for offices and hostels (monthly subscription)
- [ ] White-label API for corporate canteens
- [ ] Restaurant partner dashboard (promoted listings)
- [ ] Bundlbite Pro (premium groups: dietary tracking, split analytics)

**Revenue targets:**
- Month 12: ₹5L GMV/month
- Month 18: ₹50L GMV/month
- Month 24: Series A readiness (₹5Cr+ ARR)

---

## Competitive Moat

| Advantage | Description |
|---|---|
| Group-first UX | No competitor builds for groups natively |
| Multi-provider comparison | Price + ETA arbitrage between Swiggy and Zomato |
| RAG personalisation | Gets smarter with every group order |
| MCP-native | Built on official AI protocols, not brittle scraping |
| Budget optimisation | Unique feature — no equivalent in market |
