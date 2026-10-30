/** One film or book: title, details and reasons, its percentile (tap for why), and 👍 😐 👎. */
import { Pressable, StyleSheet, View } from 'react-native';

import type { ItemCard, Rating } from '@/api/client';
import { useRate } from '@/api/hooks';
import { ThemedText } from '@/components/themed-text';
import { ACCENT } from '@/components/kit';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const BUTTONS: { value: Rating; icon: string; label: string }[] = [
  { value: 1, icon: '👍', label: 'Like' },
  { value: 0, icon: '😐', label: 'Meh: tried it, neither loved nor hated it' },
  { value: -1, icon: '👎', label: 'Dislike' },
];

function ordinal(n: number): string {
  const suffix = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th';
  return `${n}${suffix}`;
}

export function RatingButtons({ item }: { item: ItemCard }) {
  const { user } = useSettings();
  const rate = useRate(user);
  const theme = useTheme();
  return (
    <View style={styles.buttons}>
      {BUTTONS.map((b) => {
        const on = item.rated === b.value;
        return (
          <Pressable
            key={b.value}
            accessibilityRole="button"
            accessibilityLabel={b.label}
            accessibilityState={{ selected: on }}
            onPress={() => rate.mutate({ key: item.key, value: b.value, current: item.rated })}
            style={({ pressed }) => [
              styles.rateButton,
              { backgroundColor: on ? ACCENT : theme.backgroundElement },
              pressed && { opacity: 0.6 },
            ]}>
            <ThemedText style={styles.icon}>{b.icon}</ThemedText>
          </Pressable>
        );
      })}
    </View>
  );
}

export function ItemRow({
  item,
  rank,
  source,
  onExplain,
}: {
  item: ItemCard;
  rank?: number;
  source?: string;
  onExplain?: (item: ItemCard) => void;
}) {
  const theme = useTheme();
  const details = [
    item.location ? `📍 ${item.location}` : '',
    item.creator,
    item.genres.join(' · '),
    item.more_in_series ? `+${item.more_in_series} more in ${item.series}` : '',
  ].filter(Boolean);
  const because = item.because
    .map((b) => (b.from_other_domain && source ? `${b.tag} (from ${source})` : b.tag))
    .join(', ');
  return (
    <View style={[styles.row, { borderBottomColor: theme.backgroundElement }]}>
      <View style={styles.text}>
        <ThemedText type="smallBold">
          {rank !== undefined ? `${rank}. ` : ''}
          {item.label}
        </ThemedText>
        {details.length > 0 && (
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>
            {details.join(' · ')}
          </ThemedText>
        )}
        {because ? (
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={2} style={styles.because}>
            because: {because}
          </ThemedText>
        ) : null}
      </View>
      <View style={styles.side}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Why this is recommended"
          onPress={() => onExplain?.(item)}
          style={({ pressed }) => [styles.pct, { backgroundColor: theme.backgroundElement }, pressed && { opacity: 0.6 }]}>
          <ThemedText type="small">{ordinal(Math.round(item.percentile))} pct</ThemedText>
        </Pressable>
        <RatingButtons item={item} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: Spacing.three,
    paddingVertical: Spacing.three,
    borderBottomWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
  },
  text: { flex: 1, gap: 2 },
  because: { fontStyle: 'italic' },
  side: { alignItems: 'flex-end', gap: Spacing.two },
  pct: { paddingHorizontal: Spacing.two + 2, paddingVertical: Spacing.one, borderRadius: Spacing.two },
  buttons: { flexDirection: 'row', gap: Spacing.one },
  rateButton: { width: 36, height: 32, borderRadius: Spacing.two, alignItems: 'center', justifyContent: 'center' },
  icon: { fontSize: 16, lineHeight: 20 },
});
