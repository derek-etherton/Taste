/**
 * App config: app.json, plus what depends on your Apple and Google setup (README, Sign-in setup).
 *   TASTE_APP_ID                       the iOS bundle id / Android package, e.g. app.taste.books
 *   EXPO_PUBLIC_GOOGLE_IOS_URL_SCHEME  the iOS client's "reversed client id" from Google Cloud
 * Google's native plugin needs that scheme, so it's only added once it's set.
 */
import type { ConfigContext, ExpoConfig } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => {
  const id = process.env.TASTE_APP_ID ?? 'com.example.taste';
  const googleScheme = process.env.EXPO_PUBLIC_GOOGLE_IOS_URL_SCHEME;
  return {
    ...config,
    name: config.name ?? 'Taste',
    slug: config.slug ?? 'taste',
    ios: { ...config.ios, bundleIdentifier: id, usesAppleSignIn: true },
    android: { ...config.android, package: id },
    plugins: [
      ...(config.plugins ?? []),
      ...(googleScheme ? [['@react-native-google-signin/google-signin', { iosUrlScheme: googleScheme }] as [string, object]] : []),
    ],
  };
};
