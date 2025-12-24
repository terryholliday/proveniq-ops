/**
 * PROVENIQ Ops - Vendor Setup Screen
 * Select and optionally connect vendor accounts
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { colors, typography, spacing } from '../../theme';
import { HudButton, HudContainer } from '../../components';

interface VendorSetupScreenProps {
  onContinue: (vendors: VendorSelection[]) => void;
  onSkip: () => void;
  onBack: () => void;
}

export interface VendorSelection {
  vendorId: string;
  vendorName: string;
  selected: boolean;
  customerNumber?: string;
  hasCredentials: boolean;
}

interface Vendor {
  id: string;
  name: string;
  logo: string;
  description: string;
}

const VENDORS: Vendor[] = [
  { id: 'sysco', name: 'SYSCO', logo: '🔵', description: 'Food service distribution' },
  { id: 'usfoods', name: 'US Foods', logo: '🔴', description: 'Food service distribution' },
  { id: 'pfg', name: 'Performance Food Group', logo: '🟢', description: 'Food service distribution' },
  { id: 'gfs', name: 'Gordon Food Service', logo: '🟡', description: 'Regional food service' },
  { id: 'other', name: 'Other Vendor', logo: '⚪', description: 'Manual entry' },
];

export function VendorSetupScreen({ onContinue, onSkip, onBack }: VendorSetupScreenProps) {
  const [selectedVendors, setSelectedVendors] = useState<Set<string>>(new Set());
  const [expandedVendor, setExpandedVendor] = useState<string | null>(null);
  const [customerNumbers, setCustomerNumbers] = useState<Record<string, string>>({});

  const toggleVendor = (vendorId: string) => {
    const newSelected = new Set(selectedVendors);
    if (newSelected.has(vendorId)) {
      newSelected.delete(vendorId);
      setExpandedVendor(null);
    } else {
      newSelected.add(vendorId);
      setExpandedVendor(vendorId);
    }
    setSelectedVendors(newSelected);
  };

  const handleContinue = () => {
    const vendors: VendorSelection[] = Array.from(selectedVendors).map(id => {
      const vendor = VENDORS.find(v => v.id === id)!;
      return {
        vendorId: id,
        vendorName: vendor.name,
        selected: true,
        customerNumber: customerNumbers[id],
        hasCredentials: !!customerNumbers[id],
      };
    });
    onContinue(vendors);
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Progress */}
      <View style={styles.progress}>
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={[styles.progressDot, styles.progressDotActive]} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
      </View>

      <ScrollView 
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.step}>STEP 4 OF 6</Text>
          <Text style={styles.title}>Which vendors do you use?</Text>
          <Text style={styles.subtitle}>
            Select your food/product distributors. You can connect accounts later.
          </Text>
        </View>

        {/* Vendor List */}
        <View style={styles.vendorList}>
          {VENDORS.map((vendor) => {
            const isSelected = selectedVendors.has(vendor.id);
            const isExpanded = expandedVendor === vendor.id;

            return (
              <View key={vendor.id}>
                <TouchableOpacity
                  style={[
                    styles.vendorCard,
                    isSelected && styles.vendorCardSelected,
                  ]}
                  onPress={() => toggleVendor(vendor.id)}
                  activeOpacity={0.7}
                >
                  <Text style={styles.vendorLogo}>{vendor.logo}</Text>
                  <View style={styles.vendorInfo}>
                    <Text style={styles.vendorName}>{vendor.name}</Text>
                    <Text style={styles.vendorDesc}>{vendor.description}</Text>
                  </View>
                  <View style={[styles.checkbox, isSelected && styles.checkboxSelected]}>
                    {isSelected && <Text style={styles.checkmark}>✓</Text>}
                  </View>
                </TouchableOpacity>

                {/* Expanded: Customer Number Input */}
                {isSelected && isExpanded && (
                  <View style={styles.expandedSection}>
                    <Text style={styles.expandedLabel}>
                      CUSTOMER NUMBER (OPTIONAL)
                    </Text>
                    <TextInput
                      style={styles.expandedInput}
                      value={customerNumbers[vendor.id] || ''}
                      onChangeText={(text) => 
                        setCustomerNumbers(prev => ({ ...prev, [vendor.id]: text }))
                      }
                      placeholder="Enter your account number"
                      placeholderTextColor={colors.textMuted}
                    />
                    <Text style={styles.expandedHint}>
                      You can add full API credentials later in Settings
                    </Text>
                  </View>
                )}
              </View>
            );
          })}
        </View>
      </ScrollView>

      {/* Footer */}
      <View style={styles.footer}>
        <HudButton
          title="BACK"
          onPress={onBack}
          variant="ghost"
          style={styles.backButton}
        />
        {selectedVendors.size > 0 ? (
          <HudButton
            title={`CONTINUE (${selectedVendors.size})`}
            onPress={handleContinue}
            style={styles.continueButton}
          />
        ) : (
          <HudButton
            title="SKIP FOR NOW"
            onPress={onSkip}
            variant="secondary"
            style={styles.continueButton}
          />
        )}
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
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
  },
  header: {
    marginBottom: spacing.lg,
  },
  step: {
    ...typography.labelSmall,
    color: colors.primary,
    letterSpacing: 2,
    marginBottom: spacing.sm,
  },
  title: {
    ...typography.headingMedium,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.bodyMedium,
    color: colors.textMuted,
  },
  vendorList: {
    marginTop: spacing.sm,
  },
  vendorCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  vendorCardSelected: {
    borderColor: colors.primary,
    backgroundColor: `${colors.primary}10`,
  },
  vendorLogo: {
    fontSize: 28,
    width: 44,
  },
  vendorInfo: {
    flex: 1,
    marginLeft: spacing.sm,
  },
  vendorName: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  vendorDesc: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.hudBorder,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkboxSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  checkmark: {
    color: colors.bgPrimary,
    fontWeight: 'bold',
    fontSize: 14,
  },
  expandedSection: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderTopWidth: 0,
    borderColor: colors.primary,
    borderBottomLeftRadius: 12,
    borderBottomRightRadius: 12,
    padding: spacing.md,
    marginTop: -12,
  },
  expandedLabel: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    letterSpacing: 1,
    marginBottom: spacing.xs,
  },
  expandedInput: {
    backgroundColor: colors.bgPrimary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    padding: spacing.md,
    color: colors.textPrimary,
    ...typography.bodyMedium,
  },
  expandedHint: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: spacing.xs,
    fontStyle: 'italic',
  },
  footer: {
    flexDirection: 'row',
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.hudBorder,
  },
  backButton: {
    flex: 0.4,
    marginRight: spacing.md,
  },
  continueButton: {
    flex: 0.6,
  },
});
