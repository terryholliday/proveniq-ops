/**
 * PROVENIQ Ops - Bishop Status Display
 * Shows current Bishop FSM state with HUD styling
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography, spacing } from '../../theme';
import { useBishopStore, BishopState } from '../../store';
import { HudContainer } from './HudContainer';

const STATE_COLORS: Record<BishopState, string> = {
  IDLE: colors.stateIdle,
  SCANNING: colors.stateScanning,
  ANALYZING_RISK: colors.stateAnalyzing,
  CHECKING_FUNDS: colors.stateChecking,
  ORDER_QUEUED: colors.stateQueued,
};

const STATE_LABELS: Record<BishopState, string> = {
  IDLE: 'IDLE',
  SCANNING: 'SCANNING',
  ANALYZING_RISK: 'RISK EVAL',
  CHECKING_FUNDS: 'FUNDS CHK',
  ORDER_QUEUED: 'QUEUED',
};

export function BishopStatus() {
  const { state, message, isLoading } = useBishopStore();
  const stateColor = STATE_COLORS[state];
  
  return (
    <HudContainer glowColor={stateColor}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <View style={[styles.indicator, { backgroundColor: stateColor }]} />
          <Text style={styles.title}>BISHOP</Text>
        </View>
        <View style={[styles.stateBadge, { borderColor: stateColor }]}>
          <Text style={[styles.stateText, { color: stateColor }]}>
            {STATE_LABELS[state]}
          </Text>
        </View>
      </View>
      
      <View style={styles.messageContainer}>
        <Text style={styles.message}>{message}</Text>
        {isLoading && (
          <View style={styles.loadingIndicator}>
            <Text style={[styles.loadingDot, { color: stateColor }]}>●</Text>
          </View>
        )}
      </View>
    </HudContainer>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  indicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  title: {
    ...typography.labelMedium,
    color: colors.textSecondary,
  },
  stateBadge: {
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  stateText: {
    ...typography.labelSmall,
  },
  messageContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  message: {
    ...typography.mono,
    color: colors.textPrimary,
    flex: 1,
  },
  loadingIndicator: {
    width: 16,
  },
  loadingDot: {
    fontSize: 12,
  },
});
