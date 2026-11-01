/** The weight on general quality (the API's `quality`, 0 to 1): how much a book's ratings from other
 * readers count towards its score, shown as a percentage. */
import Slider from '@react-native-community/slider';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ACCENT } from '@/components/kit';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useSettings } from '@/state/settings';

/** 0 to 1 in steps of 0.05. Lists only refetch when you let go, not on every step of the drag. */
export function QualitySlider() {
  const { quality, setQuality } = useSettings();
  const theme = useTheme();
  const [dragging, setDragging] = useState<number | null>(null);
  return (
    <View style={styles.row}>
      <ThemedText type="small" themeColor="textSecondary">
        Book rating contribution: {Math.round((dragging ?? quality) * 100)}%
      </ThemedText>
      <Slider
        style={styles.slider}
        minimumValue={0}
        maximumValue={1}
        step={0.05}
        value={quality}
        onValueChange={setDragging}
        onSlidingComplete={(v) => {
          setQuality(Math.round(v * 20) / 20);
          setDragging(null);
        }}
        minimumTrackTintColor={ACCENT}
        maximumTrackTintColor={theme.backgroundSelected}
        thumbTintColor={ACCENT}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { gap: Spacing.one },
  slider: { width: '100%', maxWidth: 320, height: 28 },
});
