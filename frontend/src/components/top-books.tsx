/** "Your 3 books": the books that best match your taste (liked or not yet read), ranked, as three
 * covers side by side. Tap one for its page. */
import { Image } from 'expo-image';
import { Pressable, StyleSheet, View } from 'react-native';

import type { ItemCard } from '@/api/client';
import { openItem } from '@/components/item-row';
import { Icon } from '@/components/kit';
import { signed } from '@/components/tag-charts';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function TopBooks({ items }: { items: ItemCard[] }) {
  const theme = useTheme();
  return (
    <View style={styles.row}>
      {items.map((item, i) => (
        <Pressable
          key={item.key}
          accessibilityRole="link"
          accessibilityLabel={`${i + 1}. ${item.title} by ${item.creator}, score ${signed(item.score)}${item.rated === 1 ? ', liked' : ''}`}
          onPress={() => openItem(item.key)}
          style={({ pressed }) => [styles.book, pressed && styles.pressed]}>
          <View style={[styles.cover, styles.shadow, { backgroundColor: theme.placeholder }]}>
            {item.cover_url && <Image source={{ uri: item.cover_url }} style={styles.cover} contentFit="cover" transition={200} />}
            <View style={[styles.rank, { backgroundColor: theme.button }]}>
              <ThemedText type="footnote" style={[styles.rankText, { color: theme.onButton }]}>
                {i + 1}
              </ThemedText>
            </View>
          </View>
          <ThemedText type="subheadline" numberOfLines={2} style={styles.title}>
            {item.title}
          </ThemedText>
          <ThemedText type="footnote" themeColor="secondaryLabel" numberOfLines={1}>
            {item.creator}
          </ThemedText>
          <View style={styles.badges}>
            <View style={[styles.capsule, { backgroundColor: theme.accentFill }]}>
              <ThemedText type="footnote" style={[styles.strong, { color: theme.accent }]}>
                {signed(item.score)}
              </ThemedText>
            </View>
            {item.rated === 1 && (
              <View style={[styles.capsule, styles.liked, { backgroundColor: theme.fill }]}>
                <Icon name={{ ios: 'hand.thumbsup.fill', md: 'thumb_up' }} size={11} color={theme.secondaryLabel} />
                <ThemedText type="footnote" themeColor="secondaryLabel">
                  Liked
                </ThemedText>
              </View>
            )}
          </View>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: Spacing.three, padding: Spacing.three },
  book: { flex: 1, gap: 4 },
  pressed: { opacity: 0.6 },
  cover: { width: '100%', aspectRatio: 2 / 3, borderRadius: 6 },
  shadow: { boxShadow: '0 3px 10px rgba(0, 0, 0, 0.16)', marginBottom: Spacing.one },
  rank: {
    position: 'absolute',
    top: 6,
    left: 6,
    minWidth: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  rankText: { fontWeight: '700', fontVariant: ['tabular-nums'] },
  title: { fontWeight: '600' },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 2 },
  capsule: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: Radius.capsule },
  liked: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  strong: { fontWeight: '600', fontVariant: ['tabular-nums'] },
});
