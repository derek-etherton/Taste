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
src/app/            screens (Expo Router): (tabs)/index (Discover), (tabs)/shelf (Shelf Scan), (tabs)/profile,
                    item/[key] (a book's page, pushed under a native navigation bar)
src/api/            client.ts (typed fetch client), hooks.ts (TanStack Query), schema.d.ts (generated)
src/components/     kit (Screen, LargeTitle, Section, Button, SearchField, Icon, appearance toggle), item-row,
                    sheet, explanation-sheet, tag-filter, tag-charts, book-info, quality-slider, app-tabs
src/constants/      palette.ts (brand colours), theme.ts (colours, type, spacing), color.ts (contrast maths)
src/state/          settings.tsx (quality weight), appearance.ts (the light/dark choice, saved on the device)
```

## Look and feel

The UI follows Apple's Human Interface Guidelines, using platform components where they exist:

- **Tabs:** `NativeTabs` (the system tab bar on iOS and Android, Expo Router's floating bar on web).
- **Controls:** `@expo/ui`'s segmented control and slider (SwiftUI on iOS, Compose on Android, web fallbacks).
- **Icons:** SF Symbols via `expo-symbols` (Material Symbols on Android and web).
- **Layout and type:** inset-grouped lists, capsule buttons and Apple's text styles, from `kit.tsx` and `theme.ts`.

Colours are iOS system colours (grouped backgrounds, labels, separators, fills) plus a brand palette. **To change the palette**, paste the new colours into `src/constants/palette.ts` (any names; the "CSS HEX" export from coolors.co works) and point its three roles at them:

- `accent`: the tint for buttons, links and controls;
- `secondary`: the second chart hue;
- `surfaceTint`: placeholders.

`theme.ts` derives light and dark variants with enough contrast for each role. The sun/moon button at the top right switches light and dark, and is saved on the device (`localStorage` on web, AsyncStorage on phones); until it's used, the app follows the system.

Checks: `npm run typecheck` and `npx expo lint`.
