/**
 * AuroraGradient.tsx
 *
 * SVG-based aurora gradient background using react-native-svg.
 * Renders the characteristic aurora gradient as a decorative backdrop
 * for CTA cards, hero sections, and branding areas.
 */

import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import Svg, { Defs, LinearGradient, Stop, Rect } from 'react-native-svg';
import { useTheme } from '../hooks/useTheme';

interface AuroraGradientProps {
  children?: React.ReactNode;
  style?: ViewStyle;
  variant?: 'horizontal' | 'diagonal' | 'vertical';
  intensity?: 'full' | 'muted';
}

export const AuroraGradient = ({
  children,
  style,
  variant = 'horizontal',
  intensity = 'full',
}: AuroraGradientProps) => {
  const { colors } = useTheme();

  const getCoords = () => {
    switch (variant) {
      case 'diagonal': return { x1: '0%', y1: '0%', x2: '100%', y2: '100%' };
      case 'vertical': return { x1: '0%', y1: '0%', x2: '0%', y2: '100%' };
      default: return { x1: '0%', y1: '0%', x2: '100%', y2: '0%' };
    }
  };

  const coords = getCoords();
  const opacity = intensity === 'muted' ? 0.6 : 1;

  return (
    <View style={[styles.container, style]}>
      <View style={StyleSheet.absoluteFill}>
        <Svg width="100%" height="100%" preserveAspectRatio="none">
          <Defs>
            <LinearGradient id="auroraGrad" {...coords}>
              <Stop offset="0%" stopColor={colors.auroraStart} stopOpacity={opacity} />
              <Stop offset="50%" stopColor={colors.auroraMid} stopOpacity={opacity} />
              <Stop offset="100%" stopColor={colors.auroraEnd} stopOpacity={opacity} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#auroraGrad)" />
        </Svg>
      </View>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    overflow: 'hidden',
  },
});
