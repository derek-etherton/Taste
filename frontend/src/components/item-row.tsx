/** One book as a row of an inset-grouped list: cover, title, author and year, why it's
 * recommended (tap for its page), its score (tap for why), and like / meh / dislike. */
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import type { ItemCard, Rating } from '@/api/client';
import { useRate } from '@/api/hooks';
import { Icon, type IconName, Separator, groupedRow } from '@/components/kit';
import { signed } from '@/components/tag-charts';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const BUTTONS: { value: Rating; icon: IconName; label: string; short: string }[] = [
  { value: 1, icon: { ios: 'hand.thumbsup', md: 'thumb_up' }, label: 'Like', short: 'Like' },
  { value: 0, icon: { ios: 'minus', md: 'remove' }, label: 'Meh: tried it, neither loved nor hated it', short: 'Meh' },
  { value: -1, icon: { ios: 'hand.thumbsdown', md: 'thumb_down' }, label: 'Dislike', short: 'Dislike' },
];

const COVER = { width: 44, height: 66 };
const TEXT_INSET = Spacing.three + COVER.width + Spacing.three; // separators line up with the text

export function openItem(key: string) {
  router.push({ pathname: '/item/[key]', params: { key } });
}

/** Like / meh / dislike. Compact circles in lists; labelled capsules on a book's page. Tapping
 * the current rating clears it. */
export function RatingButtons({ item, labelled }: { item: ItemCard; labelled?: boolean }) {
  const { user } = useSettings();
  const rate = useRate(user);
  const theme = useTheme();
  return (
    <View style={styles.buttons}>
      {BUTTONS.map((b) => {
        const on = item.rated === b.value;
        const color = on ? theme.onButton : theme.accent;
        return (
          <Pressable
            key={b.value}
            accessibilityRole="button"
            accessibilityLabel={b.label}
            accessibilityState={{ selected: on }}
            hitSlop={labelled ? 0 : 4}
            onPress={() => rate.mutate({ key: item.key, value: b.value, current: item.rated })}
            style={({ pressed }) => [
              labelled ? styles.labelled : styles.circle,
              { backgroundColor: on ? theme.button : theme.fill, opacity: pressed ? 0.7 : 1 },
            ]}>
            <Icon name={b.icon} size={labelled ? 17 : 15} color={color} />
            {labelled && (
              <ThemedText type="subheadline" style={[styles.semibold, { color }]}>
                {b.short}
              </ThemedText>
            )}
          </Pressable>
        );
      })}
    </View>
  );
}

export function ItemRow({
  item,
  index = 0,
  count,
  source,
  onExplain,
}: {
  item: ItemCard;
  /** Position in its list: rows after the first get a separator. */
  index?: number;
  /** The list's length, when the row draws its own grouped card (a FlatList); omit inside a Section. */
  count?: number;
  source?: string;
  onExplain?: (item: ItemCard) => void;
}) {
  const theme = useTheme();
  const book = item.key.startsWith('book:');
  const details = [
    item.location ?? '',
    item.creator,
    item.year ? String(item.year) : '',
    item.similarity != null ? `${Math.round(item.similarity * 100)}% similar` : '',
    item.tag_match != null ? `${Math.round(item.tag_match * 100)}% tag match` : '',
  ].filter(Boolean);
  const because = item.because
    .map((b) => (b.from_other_domain && source ? `${b.tag} (from ${source})` : b.tag))
    .join(', ');
  return (
    <View style={count != null ? groupedRow(index, count, theme.card) : undefined}>
      {index > 0 && <Separator inset={book ? TEXT_INSET : Spacing.three} />}
      <View style={styles.row}>
        <Pressable
          accessibilityRole="link"
          onPress={() => openItem(item.key)}
          style={({ pressed }) => [styles.main, pressed && styles.pressed]}>
          {book && (
            <View style={[styles.cover, { backgroundColor: theme.placeholder }]}>
              {item.cover_url && <Image source={{ uri: item.cover_url }} style={styles.cover} contentFit="cover" transition={150} />}
            </View>
          )}
          <View style={styles.text}>
            <ThemedText type="headline" numberOfLines={2}>
              {item.title}
            </ThemedText>
            {details.length > 0 && (
              <ThemedText type="subheadline" themeColor="secondaryLabel" numberOfLines={1}>
                {details.join(' · ')}
              </ThemedText>
            )}
            {because ? (
              <ThemedText type="footnote" themeColor="secondaryLabel" numberOfLines={2}>
                {because}
              </ThemedText>
            ) : null}
          </View>
        </Pressable>
        <View style={styles.side}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Score ${signed(item.score)}: why`}
            onPress={() => (onExplain ? onExplain(item) : openItem(item.key))}
            style={({ pressed }) => [styles.score, { backgroundColor: theme.accentFill }, pressed && styles.pressed]}>
            <ThemedText type="footnote" style={[styles.scoreText, { color: theme.accent }]}>
              {signed(item.score)}
            </ThemedText>
          </Pressable>
          <RatingButtons item={item} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingVertical: 12,
    paddingHorizontal: Spacing.three,
  },
  main: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: Spacing.three },
  pressed: { opacity: 0.6 },
  cover: { ...COVER, borderRadius: Radius.cover, overflow: 'hidden' }, // a placeholder when there's none, so titles line up
  text: { flex: 1, gap: 2 },
  side: { alignItems: 'flex-end', gap: Spacing.two },
  score: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: Radius.capsule },
  scoreText: { fontWeight: '600', fontVariant: ['tabular-nums'] },
  buttons: { flexDirection: 'row', gap: 6 },
  circle: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  labelled: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    minHeight: 34,
    paddingHorizontal: 14,
    borderRadius: Radius.capsule,
  },
  semibold: { fontWeight: '600' },
});
