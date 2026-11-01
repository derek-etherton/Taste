/** Building blocks shared by the screens, after iOS patterns: a grouped-background page with a
 * large title, inset-grouped sections and list rows, capsule buttons, a search field, icons. */
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import type { PropsWithChildren, ReactNode } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  TextInput,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Radius, Spacing, Type } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useTheme } from '@/hooks/use-theme';
import { setScheme } from '@/state/appearance';

/** A page: grouped background, safe-area aware, centred, at most MaxContentWidth wide. */
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
export const topInset = Platform.OS === 'web' ? 72 : 0;

export const listPadding: ViewStyle = {
  paddingHorizontal: Spacing.three,
  paddingTop: topInset,
  paddingBottom: BottomTabInset + Spacing.six,
};

/** The screen's title, in Apple's large-title style, with the appearance toggle at the top right
 * (and any other control beside it). */
export function LargeTitle({ title, trailing }: { title: string; trailing?: ReactNode }) {
  return (
    <View style={styles.largeTitle}>
      <ThemedText type="largeTitle" accessibilityRole="header" style={styles.flex}>
        {title}
      </ThemedText>
      {trailing}
      <AppearanceToggle />
    </View>
  );
}

/** Sun or moon: switches between light and dark, and remembers the choice on this device. */
export function AppearanceToggle() {
  const theme = useTheme();
  const dark = useColorScheme() === 'dark';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      hitSlop={10}
      onPress={() => setScheme(dark ? 'light' : 'dark')}
      style={({ pressed }) => [styles.toggle, pressed && { opacity: 0.5 }]}>
      <Icon name={dark ? { ios: 'sun.max', md: 'light_mode' } : { ios: 'moon', md: 'dark_mode' }} size={22} color={theme.accent} />
    </Pressable>
  );
}

/** An inset-grouped section: optional header, its rows on a rounded card, optional footer. */
export function Section({
  title,
  footer,
  children,
  plain,
}: PropsWithChildren<{ title?: string; footer?: ReactNode; plain?: boolean }>) {
  const theme = useTheme();
  return (
    <View style={styles.section}>
      {title && (
        <ThemedText type="title3" accessibilityRole="header" style={styles.sectionTitle}>
          {title}
        </ThemedText>
      )}
      {plain ? children : <View style={[styles.card, { backgroundColor: theme.card }]}>{children}</View>}
      {typeof footer === 'string' ? (
        <ThemedText type="footnote" themeColor="secondaryLabel" style={styles.sectionFooter}>
          {footer}
        </ThemedText>
      ) : (
        footer
      )}
    </View>
  );
}

/** Row `index` of `count` in a FlatList drawn as one inset-grouped card: the first and last
 * rows round the card's corners. */
export function groupedRow(index: number, count: number, card: string): StyleProp<ViewStyle> {
  return [
    { backgroundColor: card },
    index === 0 && { borderTopLeftRadius: Radius.card, borderTopRightRadius: Radius.card },
    index === count - 1 && { borderBottomLeftRadius: Radius.card, borderBottomRightRadius: Radius.card },
  ];
}

/** A hairline between rows, inset from the leading edge like iOS table separators. */
export function Separator({ inset = Spacing.three }: { inset?: number }) {
  const theme = useTheme();
  return <View style={[styles.separator, { marginLeft: inset, backgroundColor: theme.separator }]} />;
}

export type ButtonVariant = 'filled' | 'tinted' | 'gray' | 'plain';

/** A capsule button in one of Apple's styles: filled (the main action), tinted, gray or plain. */
export function Button({
  label,
  onPress,
  variant = 'gray',
  small,
  busy,
  disabled,
  icon,
}: {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  small?: boolean;
  busy?: boolean;
  disabled?: boolean;
  icon?: IconName;
}) {
  const theme = useTheme();
  const off = disabled || busy;
  const [background, color] = {
    filled: [theme.button, theme.onButton],
    tinted: [theme.accentFill, theme.accent],
    gray: [theme.fill, theme.accent],
    plain: ['transparent', theme.accent],
  }[variant];
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      accessibilityRole="button"
      accessibilityState={{ disabled: off, busy }}
      style={({ pressed }) => [
        styles.button,
        small ? styles.buttonSmall : styles.buttonRegular,
        variant === 'plain' && styles.buttonPlain,
        { backgroundColor: background, opacity: off ? 0.4 : pressed ? 0.7 : 1 },
      ]}>
      {busy ? (
        <ActivityIndicator size="small" color={color} />
      ) : icon ? (
        <Icon name={icon} size={small ? 15 : 17} color={color} />
      ) : null}
      <ThemedText type={small ? 'subheadline' : 'headline'} style={[small && styles.semibold, { color }]}>
        {label}
      </ThemedText>
    </Pressable>
  );
}

/** An iOS search field: magnifying glass, placeholder, and a clear button once there's text. */
export function SearchField({
  value,
  onChangeText,
  placeholder = 'Search',
  autoFocus,
}: {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const theme = useTheme();
  return (
    <View style={[styles.search, { backgroundColor: theme.fill }]}>
      <Icon name={{ ios: 'magnifyingglass', md: 'search' }} size={16} color={theme.secondaryLabel} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={theme.secondaryLabel}
        autoCorrect={false}
        autoFocus={autoFocus}
        returnKeyType="search"
        clearButtonMode="never"
        style={[Type.body, styles.searchInput, { color: theme.label }]}
      />
      {value.length > 0 && (
        <Pressable accessibilityRole="button" accessibilityLabel="Clear" hitSlop={8} onPress={() => onChangeText('')}>
          <Icon name={{ ios: 'xmark.circle.fill', md: 'cancel' }} size={16} color={theme.secondaryLabel} />
        </Pressable>
      )}
    </View>
  );
}

/** A short message in place of content: an empty list, or an error (in red). */
export function Note({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'error' }) {
  return typeof children === 'string' ? (
    <ThemedText
      type={tone === 'error' ? 'footnote' : 'subheadline'}
      themeColor={tone === 'error' ? 'destructive' : 'secondaryLabel'}
      style={styles.note}>
      {children}
    </ThemedText>
  ) : (
    <View style={styles.note}>{children}</View>
  );
}

export function Loading() {
  return <ActivityIndicator style={styles.loading} />;
}

/** An SF Symbol on iOS; the matching Material Symbol on Android and web. */
type Symbol = SymbolViewProps['name'];
export type IconName = { ios: Extract<Symbol, string>; md: NonNullable<Extract<Symbol, object>['android']> };

export function Icon({ name, size = 17, color }: { name: IconName; size?: number; color: string }) {
  return (
    <SymbolView
      name={{ ios: name.ios, android: name.md, web: name.md }}
      size={size}
      tintColor={color}
      style={{ width: size, height: size }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, flexDirection: 'row', justifyContent: 'center' },
  safe: { flex: 1, maxWidth: MaxContentWidth, width: '100%' },
  flex: { flex: 1 },
  largeTitle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    paddingTop: Spacing.two,
    paddingBottom: Spacing.two,
  },
  section: { gap: Spacing.two },
  sectionTitle: { paddingHorizontal: Spacing.one },
  sectionFooter: { paddingHorizontal: Spacing.three },
  card: { borderRadius: Radius.card, overflow: 'hidden' },
  separator: { height: StyleSheet.hairlineWidth },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
    borderRadius: Radius.capsule,
    alignSelf: 'flex-start',
  },
  buttonRegular: { minHeight: 50, paddingHorizontal: 20 },
  buttonSmall: { minHeight: 34, paddingHorizontal: 14 },
  buttonPlain: { paddingHorizontal: 0 },
  semibold: { fontWeight: '600' },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 36,
    paddingHorizontal: Spacing.two,
    borderRadius: Radius.field,
  },
  searchInput: { flex: 1, paddingVertical: 0, outlineWidth: 0 }, // no web focus ring: the field is the affordance
  note: { paddingVertical: Spacing.three, paddingHorizontal: Spacing.one },
  loading: { margin: Spacing.four },
  toggle: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
});
