/**
 * NeonButton.tsx
 *
 * A reusable primary button with aurora glow effect.
 * Supports primary, secondary, outline, and aurora variants.
 */

import React from 'react';
import {
  TouchableOpacity,
  Text,
  View,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
  Animated,
} from 'react-native';
import Svg, { Defs, LinearGradient, Stop, Rect } from 'react-native-svg';
import { useTheme } from '../hooks/useTheme';

interface NeonButtonProps {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
  variant?: 'primary' | 'secondary' | 'outline' | 'aurora';
  icon?: React.ReactNode;
}

export const NeonButton = ({
  title,
  onPress,
  loading = false,
  disabled = false,
  style,
  textStyle,
  variant = 'primary',
  icon,
}: NeonButtonProps) => {
  const { colors, borderRadius, spacing } = useTheme();
  const [scaleValue] = React.useState(new Animated.Value(1));

  const handlePressIn = () => {
    Animated.spring(scaleValue, {
      toValue: 0.96,
      useNativeDriver: true,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(scaleValue, {
      toValue: 1,
      friction: 4,
      tension: 40,
      useNativeDriver: true,
    }).start();
  };

  const getBackgroundColor = () => {
    if (disabled) return colors.surfaceHighlight;
    if (variant === 'aurora') return 'transparent';
    if (variant === 'primary') return colors.primary;
    if (variant === 'secondary') return colors.surfaceHighlight;
    return 'transparent';
  };

  const getTextColor = () => {
    if (disabled) return colors.textMuted;
    if (variant === 'primary' || variant === 'aurora') return '#FFFFFF';
    if (variant === 'secondary') return colors.text;
    return colors.primary;
  };

  const getBorderColor = () => {
    if (disabled) return colors.border;
    if (variant === 'outline') return colors.primary;
    return 'transparent';
  };

  const isAurora = variant === 'aurora' && !disabled;

  return (
    <Animated.View style={{ transform: [{ scale: scaleValue }] }}>
      <TouchableOpacity
        onPress={onPress}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        disabled={disabled || loading}
        activeOpacity={0.8}
        style={[
          styles.button,
          {
            backgroundColor: getBackgroundColor(),
            borderColor: getBorderColor(),
            borderWidth: variant === 'outline' ? 1 : 0,
            borderRadius: borderRadius.md,
            paddingVertical: spacing.md,
            shadowColor:
              (variant === 'primary' || variant === 'aurora') && !disabled
                ? colors.primary
                : 'transparent',
            overflow: 'hidden',
          },
          style,
        ]}>
        {isAurora && (
          <View style={StyleSheet.absoluteFill}>
            <Svg width="100%" height="100%">
              <Defs>
                <LinearGradient id="btnAurora" x1="0%" y1="0%" x2="100%" y2="0%">
                  <Stop offset="0%" stopColor={colors.auroraStart} />
                  <Stop offset="50%" stopColor={colors.auroraMid} />
                  <Stop offset="100%" stopColor={colors.auroraEnd} />
                </LinearGradient>
              </Defs>
              <Rect x="0" y="0" width="100%" height="100%" fill="url(#btnAurora)" />
            </Svg>
          </View>
        )}
        {loading ? (
          <ActivityIndicator color={getTextColor()} />
        ) : (
          <View style={styles.contentRow}>
            {icon && <View style={styles.iconWrap}>{icon}</View>}
            <Text style={[styles.text, { color: getTextColor() }, textStyle]}>
              {title}
            </Text>
          </View>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    justifyContent: 'center',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 4,
  },
  contentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  iconWrap: {
    marginRight: 2,
  },
  text: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
});
