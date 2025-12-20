/**
 * PROVENIQ Ops - Ready Screen
 * Final onboarding screen - confirmation
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
} from 'react-native';
import { colors, typography, spacing } from '../../theme';
import { HudButton } from '../../components';

interface ReadyScreenProps {
  businessName: string;
  locationName: string;
  vendorCount: number;
  teamCount: number;
  onFinish: () => void;
}

export function ReadyScreen({ 
  businessName, 
  locationName, 
  vendorCount, 
  teamCount,
  onFinish 
}: ReadyScreenProps) {
  return (
    <SafeAreaView style={styles.container}>
      {/* Content */}
      <View style={styles.content}>
        <View style={styles.successIcon}>
          <Text style={styles.checkmark}>✓</Text>
        </View>

        <Text style={styles.title}>You're all set!</Text>
        <Text style={styles.subtitle}>
          {businessName} is ready to use PROVENIQ Ops
        </Text>

        {/* Summary */}
        <View style={styles.summary}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryIcon}>📍</Text>
            <View style={styles.summaryText}>
              <Text style={styles.summaryLabel}>Location</Text>
              <Text style={styles.summaryValue}>{locationName}</Text>
            </View>
          </View>

          <View style={styles.summaryItem}>
            <Text style={styles.summaryIcon}>🏪</Text>
            <View style={styles.summaryText}>
              <Text style={styles.summaryLabel}>Vendors</Text>
              <Text style={styles.summaryValue}>
                {vendorCount > 0 ? `${vendorCount} connected` : 'None yet'}
              </Text>
            </View>
          </View>

          <View style={styles.summaryItem}>
            <Text style={styles.summaryIcon}>👥</Text>
            <View style={styles.summaryText}>
              <Text style={styles.summaryLabel}>Team</Text>
              <Text style={styles.summaryValue}>
                {teamCount > 0 ? `${teamCount} invited` : 'Just you'}
              </Text>
            </View>
          </View>
        </View>

        {/* Next Steps */}
        <View style={styles.nextSteps}>
          <Text style={styles.nextStepsTitle}>WHAT'S NEXT</Text>
          <Text style={styles.nextStepsItem}>• Start your first inventory scan</Text>
          <Text style={styles.nextStepsItem}>• Set par levels for your items</Text>
          <Text style={styles.nextStepsItem}>• Connect vendor API credentials in Settings</Text>
        </View>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <HudButton
          title="GO TO DASHBOARD"
          onPress={onFinish}
          size="large"
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
  },
  successIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#22c55e',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  checkmark: {
    fontSize: 48,
    color: colors.bgPrimary,
    fontWeight: 'bold',
  },
  title: {
    ...typography.headingLarge,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.bodyLarge,
    color: colors.textMuted,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  summary: {
    width: '100%',
    backgroundColor: colors.bgSecondary,
    borderRadius: 12,
    padding: spacing.lg,
    marginBottom: spacing.xl,
  },
  summaryItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  summaryIcon: {
    fontSize: 24,
    width: 40,
  },
  summaryText: {
    flex: 1,
  },
  summaryLabel: {
    ...typography.labelSmall,
    color: colors.textMuted,
  },
  summaryValue: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  nextSteps: {
    width: '100%',
    padding: spacing.md,
  },
  nextStepsTitle: {
    ...typography.labelSmall,
    color: colors.primary,
    letterSpacing: 2,
    marginBottom: spacing.sm,
  },
  nextStepsItem: {
    ...typography.bodyMedium,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  footer: {
    padding: spacing.lg,
  },
});
