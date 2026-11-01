import { View, type ViewProps } from 'react-native';

import type { ThemeColor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export type ThemedViewProps = ViewProps & { type?: ThemeColor };

/** A view on one of the theme's backgrounds (the grouped background by default). */
export function ThemedView({ style, type, ...rest }: ThemedViewProps) {
  const theme = useTheme();
  return <View style={[{ backgroundColor: theme[type ?? 'groupedBackground'] }, style]} {...rest} />;
}
