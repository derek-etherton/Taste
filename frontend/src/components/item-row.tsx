/** One film or book: cover (books), title, details and reasons (tap for its page), its score (tap for why),
 * and 👍 😐 👎. */
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import type { ItemCard, Rating } from '@/api/client';
import { useRate } from '@/api/hooks';
import { ThemedText } from '@/components/themed-text';
import { ACCENT } from '@/components/kit';
import { signed } from '@/components/tag-charts';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const BUTTONS: { value: Rating; icon: string; label: string }[] = [
  { value: 1, icon: '👍', label: 'Like' },
  { value: 0, icon: '😐', label: 'Meh: tried it, neither loved nor hated it' },
  { value: -1, icon: '👎', label: 'Dislike' },
];

export function openItem(key: string) {
  router.push({ pathname: '/item/[key]', params: { key } });
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
    item.similarity != null ? `similarity ${item.similarity.toFixed(2)}` : '',
    item.tag_match != null ? `tag match ${item.tag_match.toFixed(2)}` : '',
    item.creator,
    item.genres.join(' · '),
  ].filter(Boolean);
  const because = item.because
    .map((b) => (b.from_other_domain && source ? `${b.tag} (from ${source})` : b.tag))
    .join(', ');
  const book = item.key.startsWith('book:');
  return (
    <View style={[styles.row, { borderBottomColor: theme.backgroundElement }]}>
      {book && (
        <Pressable onPress={() => openItem(item.key)} accessibilityElementsHidden importantForAccessibility="no">
          <View style={[styles.cover, { backgroundColor: theme.backgroundElement }]}>
            {item.cover_url && <Image source={{ uri: item.cover_url }} style={styles.cover} contentFit="cover" transition={150} />}
          </View>
        </Pressable>
      )}
      <Pressable
        accessibilityRole="link"
        onPress={() => openItem(item.key)}
        style={({ pressed }) => [styles.text, pressed && { opacity: 0.6 }]}>
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
      </Pressable>
      <View style={styles.side}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Why this is recommended"
          onPress={() => (onExplain ? onExplain(item) : openItem(item.key))}
          style={({ pressed }) => [styles.pct, { backgroundColor: theme.backgroundElement }, pressed && { opacity: 0.6 }]}>
          <ThemedText type="small">{signed(item.score)}</ThemedText>
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
  cover: { width: 44, height: 66, borderRadius: 3, overflow: 'hidden' }, // a placeholder when there's none, so titles line up
  text: { flex: 1, gap: 2 },
  because: { fontStyle: 'italic' },
  side: { alignItems: 'flex-end', gap: Spacing.two },
  pct: { paddingHorizontal: Spacing.two + 2, paddingVertical: Spacing.one, borderRadius: Spacing.two },
  buttons: { flexDirection: 'row', gap: Spacing.one },
  rateButton: { width: 36, height: 32, borderRadius: Spacing.two, alignItems: 'center', justifyContent: 'center' },
  icon: { fontSize: 16, lineHeight: 20 },
});
