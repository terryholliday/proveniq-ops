/**
 * PROVENIQ Ops - Welcome Screen
 * First screen after login - value proposition
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  Dimensions,
} from 'react-native';
import { colors, typography, spacing } from '../../theme';
import { HudButton } from '../../components';

interface WelcomeScreenProps {
  onContinue: () => void;
}

const { width } = Dimensions.get('window');

export function WelcomeScreen({ onContinue }: WelcomeScreenProps) {
  return (
    <SafeAreaView style={styles.container}>
      {/* Progress */}
      <View style={styles.progress}>
        <View style={[styles.progressDot, styles.progressDotActive]} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
      </View>

      {/* Content */}
      <View style={styles.content}>
        <Text style={styles.logo}>P R O V E N I Q</Text>
        <Text style={styles.productName}>O P S</Text>
        
        <View style={styles.valueProps}>
          <View style={styles.valueProp}>
            <Text style={styles.valueIcon}>📷</Text>
            <View style={styles.valueText}>
              <Text style={styles.valueTitle}>Scan Inventory</Text>
              <Text style={styles.valueDesc}>Point, scan, done. Know what you have in seconds.</Text>
            </View>
          </View>

          <View style={styles.valueProp}>
            <Text style={styles.valueIcon}>🔍</Text>
            <View style={styles.valueText}>
              <Text style={styles.valueTitle}>Detect Shrinkage</Text>
              <Text style={styles.valueDesc}>Catch theft, spoilage, and variance before it hurts.</Text>
            </View>
          </View>

          <View style={styles.valueProp}>
            <Text style={styles.valueIcon}>🛒</Text>
            <View style={styles.valueText}>
              <Text style={styles.valueTitle}>Auto-Order</Text>
              <Text style={styles.valueDesc}>Never run out. Orders sent to your vendors automatically.</Text>
            </View>
          </View>

          <View style={styles.valueProp}>
            <Text style={styles.valueIcon}>📊</Text>
            <View style={styles.valueText}>
              <Text style={styles.valueTitle}>Real-Time Visibility</Text>
              <Text style={styles.valueDesc}>Know your inventory across all locations, instantly.</Text>
            </View>
          </View>
        </View>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <HudButton
          title="GET STARTED"
          onPress={onContinue}
          size="large"
        />
        <Text style={styles.footerText}>
          Takes about 3 minutes to set up
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
    paddingVertical: spacing.md,
  },
  progressDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.hudBorder,
    marginHorizontal: 4,
  },
  progressDotActive: {
    backgroundColor: colors.primary,
    width: 24,
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
  },
  logo: {
    color: colors.primary,
    textAlign: 'center',
    fontSize: 22,
    fontWeight: '500',
    marginBottom: spacing.sm,
  },
  productName: {
    color: colors.textPrimary,
    textAlign: 'center',
    fontSize: 48,
    fontWeight: '200',
    marginBottom: spacing.xl,
  },
  valueProps: {
    marginTop: spacing.md,
  },
  valueProp: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: spacing.lg,
  },
  valueIcon: {
    fontSize: 28,
    width: 40,
    marginRight: spacing.md,
  },
  valueText: {
    flex: 1,
  },
  valueTitle: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    fontWeight: '600',
    marginBottom: 2,
  },
  valueDesc: {
    ...typography.bodyMedium,
    color: colors.textMuted,
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
