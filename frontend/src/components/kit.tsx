/** Small building blocks shared by the screens: page layout, chip selectors, buttons, notes. */
import type { PropsWithChildren, ReactNode } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, View, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export const ACCENT = '#3c87f7';

/** A page: safe-area aware, centred, at most MaxContentWidth wide. */
export function Screen({ children }: PropsWithChildren) {
  return (
    <ThemedView style={styles.screen}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        {children}
      </SafeAreaView>
    </ThemedView>
  );
}

// On web the tab bar floats over the top of the page; on phones it sits at the bottom.
export const topInset = Platform.OS === 'web' ? 80 : 0;

export const listPadding: ViewStyle = {
  paddingHorizontal: Spacing.three,
  paddingTop: topInset,
  paddingBottom: BottomTabInset + Spacing.six,
};

export type ChipOption<T> = { value: T; label: string };

/** A row of mutually exclusive choices. */
export function Chips<T extends string | number>({
  options,
  value,
  onChange,
}: {
  options: ChipOption<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  const theme = useTheme();
  return (
    <View style={styles.chips}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Pressable
            key={String(o.value)}
            onPress={() => onChange(o.value)}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
            style={({ pressed }) => [
              styles.chip,
              { backgroundColor: on ? theme.backgroundSelected : theme.backgroundElement },
              pressed && styles.pressed,
            ]}>
            <ThemedText type={on ? 'smallBold' : 'small'} themeColor={on ? 'text' : 'textSecondary'}>
              {o.label}
            </ThemedText>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Full-width tabs with an underline, for switching what the whole page below shows. */
export function TabStrip<T extends string>({
  options,
  value,
  onChange,
}: {
  options: ChipOption<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  const theme = useTheme();
  return (
    <View style={[styles.tabStrip, { borderBottomColor: theme.backgroundSelected }]} accessibilityRole="tablist">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Pressable
            key={o.value}
            onPress={() => onChange(o.value)}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            style={({ pressed }) => [styles.tab, on && { borderBottomColor: ACCENT }, pressed && styles.pressed]}>
            <ThemedText type={on ? 'smallBold' : 'small'} themeColor={on ? 'text' : 'textSecondary'} style={styles.tabLabel}>
              {o.label}
            </ThemedText>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Button({
  label,
  onPress,
  busy,
  disabled,
  primary,
}: {
  label: string;
  onPress: () => void;
  busy?: boolean;
  disabled?: boolean;
  primary?: boolean;
}) {
  const theme = useTheme();
  const off = disabled || busy;
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: primary ? ACCENT : theme.backgroundElement, opacity: off ? 0.5 : 1 },
        pressed && styles.pressed,
      ]}>
      {busy && <ActivityIndicator size="small" color={primary ? '#fff' : theme.text} />}
      <ThemedText type="smallBold" style={primary ? { color: '#fff' } : undefined}>
        {label}
      </ThemedText>
    </Pressable>
  );
}

/** A tinted box for info, warnings and errors. */
export function Note({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'error' }) {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.note,
        { backgroundColor: tone === 'error' ? 'rgba(220, 60, 60, 0.15)' : theme.backgroundElement },
      ]}>
      {typeof children === 'string' ? <ThemedText type="small">{children}</ThemedText> : children}
    </View>
  );
}

export function Loading() {
  const theme = useTheme();
  return <ActivityIndicator style={{ margin: Spacing.four }} color={theme.textSecondary} />;
}

const styles = StyleSheet.create({
  screen: { flex: 1, flexDirection: 'row', justifyContent: 'center' },
  safe: { flex: 1, maxWidth: MaxContentWidth, width: '100%' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  chip: { paddingVertical: Spacing.one + 2, paddingHorizontal: Spacing.three, borderRadius: Spacing.four },
  pressed: { opacity: 0.7 },
  tabStrip: { flexDirection: 'row', borderBottomWidth: 1 },
  tab: { flex: 1, alignItems: 'center', paddingVertical: Spacing.two + 2, borderBottomWidth: 2, borderBottomColor: 'transparent', marginBottom: -1 },
  tabLabel: { fontSize: 16 },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.two + 2,
    paddingHorizontal: Spacing.four,
    borderRadius: Spacing.three,
  },
  note: { padding: Spacing.three, borderRadius: Spacing.three },
});
