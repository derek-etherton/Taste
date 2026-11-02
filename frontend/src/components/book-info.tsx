/** What Open Library knows about a book, for its page: cover, facts, blurb, subjects, links. */
import { Image } from 'expo-image';
import { Fragment, useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import type { BookInfo } from '@/api/client';
import { Icon, Section, Separator } from '@/components/kit';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// MARC language codes Open Library uses; anything else shows as its code.
const LANGUAGES: Record<string, string> = {
  eng: 'English', fre: 'French', ger: 'German', rus: 'Russian', spa: 'Spanish', ita: 'Italian', por: 'Portuguese',
  jpn: 'Japanese', chi: 'Chinese', kor: 'Korean', swe: 'Swedish', nor: 'Norwegian', dan: 'Danish', dut: 'Dutch',
  pol: 'Polish', cze: 'Czech', hun: 'Hungarian', fin: 'Finnish', gre: 'Greek', grc: 'Ancient Greek', lat: 'Latin',
  heb: 'Hebrew', ara: 'Arabic', tur: 'Turkish', per: 'Persian', hin: 'Hindi', ice: 'Icelandic', ukr: 'Ukrainian',
};

/** The cover, at the top of the page; a quiet placeholder if there's none or it fails to load. */
export function BookCover({ book }: { book?: BookInfo | null }) {
  const theme = useTheme();
  const [failed, setFailed] = useState(false);
  return (
    <View style={[styles.cover, styles.shadow, { backgroundColor: theme.placeholder }]}>
      {book?.cover_url && !failed && (
        <Image
          source={{ uri: book.cover_url }}
          style={styles.cover}
          contentFit="cover"
          transition={200}
          accessibilityLabel="Cover"
          onError={() => setFailed(true)}
        />
      )}
    </View>
  );
}

/** "First published 1937 · 310 pages · originally in French". */
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

function Capsules({ label, values }: { label: string; values: string[] }) {
  const theme = useTheme();
  return (
    <View style={styles.group}>
      <ThemedText type="footnote" themeColor="secondaryLabel">
        {label}
      </ThemedText>
      <View style={styles.capsules}>
        {values.map((v) => (
          <View key={v} style={[styles.capsule, { backgroundColor: theme.fill }]}>
            <ThemedText type="subheadline">{v}</ThemedText>
          </View>
        ))}
      </View>
    </View>
  );
}

function LinkRow({ title, url, first }: { title: string; url: string; first?: boolean }) {
  const theme = useTheme();
  return (
    <>
      {!first && <Separator />}
      <Pressable
        accessibilityRole="link"
        onPress={() => /^https?:\/\//i.test(url) && Linking.openURL(url)} // links come from editable Open Library data
        style={({ pressed }) => [styles.linkRow, pressed && { backgroundColor: theme.fill }]}>
        <ThemedText type="body" style={[styles.flex, { color: theme.accent }]}>
          {title}
        </ThemedText>
        <Icon name={{ ios: 'arrow.up.right', md: 'open_in_new' }} size={14} color={theme.accent} />
      </Pressable>
    </>
  );
}

/** "About" (the blurb, a few lines until you tap it, then subjects, places, people, times) and
 * "Links" sections. */
export function BookAbout({ book }: { book: BookInfo }) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const text = book.description ?? (book.first_sentence ? `“${book.first_sentence}”` : null);
  const wikipedia = book.links.find((l) => /wikipedia\.org/.test(l.url));
  const groups = (
    [
      ['Subjects', book.subjects],
      ['Places', book.places],
      ['People', book.people],
      ['Times', book.times],
    ] as const
  ).filter(([, values]) => values.length);
  return (
    <>
      {(text || groups.length > 0) && (
        <Section title="About">
          {text && (
            <Pressable
              onPress={() => setOpen(!open)}
              accessibilityRole="button"
              accessibilityHint="Shows the whole description"
              style={styles.blurb}>
              <ThemedText type="body" numberOfLines={open ? undefined : 5}>
                {text}
              </ThemedText>
              {!open && text.length > 280 && (
                <ThemedText type="body" style={{ color: theme.accent }}>
                  more
                </ThemedText>
              )}
            </Pressable>
          )}
          {groups.map(([label, values], i) => (
            <Fragment key={label}>
              {(text || i > 0) && <Separator />}
              <Capsules label={label} values={[...values]} />
            </Fragment>
          ))}
        </Section>
      )}
      <Section title="Links">
        <LinkRow first title="Open Library" url={book.url} />
        {wikipedia && <LinkRow title="Wikipedia" url={wikipedia.url} />}
      </Section>
    </>
  );
}

const styles = StyleSheet.create({
  cover: { width: 116, aspectRatio: 2 / 3, borderRadius: 6 },
  shadow: { boxShadow: '0 4px 14px rgba(0, 0, 0, 0.18)' },
  flex: { flex: 1 },
  blurb: { padding: Spacing.three, gap: Spacing.one },
  group: { padding: Spacing.three, gap: Spacing.two },
  capsules: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  capsule: { paddingVertical: 4, paddingHorizontal: 10, borderRadius: Radius.capsule },
  linkRow: { flexDirection: 'row', alignItems: 'center', minHeight: 44, paddingHorizontal: Spacing.three },
});
