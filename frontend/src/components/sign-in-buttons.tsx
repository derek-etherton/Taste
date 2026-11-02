/** The ways to sign in: Apple (iOS), Google, and, in local development, any email. Used on the
 * sign-in screen and on Profile, where a guest signs in to keep their ratings. */
import * as AppleAuthentication from 'expo-apple-authentication';
import { useCallback, useEffect, useState } from 'react';
import { Platform, StyleSheet, TextInput, View } from 'react-native';

import { GoogleButton } from '@/components/google-button';
import { Button, Note } from '@/components/kit';
import { Radius, Spacing, Type } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useTheme } from '@/hooks/use-theme';
import { useSession } from '@/state/session';

const DEV_LOGIN = process.env.EXPO_PUBLIC_DEV_LOGIN === 'true';

function AppleButton({ onError }: { onError: (message: string) => void }) {
  const { signInWithApple } = useSession();
  const dark = useColorScheme() === 'dark';
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    if (Platform.OS === 'ios') AppleAuthentication.isAvailableAsync().then(setAvailable, () => setAvailable(false));
  }, []);
  if (!available) return null;
  return (
    <AppleAuthentication.AppleAuthenticationButton
      buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
      buttonStyle={dark ? AppleAuthentication.AppleAuthenticationButtonStyle.WHITE : AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
      cornerRadius={25}
      style={styles.apple}
      onPress={async () => {
        try {
          const c = await AppleAuthentication.signInAsync({
            requestedScopes: [AppleAuthentication.AppleAuthenticationScope.FULL_NAME, AppleAuthentication.AppleAuthenticationScope.EMAIL],
          });
          if (!c.identityToken) throw new Error('Apple sent no identity token.');
          // Apple only shares the name on the first sign-in, so pass it along now.
          const name = [c.fullName?.givenName, c.fullName?.familyName].filter(Boolean).join(' ') || null;
          await signInWithApple(c.identityToken, name);
        } catch (err) {
          if ((err as { code?: string }).code === 'ERR_REQUEST_CANCELED') return;
          onError(err instanceof Error ? err.message : String(err));
        }
      }}
    />
  );
}

function DevLogin({ onError }: { onError: (message: string) => void }) {
  const { signInDev } = useSession();
  const theme = useTheme();
  const [email, setEmail] = useState('');
  return (
    <View style={styles.dev}>
      <TextInput
        value={email}
        onChangeText={setEmail}
        placeholder="Email (development sign-in)"
        placeholderTextColor={theme.secondaryLabel}
        autoCapitalize="none"
        keyboardType="email-address"
        style={[Type.body, styles.field, { backgroundColor: theme.fill, color: theme.label }]}
      />
      <Button
        small
        variant="gray"
        label="Sign In"
        disabled={!email.includes('@')}
        onPress={() => signInDev(email).catch((err: Error) => onError(err.message))}
      />
    </View>
  );
}

export function SignInButtons() {
  const { signInWithGoogle } = useSession();
  const [error, setError] = useState<string | null>(null);
  const google = useCallback(
    (idToken: string) => signInWithGoogle(idToken).catch((err: Error) => setError(err.message)),
    [signInWithGoogle],
  );
  return (
    <View style={styles.buttons}>
      <AppleButton onError={setError} />
      <GoogleButton onToken={google} onError={setError} />
      {DEV_LOGIN && <DevLogin onError={setError} />}
      {error && <Note tone="error">{error}</Note>}
    </View>
  );
}

const styles = StyleSheet.create({
  buttons: { gap: Spacing.two, alignItems: 'stretch' },
  apple: { height: 50, width: '100%' },
  dev: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two },
  field: { flex: 1, height: 36, paddingHorizontal: Spacing.three, borderRadius: Radius.field },
});
