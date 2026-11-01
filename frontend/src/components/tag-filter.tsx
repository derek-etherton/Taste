/** "Filter by tags": a button that opens a searchable tag picker, and the chosen tags as removable chips.
 * Choosing tags doesn't hide anything: the list is re-sorted by tag match × where it was on your list. */
import { useMemo, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';

import { useTags } from '@/api/hooks';
import { Button, Loading, Note } from '@/components/kit';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const MAX = 10; // the API's limit

export function TagFilter({ domain, value, onChange }: { domain: string; value: string[]; onChange: (tags: string[]) => void }) {
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const toggle = (t: string) => onChange(value.includes(t) ? value.filter((v) => v !== t) : [...value, t]);
  return (
    <View style={styles.bar}>
      <Pressable
        accessibilityRole="button"
        onPress={() => setOpen(true)}
        style={({ pressed }) => [styles.chip, { backgroundColor: theme.backgroundElement }, pressed && styles.pressed]}>
        <ThemedText type="small" themeColor="textSecondary">
          Filter by tags{value.length ? ` (${value.length})` : ''} ▾
        </ThemedText>
      </Pressable>
      {value.map((t) => (
        <Pressable
          key={t}
          accessibilityRole="button"
          accessibilityLabel={`Remove ${t}`}
          onPress={() => toggle(t)}
          style={({ pressed }) => [styles.chip, { backgroundColor: theme.backgroundSelected }, pressed && styles.pressed]}>
          <ThemedText type="smallBold">{t} ×</ThemedText>
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
    <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable onPress={() => {}} style={styles.sheetWrap}>
          <ThemedView style={[styles.sheet, { borderColor: theme.backgroundSelected }]}>
            <View style={styles.head}>
              <ThemedText type="smallBold">Filter by tags</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                First: what has the chosen tags and is also high on your list. Nothing is hidden.
              </ThemedText>
              <TextInput
                value={text}
                onChangeText={setText}
                placeholder={`Search ${tags.data?.length ?? ''} tags…`}
                placeholderTextColor={theme.textSecondary}
                autoCorrect={false}
                autoFocus
                style={[styles.search, { backgroundColor: theme.backgroundElement, color: theme.text }]}
              />
            </View>
            {tags.isPending && <Loading />}
            {tags.error && <Note tone="error">{tags.error.message}</Note>}
            <ScrollView style={styles.list} keyboardShouldPersistTaps="handled">
              {shown.map((t) => {
                const on = value.includes(t);
                return (
                  <Pressable
                    key={t}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: on, disabled: !on && full }}
                    disabled={!on && full}
                    onPress={() => onToggle(t)}
                    style={({ pressed }) => [
                      styles.option,
                      on && { backgroundColor: theme.backgroundSelected },
                      !on && full && { opacity: 0.4 },
                      pressed && styles.pressed,
                    ]}>
                    <ThemedText type={on ? 'smallBold' : 'small'}>
                      {on ? '☑' : '☐'} {t}
                    </ThemedText>
                  </Pressable>
                );
              })}
              {tags.data && !shown.length && <Note>No tags match.</Note>}
            </ScrollView>
            <View style={styles.foot}>
              <ThemedText type="small" themeColor="textSecondary" style={styles.count}>
                {value.length ? `${value.length} chosen${full ? ` (at most ${MAX})` : ''}` : 'None chosen'}
              </ThemedText>
              <Button label="Clear" onPress={onClear} disabled={!value.length} />
              <Button label="Done" onPress={onClose} primary />
            </View>
          </ThemedView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  chip: { paddingVertical: Spacing.one + 2, paddingHorizontal: Spacing.three, borderRadius: Spacing.four },
  pressed: { opacity: 0.7 },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', padding: Spacing.three },
  sheetWrap: { alignSelf: 'center', width: '100%', maxWidth: 480, height: '80%' },
  sheet: { flex: 1, minHeight: 0, borderRadius: Spacing.four, borderWidth: StyleSheet.hairlineWidth, overflow: 'hidden' },
  head: { padding: Spacing.three, gap: Spacing.two },
  search: { paddingHorizontal: Spacing.three, paddingVertical: Spacing.two + 2, borderRadius: Spacing.three, fontSize: 16 },
  list: { flex: 1, minHeight: 0 }, // minHeight: on web a flex child won't shrink below its content without it
  option: { paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, userSelect: 'none' },
  foot: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, padding: Spacing.three },
  count: { flex: 1 },
});
