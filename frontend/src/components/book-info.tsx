/** What Open Library knows about a book, for its page: cover, facts, blurb, subjects, links. */
import { Image } from 'expo-image';
import { useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import type { BookInfo } from '@/api/client';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// MARC language codes Open Library uses; anything else shows as its code.
const LANGUAGES: Record<string, string> = {
  eng: 'English', fre: 'French', ger: 'German', rus: 'Russian', spa: 'Spanish', ita: 'Italian', por: 'Portuguese',
  jpn: 'Japanese', chi: 'Chinese', kor: 'Korean', swe: 'Swedish', nor: 'Norwegian', dan: 'Danish', dut: 'Dutch',
  pol: 'Polish', cze: 'Czech', hun: 'Hungarian', fin: 'Finnish', gre: 'Greek', grc: 'Ancient Greek', lat: 'Latin',
  heb: 'Hebrew', ara: 'Arabic', tur: 'Turkish', per: 'Persian', hin: 'Hindi', ice: 'Icelandic', ukr: 'Ukrainian',
};

/** Cover beside the title block; nothing if there's no cover or it fails to load. */
export function BookCover({ book }: { book: BookInfo }) {
  const [failed, setFailed] = useState(false);
  if (!book.cover_url || failed) return null;
  return (
    <Image
      source={{ uri: book.cover_url }}
      style={styles.cover}
      contentFit="cover"
      accessibilityLabel="Cover"
      onError={() => setFailed(true)}
    />
  );
}

/** "First published 1937 · 310 pages · translated from French". */
export function bookFacts(book: BookInfo): string {
  const language = book.original_language;
  return [
    book.first_published ? `First published ${book.first_published}` : '',
    book.pages ? `${book.pages} pages` : '',
    language && language !== 'eng' ? `originally in ${LANGUAGES[language] ?? language}` : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

function Chips({ label, values }: { label: string; values: string[] }) {
  const theme = useTheme();
  if (!values.length) return null;
  return (
    <View style={styles.chipRow}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.chipLabel}>
        {label}
      </ThemedText>
      {values.map((v) => (
        <View key={v} style={[styles.chip, { backgroundColor: theme.backgroundElement }]}>
          <ThemedText type="small">{v}</ThemedText>
        </View>
      ))}
    </View>
  );
}

function ExternalLink({ title, url }: { title: string; url: string }) {
  return (
    <Pressable accessibilityRole="link" onPress={() => Linking.openURL(url)} style={({ pressed }) => pressed && { opacity: 0.6 }}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.link}>
        {title} ↗
      </ThemedText>
    </Pressable>
  );
}

/** The blurb (a few lines, tap for more), subject chips and outbound links. */
export function BookAbout({ book }: { book: BookInfo }) {
  const [open, setOpen] = useState(false);
  const text = book.description ?? (book.first_sentence ? `“${book.first_sentence}”` : null);
  const wikipedia = book.links.find((l) => /wikipedia\.org/.test(l.url));
  return (
    <View style={styles.about}>
      {text && (
        <Pressable onPress={() => setOpen(!open)} accessibilityRole="button" accessibilityHint="Shows the whole description">
          <ThemedText numberOfLines={open ? undefined : 4}>{text}</ThemedText>
          {!open && text.length > 240 && (
            <ThemedText type="small" themeColor="textSecondary">
              more
            </ThemedText>
          )}
        </Pressable>
      )}
      <Chips label="Subjects" values={book.subjects} />
      <Chips label="Places" values={book.places} />
      <Chips label="People" values={book.people} />
      <Chips label="Times" values={book.times} />
      <View style={styles.links}>
        <ExternalLink title="Open Library" url={book.url} />
        {wikipedia && <ExternalLink title="Wikipedia" url={wikipedia.url} />}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  cover: { width: 96, aspectRatio: 2 / 3, borderRadius: Spacing.one },
  about: { gap: Spacing.two },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: Spacing.one },
  chipLabel: { marginRight: Spacing.one },
  chip: { paddingVertical: 2, paddingHorizontal: Spacing.two, borderRadius: Spacing.three },
  links: { flexDirection: 'row', gap: Spacing.three },
  link: { textDecorationLine: 'underline' },
});
