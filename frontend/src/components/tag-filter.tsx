/** "Filter by tags": a button that opens a searchable tag picker, and the chosen tags as removable
 * capsules. Choosing tags hides nothing: the list is re-sorted by tag match × where it was on
 * your list. */
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { useTags } from '@/api/hooks';
import { Button, Icon, Loading, Note, SearchField, Separator } from '@/components/kit';
import { Sheet } from '@/components/sheet';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const MAX = 10; // the API's limit

export function TagFilter({ domain, value, onChange }: { domain: string; value: string[]; onChange: (tags: string[]) => void }) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const toggle = (t: string) => onChange(value.includes(t) ? value.filter((v) => v !== t) : [...value, t]);
  return (
    <View style={styles.bar}>
      <Button
        small
        variant={value.length ? 'tinted' : 'gray'}
        icon={{ ios: 'line.3.horizontal.decrease.circle', md: 'filter_list' }}
        label={value.length ? `Tags (${value.length})` : 'Filter by Tags'}
        onPress={() => setOpen(true)}
      />
      {value.map((t) => (
        <Pressable
          key={t}
          accessibilityRole="button"
          accessibilityLabel={`Remove ${t}`}
          onPress={() => toggle(t)}
          style={({ pressed }) => [styles.capsule, { backgroundColor: theme.accentFill, opacity: pressed ? 0.6 : 1 }]}>
          <ThemedText type="subheadline" style={{ color: theme.accent }}>
            {t}
          </ThemedText>
          <Icon name={{ ios: 'xmark', md: 'close' }} size={11} color={theme.accent} />
        </Pressable>
      ))}
      <TagPicker domain={domain} open={open} value={value} onToggle={toggle} onClear={() => onChange([])} onClose={() => setOpen(false)} />
    </View>
  );
}

function TagPicker({
  domain,
  open,
  value,
  onToggle,
  onClear,
  onClose,
}: {
  domain: string;
  open: boolean;
  value: string[];
  onToggle: (tag: string) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  const theme = useTheme();
  const tags = useTags(domain);
  const [text, setText] = useState('');
  const shown = useMemo(() => {
    const q = text.trim().toLowerCase();
    const all = tags.data ?? [];
    return q ? all.filter((t) => t.toLowerCase().includes(q)) : all;
  }, [tags.data, text]);
  const full = value.length >= MAX;

  return (
    <Sheet
      visible={open}
      title="Filter by Tags"
      onClose={onClose}
      leading={
        <Pressable accessibilityRole="button" onPress={onClear} disabled={!value.length} hitSlop={8}>
          <ThemedText type="body" style={{ color: theme.accent, opacity: value.length ? 1 : 0.4 }}>
            Clear
          </ThemedText>
        </Pressable>
      }>
      <View style={styles.head}>
        <SearchField value={text} onChangeText={setText} placeholder={`Search ${tags.data?.length ?? ''} tags`} autoFocus />
        <ThemedText type="footnote" themeColor="secondaryLabel" style={styles.hint}>
          Books with the chosen tags that are also high on your list come first. Nothing is hidden.
          {value.length ? ` ${value.length} chosen${full ? `, at most ${MAX}` : ''}.` : ''}
        </ThemedText>
      </View>
      {tags.isPending && <Loading />}
      {tags.error && <Note tone="error">{tags.error.message}</Note>}
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent} keyboardShouldPersistTaps="handled">
        {shown.length > 0 && (
          <View style={[styles.card, { backgroundColor: theme.card }]}>
            {shown.map((t, i) => {
              const on = value.includes(t);
              return (
                <View key={t}>
                  {i > 0 && <Separator />}
                  <Pressable
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: on, disabled: !on && full }}
                    disabled={!on && full}
                    onPress={() => onToggle(t)}
                    style={({ pressed }) => [
                      styles.option,
                      pressed && { backgroundColor: theme.fill },
                      !on && full && styles.disabled,
                    ]}>
                    <ThemedText type="body" style={styles.flex}>
                      {t}
                    </ThemedText>
                    {on && <Icon name={{ ios: 'checkmark', md: 'check' }} size={17} color={theme.accent} />}
                  </Pressable>
                </View>
              );
            })}
          </View>
        )}
        {tags.data && !shown.length && <Note>No tags match.</Note>}
      </ScrollView>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: Spacing.two },
  capsule: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    minHeight: 34,
    paddingHorizontal: 14,
    borderRadius: Radius.capsule,
  },
  head: { padding: Spacing.three, gap: Spacing.two },
  hint: { paddingHorizontal: Spacing.one },
  list: { flex: 1, minHeight: 0 },
  listContent: { paddingHorizontal: Spacing.three, paddingBottom: Spacing.four },
  card: { borderRadius: Radius.card, overflow: 'hidden' },
  option: { flexDirection: 'row', alignItems: 'center', minHeight: 44, paddingHorizontal: Spacing.three, userSelect: 'none' },
  disabled: { opacity: 0.4 },
  flex: { flex: 1 },
});
