/**
 * PROVENIQ Ops - Business Type Selection
 * First step after login - choose your business category
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  TouchableOpacity,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudContainer } from '../components';
import { useAuthStore } from '../store/authStore';

interface BusinessTypeScreenProps {
  onTypeSelected: () => void;
  onBack?: () => void;
}

type BusinessType = 'RESTAURANT' | 'RETAIL' | 'WAREHOUSE';

interface BusinessOption {
  type: BusinessType;
  icon: string;
  title: string;
  description: string;
  examples: string;
}

const BUSINESS_OPTIONS: BusinessOption[] = [
  {
    type: 'RESTAURANT',
    icon: '🍽️',
    title: 'Restaurant & Food Service',
    description: 'Kitchens, cafeterias, bars, catering',
    examples: 'Track perishables, manage vendors like SYSCO, reduce food waste',
  },
  {
    type: 'RETAIL',
    icon: '🏪',
    title: 'Retail Store',
    description: 'Shops, boutiques, convenience stores',
    examples: 'SKU tracking, shrinkage detection, reorder automation',
  },
  {
    type: 'WAREHOUSE',
    icon: '📦',
    title: 'Warehouse & Distribution',
    description: 'Storage facilities, fulfillment centers',
    examples: 'Bulk inventory, receiving verification, zone management',
  },
];

export function BusinessTypeScreen({ onTypeSelected, onBack }: BusinessTypeScreenProps) {
  const { setBusinessType, user } = useAuthStore();

  const handleSelectType = (type: BusinessType) => {
    setBusinessType(type);
    onTypeSelected();
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Progress */}
      <View style={styles.progress}>
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={[styles.progressDot, styles.progressDotActive]} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
      </View>

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.step}>STEP 2 OF 6</Text>
        <Text style={styles.title}>What type of business do you operate?</Text>
        <Text style={styles.subtitle}>This helps optimize for your specific needs</Text>
      </View>

      {/* Content */}
      <View style={styles.content}>
        {/* Options */}
        <View style={styles.options}>
          {BUSINESS_OPTIONS.map((option) => (
            <TouchableOpacity
              key={option.type}
              style={styles.optionCard}
              onPress={() => handleSelectType(option.type)}
              activeOpacity={0.7}
            >
              <View style={styles.optionHeader}>
                <Text style={styles.optionIcon}>{option.icon}</Text>
                <Text style={styles.optionTitle}>{option.title}</Text>
              </View>
              <Text style={styles.optionDescription}>{option.description}</Text>
              <Text style={styles.optionExamples}>{option.examples}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <Text style={styles.footerText}>
          You can manage multiple locations after setup
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  progress: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: spacing.md,
  },
  progressDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.hudBorder,
  },
  progressDotActive: {
    backgroundColor: colors.primary,
    width: 24,
  },
  header: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  step: {
    ...typography.labelSmall,
    color: colors.primary,
    letterSpacing: 2,
    marginBottom: spacing.sm,
  },
  content: {
    flex: 1,
    padding: spacing.lg,
  },
  title: {
    ...typography.headingMedium,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.bodySmall,
    color: colors.textMuted,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  options: {
    gap: spacing.md,
  },
  optionCard: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 12,
    padding: spacing.lg,
  },
  optionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  optionIcon: {
    fontSize: 32,
    marginRight: spacing.md,
  },
  optionTitle: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    fontWeight: '600',
    flex: 1,
  },
  optionDescription: {
    ...typography.bodyMedium,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  optionExamples: {
    ...typography.bodySmall,
    color: colors.textMuted,
    fontStyle: 'italic',
  },
  footer: {
    padding: spacing.lg,
    alignItems: 'center',
  },
  footerText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
});
