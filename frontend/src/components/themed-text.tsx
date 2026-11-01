/** Text in one of Apple's text styles (largeTitle … caption) and a theme colour (label by default). */
import { Text, type TextProps } from 'react-native';

import { type TextStyleName, type ThemeColor, Type } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export type ThemedTextProps = TextProps & {
  type?: TextStyleName;
  themeColor?: ThemeColor;
};

export function ThemedText({ style, type = 'body', themeColor, ...rest }: ThemedTextProps) {
  const theme = useTheme();
  return <Text style={[Type[type], { color: theme[themeColor ?? 'label'] }, style]} {...rest} />;
}
