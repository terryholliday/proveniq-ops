/**
 * PROVENIQ Ops - Business Setup Screen
 * Create first location after selecting business type
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudContainer, HudButton } from '../components';
import { useAuthStore } from '../store/authStore';

interface BusinessSetupScreenProps {
  onSetupComplete: () => void;
}

const BUSINESS_LABELS: Record<string, string> = {
  RESTAURANT: 'Restaurant / Kitchen',
  RETAIL: 'Store',
  WAREHOUSE: 'Warehouse',
};

export function BusinessSetupScreen({ onSetupComplete }: BusinessSetupScreenProps) {
  const { businessType, addLocation, completeOnboarding } = useAuthStore();
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const typeLabel = businessType ? BUSINESS_LABELS[businessType] : 'Location';

  const handleSubmit = async () => {
    if (!name.trim()) {
      Alert.alert('Required', `Please enter a name for your ${typeLabel.toLowerCase()}`);
      return;
    }

    setIsSubmitting(true);

    try {
      // Add the location
      addLocation({
        name: name.trim(),
        address: address.trim() || undefined,
        type: businessType!,
      });

      // Mark onboarding complete
      completeOnboarding();

      onSetupComplete();
    } catch (error) {
      Alert.alert('Error', 'Failed to create location. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.content}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>PROVENIQ OPS</Text>
        </View>

        {/* Form */}
        <HudContainer style={styles.form}>
          <Text style={styles.title}>Set Up Your First {typeLabel}</Text>
          <Text style={styles.subtitle}>
            You can add more locations later in Settings
          </Text>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>{typeLabel.toUpperCase()} NAME *</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder={`e.g., Main ${typeLabel}`}
              placeholderTextColor={colors.textMuted}
              autoCapitalize="words"
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>ADDRESS (OPTIONAL)</Text>
            <TextInput
              style={styles.input}
              value={address}
              onChangeText={setAddress}
              placeholder="123 Main Street, City, ST"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="words"
            />
          </View>

          <HudButton
            title={isSubmitting ? 'CREATING...' : 'COMPLETE SETUP'}
            onPress={handleSubmit}
            disabled={isSubmitting || !name.trim()}
            size="large"
            style={styles.submitButton}
          />
        </HudContainer>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Bishop will be optimized for {businessType?.toLowerCase()} operations
          </Text>
        </View>
      </KeyboardAvoidingView>
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
    padding: spacing.lg,
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  logo: {
    ...typography.labelMedium,
    color: colors.primary,
    letterSpacing: 4,
  },
  form: {
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
  inputGroup: {
    marginBottom: spacing.md,
  },
  label: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
    letterSpacing: 1,
  },
  input: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 4,
    padding: spacing.md,
    color: colors.textPrimary,
    ...typography.bodyMedium,
  },
  submitButton: {
    marginTop: spacing.lg,
  },
  footer: {
    alignItems: 'center',
    marginTop: spacing.xl,
  },
  footerText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
});
