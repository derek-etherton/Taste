/** The first screen without a session: sign in with Apple or Google, or carry on without an
 * account (an anonymous profile on this device). */
import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import { Button, Note } from '@/components/kit';
import { SignInButtons } from '@/components/sign-in-buttons';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useSession } from '@/state/session';

export default function SignIn() {
  const { continueAsGuest } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <ThemedView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.page}>
        <View style={styles.head}>
          <ThemedText type="largeTitle">Taste</ThemedText>
          <ThemedText type="body" themeColor="secondaryLabel" style={styles.center}>
            Books picked for your taste. Rate a few you know, and see what to read next.
          </ThemedText>
        </View>
        <SignInButtons />
        <View style={styles.guest}>
          <Button
            variant="plain"
            label="Continue without an account"
            busy={busy}
            onPress={() => {
              setBusy(true);
              setError(null);
              continueAsGuest()
                .catch((err: Error) => setError(err.message))
                .finally(() => setBusy(false));
            }}
          />
          <ThemedText type="footnote" themeColor="secondaryLabel" style={styles.center}>
            Your ratings stay with this device. If you clear this browser&apos;s data or lose your phone, they&apos;re
            gone; sign in any time to keep them.
          </ThemedText>
          {error && <Note tone="error">{error}</Note>}
        </View>
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  page: {
    flexGrow: 1,
    justifyContent: 'center',
    width: '100%',
    maxWidth: 420,
    alignSelf: 'center',
    padding: Spacing.four,
    gap: Spacing.five,
  },
  head: { alignItems: 'center', gap: Spacing.two },
  center: { textAlign: 'center' },
  guest: { alignItems: 'center', gap: Spacing.two },
});
