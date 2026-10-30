# Taste: the app

One Expo (React Native) codebase for web, Android and iOS. It only talks to the backend API, so it deploys separately from it.

## Run

```bash
npm install
npm run web          # in a browser (expects the API at http://localhost:8000)
npx expo start       # then scan the QR code with Expo Go on a phone
```

Point the app at the API with `EXPO_PUBLIC_API_URL`. On a phone, use the PC's LAN address, since `localhost` is the phone itself:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.20:8000 npx expo start
```

## API types

`src/api/schema.d.ts` is generated from the backend's OpenAPI spec. After changing the API:

```bash
(cd ../backend && ../.venv/Scripts/python scripts/export_openapi.py)   # writes frontend/openapi.json
npm run api:types
```

## Deploy

- **Web:** `npm run export:web` builds a static site in `dist/`. Host it on S3 behind CloudFront, with every path falling back to `index.html` (it's a single-page app). Set `EXPO_PUBLIC_API_URL` when building.
- **Android / iOS:** EAS Build (`npx eas-cli@latest build`), for internal testing and the stores.

## Layout

```
src/app/            screens (Expo Router): index (Discover), shelf (Shelf scan), profile
src/api/            client.ts (typed fetch client), hooks.ts (TanStack Query), schema.d.ts (generated)
src/components/     item-row (card + rating buttons), explanation-sheet, settings-bar, kit (shared UI), tabs
src/state/          settings.tsx: current profile, domain, quality weight
```

Checks: `npm run typecheck` and `npx expo lint`.
