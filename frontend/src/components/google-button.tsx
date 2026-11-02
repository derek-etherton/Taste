/** "Continue with Google" on iOS and Android, via the native Google Sign-In SDK. Needs a
 * development build (not Expo Go) and EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID (+ _IOS_CLIENT_ID on iOS);
 * hidden until they're set. The ID token's audience is the web client id, which the API checks. */
import { Platform } from 'react-native';

import { Button } from '@/components/kit';

const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
const IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID;
export const GOOGLE_READY = Boolean(WEB_CLIENT_ID && (Platform.OS !== 'ios' || IOS_CLIENT_ID));

export function GoogleButton({ onToken, onError }: { onToken: (idToken: string) => void; onError: (message: string) => void }) {
  if (!GOOGLE_READY) return null;
  async function signIn() {
    try {
      // Loaded on demand: the native module isn't in Expo Go, and importing it there would crash.
      const { GoogleSignin, isSuccessResponse } = await import('@react-native-google-signin/google-signin');
      GoogleSignin.configure({ webClientId: WEB_CLIENT_ID, iosClientId: IOS_CLIENT_ID });
      await GoogleSignin.hasPlayServices();
      const response = await GoogleSignin.signIn();
      if (!isSuccessResponse(response)) return; // cancelled
      if (!response.data.idToken) throw new Error('Google sent no ID token.');
      onToken(response.data.idToken);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  }
  return <Button variant="gray" icon={{ ios: 'g.circle', md: 'account_circle' }} label="Continue with Google" onPress={signIn} />;
}
