/**
 * PROVENIQ Ops - Design System Colors
 * Sci-fi industrial aesthetic with HUD-style overlays
 */

export const colors = {
  // Primary palette - industrial sci-fi
  primary: '#00D4FF',      // Cyan - primary actions, active states
  secondary: '#7B61FF',    // Purple - secondary elements
  accent: '#00FF88',       // Green - success, confirmations
  warning: '#FFB800',      // Amber - warnings, caution
  danger: '#FF4757',       // Red - errors, critical alerts
  
  // Background hierarchy
  bgPrimary: '#0A0E14',    // Deep black - main background
  bgSecondary: '#12181F',  // Slightly lighter - cards, panels
  bgTertiary: '#1A2129',   // Elevated surfaces
  bgOverlay: 'rgba(10, 14, 20, 0.85)', // Camera overlay
  
  // Text hierarchy
  textPrimary: '#FFFFFF',
  textSecondary: '#8B9CB3',
  textMuted: '#5A6A7E',
  textInverse: '#0A0E14',
  
  // HUD elements
  hudBorder: 'rgba(0, 212, 255, 0.4)',
  hudGlow: 'rgba(0, 212, 255, 0.15)',
  hudScanline: 'rgba(0, 212, 255, 0.08)',
  
  // State indicators
  stateIdle: '#5A6A7E',
  stateScanning: '#00D4FF',
  stateAnalyzing: '#FFB800',
  stateChecking: '#7B61FF',
  stateQueued: '#00FF88',
  stateBlocked: '#FF4757',
  
  // Confidence levels
  confidenceHigh: '#00FF88',
  confidenceMedium: '#FFB800',
  confidenceLow: '#FF4757',
} as const;

export type ColorKey = keyof typeof colors;
