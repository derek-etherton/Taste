/** A modal sheet with an iOS navigation bar (title, Done). The native page sheet on iOS;
 * elsewhere a card over a dimmed backdrop. */
import type { PropsWithChildren, ReactNode } from 'react';
import { Modal, Platform, Pressable, StyleSheet, View } from 'react-native';

import { Separator } from '@/components/kit';
import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function Sheet({
  visible,
  title,
  onClose,
  leading,
  children,
}: PropsWithChildren<{ visible: boolean; title: string; onClose: () => void; leading?: ReactNode }>) {
  const theme = useTheme();
  const ios = Platform.OS === 'ios';
  const body = (
    <View style={[styles.sheet, !ios && styles.floating, { backgroundColor: theme.groupedBackground }]}>
      <View style={styles.bar}>
        <View style={styles.side}>{leading}</View>
        <ThemedText type="headline" numberOfLines={1} style={styles.title}>
          {title}
        </ThemedText>
        <View style={[styles.side, styles.trailing]}>
          <Pressable accessibilityRole="button" onPress={onClose} hitSlop={8}>
            {({ pressed }) => (
              <ThemedText type="headline" style={{ color: theme.accent, opacity: pressed ? 0.5 : 1 }}>
                Done
              </ThemedText>
            )}
          </Pressable>
        </View>
      </View>
      <Separator inset={0} />
      <View style={styles.content}>{children}</View>
    </View>
  );
  if (ios) {
    return (
      <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
        {body}
      </Modal>
    );
  }
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        {/* Swallow taps on the sheet itself, so only the backdrop closes it. */}
        <Pressable onPress={() => {}} style={styles.wrap}>
          {body}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0, 0, 0, 0.4)', justifyContent: 'center', padding: Spacing.three },
  wrap: { alignSelf: 'center', width: '100%', maxWidth: 520, height: '85%' },
  sheet: { flex: 1 },
  floating: { borderRadius: Radius.sheet, overflow: 'hidden' },
  bar: { flexDirection: 'row', alignItems: 'center', minHeight: 56, paddingHorizontal: Spacing.three },
  side: { flex: 1, flexDirection: 'row' },
  trailing: { justifyContent: 'flex-end' },
  title: { flex: 2, textAlign: 'center' },
  content: { flex: 1, minHeight: 0 },
});
