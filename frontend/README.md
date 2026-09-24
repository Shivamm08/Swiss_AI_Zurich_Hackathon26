# Frontend

React + TypeScript + Vite + Tailwind CSS v4, TanStack Query for data fetching,
React Router for pages. See the root README for how to run everything.

```
src/
  api/
    schema.d.ts   GENERATED from ../contracts/openapi.json. Never edit by hand (npm run gen:api)
    client.ts     typed fetch client (openapi-fetch)
    types.ts      friendly aliases for the generated types
    hooks.ts      one React Query hook per backend endpoint
  components/     Layout + small UI primitives
  pages/          one file per route
```

Rule of thumb: pages call hooks, hooks call `api`, and nothing else calls
`fetch` directly. If the backend changes an endpoint, `npm run gen:api` and
the TypeScript compiler shows every place that must change.
