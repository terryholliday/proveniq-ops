/**
 * PROVENIQ Ops - Typography System
 * Clean, technical, machine-readable
 */

import { TextStyle } from 'react-native';

export const typography = {
  // Display - large headings
  displayLarge: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.5,
    lineHeight: 40,
  } as TextStyle,
  
  displayMedium: {
    fontSize: 24,
    fontWeight: '600',
    letterSpacing: -0.3,
    lineHeight: 32,
  } as TextStyle,
  
  // Headings
  headingLarge: {
    fontSize: 20,
    fontWeight: '600',
    letterSpacing: 0,
    lineHeight: 28,
  } as TextStyle,
  
  headingMedium: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.1,
    lineHeight: 24,
  } as TextStyle,
  
  headingSmall: {
    fontSize: 14,
    fontWeight: '600',
    letterSpacing: 0.2,
    lineHeight: 20,
  } as TextStyle,
  
  // Body text
  bodyLarge: {
    fontSize: 16,
    fontWeight: '400',
    letterSpacing: 0.1,
    lineHeight: 24,
  } as TextStyle,
  
  bodyMedium: {
    fontSize: 14,
    fontWeight: '400',
    letterSpacing: 0.15,
    lineHeight: 20,
  } as TextStyle,
  
  bodySmall: {
    fontSize: 12,
    fontWeight: '400',
    letterSpacing: 0.2,
    lineHeight: 16,
  } as TextStyle,
  
  // Labels - HUD elements
  labelLarge: {
    fontSize: 14,
    fontWeight: '500',
    letterSpacing: 0.5,
    lineHeight: 20,
    textTransform: 'uppercase',
  } as TextStyle,
  
  labelMedium: {
    fontSize: 12,
    fontWeight: '500',
    letterSpacing: 0.8,
    lineHeight: 16,
    textTransform: 'uppercase',
  } as TextStyle,
  
  labelSmall: {
    fontSize: 10,
    fontWeight: '500',
    letterSpacing: 1,
    lineHeight: 14,
    textTransform: 'uppercase',
  } as TextStyle,
  
  // Monospace - data, codes, Bishop output
  mono: {
    fontSize: 14,
    fontWeight: '400',
    letterSpacing: 0,
    lineHeight: 20,
    fontFamily: 'monospace',
  } as TextStyle,
  
  monoSmall: {
    fontSize: 12,
    fontWeight: '400',
    letterSpacing: 0,
    lineHeight: 16,
    fontFamily: 'monospace',
  } as TextStyle,
} as const;

export type TypographyKey = keyof typeof typography;
