import { NativeTabs } from 'expo-router/native-tabs';
import { Platform } from 'react-native';

import { useTheme } from '@/hooks/use-theme';

/** The tab bar: native on iOS and Android, Expo Router's floating bar on web. Tinted with the
 * accent; iOS and Android keep their own bar material. */
export default function AppTabs() {
  const theme = useTheme();
  const web =
    Platform.OS === 'web'
      ? {
          backgroundColor: theme.card,
          indicatorColor: theme.fill,
          labelStyle: { color: theme.secondaryLabel, fontSize: 15, fontWeight: '600' as const },
        }
      : {};

  return (
    <NativeTabs tintColor={theme.accent} {...web}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Discover</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="sparkles" md="explore" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="shelf">
        <NativeTabs.Trigger.Label>Shelf Scan</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="books.vertical" md="photo_camera" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="profile">
        <NativeTabs.Trigger.Label>Profile</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="person.crop.circle" md="person" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
