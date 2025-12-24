/**
 * PROVENIQ Ops - Business Info Screen
 * Collect business name and owner details
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
  ScrollView,
  Alert,
} from 'react-native';
import { colors, typography, spacing } from '../../theme';
import { HudButton } from '../../components';

interface BusinessInfoScreenProps {
  onContinue: (data: BusinessInfoData) => void;
  onBack: () => void;
}

export interface BusinessInfoData {
  businessName: string;
  ownerName: string;
  phone: string;
  email?: string;
}

export function BusinessInfoScreen({ onContinue, onBack }: BusinessInfoScreenProps) {
  const [businessName, setBusinessName] = useState('');
  const [ownerName, setOwnerName] = useState('');
  const [phone, setPhone] = useState('');

  const handleContinue = () => {
    if (!businessName.trim()) {
      Alert.alert('Required', 'Please enter your business name');
      return;
    }
    if (!ownerName.trim()) {
      Alert.alert('Required', 'Please enter your name');
      return;
    }

    onContinue({
      businessName: businessName.trim(),
      ownerName: ownerName.trim(),
      phone: phone.trim(),
    });
  };

  const isValid = businessName.trim() && ownerName.trim();

  return (
    <SafeAreaView style={styles.container}>
      {/* Progress */}
      <View style={styles.progress}>
        <View style={styles.progressDot} />
        <View style={[styles.progressDot, styles.progressDotActive]} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
      </View>

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView 
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.step}>STEP 1 OF 6</Text>
            <Text style={styles.title}>Tell us about your business</Text>
            <Text style={styles.subtitle}>
              This information helps us set up your account
            </Text>
          </View>

          {/* Form */}
          <View style={styles.form}>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>BUSINESS NAME *</Text>
              <TextInput
                style={styles.input}
                value={businessName}
                onChangeText={setBusinessName}
                placeholder="e.g., Joe's Diner"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="words"
                autoCorrect={false}
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>YOUR NAME *</Text>
              <TextInput
                style={styles.input}
                value={ownerName}
                onChangeText={setOwnerName}
                placeholder="e.g., Joe Smith"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="words"
                autoCorrect={false}
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>PHONE NUMBER (OPTIONAL)</Text>
              <TextInput
                style={styles.input}
                value={phone}
                onChangeText={setPhone}
                placeholder="(555) 123-4567"
                placeholderTextColor={colors.textMuted}
                keyboardType="phone-pad"
              />
            </View>
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
          <HudButton
            title="CONTINUE"
            onPress={handleContinue}
            disabled={!isValid}
            style={styles.continueButton}
          />
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
  keyboardView: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
  },
  header: {
    marginBottom: spacing.xl,
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
  form: {
    marginBottom: spacing.md,
  },
  inputGroup: {
    marginBottom: spacing.md,
  },
  label: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    letterSpacing: 1,
  },
  input: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    padding: spacing.md,
    color: colors.textPrimary,
    ...typography.bodyMedium,
    fontSize: 16,
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
