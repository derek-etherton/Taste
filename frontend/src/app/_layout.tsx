import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { useState } from 'react';

import { AppearanceToggle } from '@/components/kit';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useTheme } from '@/hooks/use-theme';
import { SettingsProvider } from '@/state/settings';

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
      <SettingsProvider>
        <ThemeProvider value={navigation}>
          {/* The tabs, with book pages pushed on top of them under a native navigation bar. */}
          <Stack screenOptions={{ headerShown: false }}>
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
          </Stack>
        </ThemeProvider>
      </SettingsProvider>
    </QueryClientProvider>
  );
}
