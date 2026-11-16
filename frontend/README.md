# MediBot frontend

Next.js (App Router) + Tailwind chat UI for MediBot. See the [root README](../README.md) for full setup.

```bash
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                         # http://localhost:3000
```

- `app/login` — sign-in with one-click demo accounts
- `app/chat` — chat with role badge, accessible-collections sidebar, retrieval-type labels, citations, RBAC refusal cards
- `lib/api.ts` — typed API client (JWT stored in localStorage)
