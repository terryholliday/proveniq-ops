/**
 * PROVENIQ Ops - HUD Container
 * Base container with sci-fi industrial border styling
 */

import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { colors, spacing, borderRadius } from '../../theme';

interface HudContainerProps {
  children: React.ReactNode;
  style?: ViewStyle;
  variant?: 'default' | 'elevated' | 'overlay';
  glowColor?: string;
}

export function HudContainer({ 
  children, 
  style, 
  variant = 'default',
  glowColor = colors.primary,
}: HudContainerProps) {
  return (
    <View style={[
      styles.container,
      variant === 'elevated' && styles.elevated,
      variant === 'overlay' && styles.overlay,
      { shadowColor: glowColor },
      style,
    ]}>
      <View style={[styles.cornerTL, { borderColor: glowColor }]} />
      <View style={[styles.cornerTR, { borderColor: glowColor }]} />
      <View style={[styles.cornerBL, { borderColor: glowColor }]} />
      <View style={[styles.cornerBR, { borderColor: glowColor }]} />
      {children}
    </View>
  );
}

const CORNER_SIZE = 12;

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgSecondary,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    padding: spacing.md,
    position: 'relative',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  elevated: {
    backgroundColor: colors.bgTertiary,
  },
  overlay: {
    backgroundColor: colors.bgOverlay,
  },
  cornerTL: {
    position: 'absolute',
    top: -1,
    left: -1,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderTopWidth: 2,
    borderLeftWidth: 2,
    borderTopLeftRadius: borderRadius.md,
  },
  cornerTR: {
    position: 'absolute',
    top: -1,
    right: -1,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderTopWidth: 2,
    borderRightWidth: 2,
    borderTopRightRadius: borderRadius.md,
  },
  cornerBL: {
    position: 'absolute',
    bottom: -1,
    left: -1,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    borderBottomLeftRadius: borderRadius.md,
  },
  cornerBR: {
    position: 'absolute',
    bottom: -1,
    right: -1,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderBottomWidth: 2,
    borderRightWidth: 2,
    borderBottomRightRadius: borderRadius.md,
  },
});
