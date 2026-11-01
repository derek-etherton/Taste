/** The weight on general quality (the API's `quality`, 0 to 1): how much a book's ratings from other
 * readers count towards its score, shown as a percentage. A settings row: label and value, then
 * the slider. */
import { Slider } from '@expo/ui/community/slider';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

const SETTLE_MS = 400; // lists refetch once the slider rests, not on every step of a drag

export function QualitySlider() {
  const { quality, setQuality } = useSettings();
  const theme = useTheme();
  const [value, setValue] = useState(quality);
  useEffect(() => {
    if (value === quality) return;
    const t = setTimeout(() => setQuality(value), SETTLE_MS);
    return () => clearTimeout(t);
  }, [value, quality, setQuality]);
  return (
    <View style={styles.row}>
      <View style={styles.labels}>
        <ThemedText type="body" style={styles.flex}>
          Book rating contribution
        </ThemedText>
        <ThemedText type="body" themeColor="secondaryLabel" style={styles.number}>
          {Math.round(value * 100)}%
        </ThemedText>
      </View>
      <Slider
        value={value}
        minimumValue={0}
        maximumValue={1}
        step={0.05}
        onValueChange={(v) => setValue(Math.round(v * 20) / 20)}
        minimumTrackTintColor={theme.accent}
        accessibilityLabel="Book rating contribution"
        style={styles.slider}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { paddingHorizontal: Spacing.three, paddingVertical: 12, gap: Spacing.two },
  labels: { flexDirection: 'row', alignItems: 'center' },
  flex: { flex: 1 },
  number: { fontVariant: ['tabular-nums'] },
  slider: { width: '100%', height: 32 },
});
