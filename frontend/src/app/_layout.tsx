import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { useState } from 'react';

import { AppearanceToggle } from '@/components/kit';
import { ThemedView } from '@/components/themed-view';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useTheme } from '@/hooks/use-theme';
import { SessionProvider, useSession } from '@/state/session';
import { SettingsProvider } from '@/state/settings';

/** The tabs and book pages need a session (a guest's or a member's); without one, only sign-in. */
function Screens() {
  const theme = useTheme();
  const { status } = useSession();
  if (status === 'loading') return <ThemedView style={{ flex: 1 }} />; // checking a saved session
  const signedIn = status === 'signedIn';
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={signedIn}>
        {/* The tabs, with book pages pushed on top of them under a native navigation bar. */}
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="item/[key]"
          options={{
            headerShown: true,
            title: '',
            headerBackTitle: 'Back',
            headerTintColor: theme.accent,
            headerShadowVisible: false,
            headerRight: () => <AppearanceToggle />,
          }}
        />
      </Stack.Protected>
      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="sign-in" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const scheme = useColorScheme();
  const theme = useTheme();
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } }));
  const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
  const navigation = {
    ...base,
    colors: {
      ...base.colors,
      primary: theme.accent,
      background: theme.groupedBackground,
      card: theme.groupedBackground,
      text: theme.label,
      border: theme.separator,
    },
  };
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <SettingsProvider>
          <ThemeProvider value={navigation}>
            <Screens />
          </ThemeProvider>
        </SettingsProvider>
      </SessionProvider>
    </QueryClientProvider>
  );
}
