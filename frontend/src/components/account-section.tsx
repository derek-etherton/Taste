/** Profile's Account section. A guest is told what's at stake and can sign in to keep their ratings;
 * a member sees who they're signed in as, and can sign out or delete the account (which removes
 * everything: ratings, shelf scan, sign-ins). */
import { useState } from 'react';
import { Alert, Platform, Pressable, StyleSheet, View } from 'react-native';

import { Note, Section, Separator } from '@/components/kit';
import { SignInButtons } from '@/components/sign-in-buttons';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSession } from '@/state/session';

function confirm(title: string, message: string, action: string): Promise<boolean> {
  if (Platform.OS === 'web') return Promise.resolve(window.confirm(`${title}\n\n${message}`));
  return new Promise((resolve) =>
    Alert.alert(title, message, [
      { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
      { text: action, style: 'destructive', onPress: () => resolve(true) },
    ]),
  );
}

function Row({ label, color, onPress }: { label: string; color: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && { backgroundColor: theme.fill }]}>
      <ThemedText type="body" style={{ color }}>
        {label}
      </ThemedText>
    </Pressable>
  );
}

export function AccountSection() {
  const theme = useTheme();
  const { user, signOut, deleteAccount } = useSession();
  const [error, setError] = useState<string | null>(null);
  if (!user) return null;

  if (user.kind === 'guest') {
    return (
      <Section
        title="Account"
        footer="Without an account your ratings live with this device's session: clearing this browser's data or losing your phone loses them.">
        <View style={styles.guest}>
          <ThemedText type="body">Sign in to keep your ratings.</ThemedText>
          <SignInButtons />
        </View>
      </Section>
    );
  }

  return (
    <Section title="Account" footer={error ?? undefined}>
      <View style={styles.row}>
        <ThemedText type="body">{user.name ?? 'Signed in'}</ThemedText>
        {user.email && (
          <ThemedText type="subheadline" themeColor="secondaryLabel">
            {user.email}
          </ThemedText>
        )}
      </View>
      <Separator />
      <Row label="Sign Out" color={theme.accent} onPress={() => signOut().catch((err: Error) => setError(err.message))} />
      <Separator />
      <Row
        label="Delete Account"
        color={theme.destructive}
        onPress={async () => {
          const ok = await confirm(
            'Delete your account?',
            'Your ratings, shelf scan and sign-ins are deleted for good. This can’t be undone.',
            'Delete',
          );
          if (ok) deleteAccount().catch((err: Error) => setError(err.message));
        }}
      />
      {error && <Note tone="error">{error}</Note>}
    </Section>
  );
}

const styles = StyleSheet.create({
  guest: { padding: Spacing.three, gap: Spacing.three },
  row: { minHeight: 44, justifyContent: 'center', paddingHorizontal: Spacing.three, paddingVertical: Spacing.two },
});
