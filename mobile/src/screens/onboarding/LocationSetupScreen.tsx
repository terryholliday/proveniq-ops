/**
 * PROVENIQ Ops - Location Setup Screen
 * Create first location with address
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
import { BusinessType } from '../../store/authStore';

interface LocationSetupScreenProps {
  businessType: BusinessType;
  onContinue: (data: LocationData) => void;
  onBack: () => void;
}

export interface LocationData {
  name: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
}

const TYPE_LABELS: Record<BusinessType, string> = {
  RESTAURANT: 'kitchen or restaurant',
  RETAIL: 'store',
  WAREHOUSE: 'warehouse',
};

export function LocationSetupScreen({ businessType, onContinue, onBack }: LocationSetupScreenProps) {
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zipCode, setZipCode] = useState('');

  const typeLabel = TYPE_LABELS[businessType] || 'location';

  const handleContinue = () => {
    if (!name.trim()) {
      Alert.alert('Required', `Please enter a name for your ${typeLabel}`);
      return;
    }

    onContinue({
      name: name.trim(),
      address: address.trim(),
      city: city.trim(),
      state: state.trim(),
      zipCode: zipCode.trim(),
    });
  };

  const isValid = name.trim();

  return (
    <SafeAreaView style={styles.container}>
      {/* Progress */}
      <View style={styles.progress}>
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={[styles.progressDot, styles.progressDotActive]} />
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
            <Text style={styles.step}>STEP 3 OF 6</Text>
            <Text style={styles.title}>Set up your first {typeLabel}</Text>
            <Text style={styles.subtitle}>
              You can add more locations later in Settings
            </Text>
          </View>

          {/* Form */}
          <View style={styles.form}>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>LOCATION NAME *</Text>
              <TextInput
                style={styles.input}
                value={name}
                onChangeText={setName}
                placeholder={`e.g., Main ${typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1)}`}
                placeholderTextColor={colors.textMuted}
                autoCapitalize="words"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>STREET ADDRESS</Text>
              <TextInput
                style={styles.input}
                value={address}
                onChangeText={setAddress}
                placeholder="123 Main Street"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="words"
              />
            </View>

            <View style={styles.row}>
              <View style={[styles.inputGroup, { flex: 2 }]}>
                <Text style={styles.label}>CITY</Text>
                <TextInput
                  style={styles.input}
                  value={city}
                  onChangeText={setCity}
                  placeholder="City"
                  placeholderTextColor={colors.textMuted}
                  autoCapitalize="words"
                />
              </View>

              <View style={[styles.inputGroup, { flex: 1 }]}>
                <Text style={styles.label}>STATE</Text>
                <TextInput
                  style={styles.input}
                  value={state}
                  onChangeText={setState}
                  placeholder="ST"
                  placeholderTextColor={colors.textMuted}
                  autoCapitalize="characters"
                  maxLength={2}
                />
              </View>

              <View style={[styles.inputGroup, { flex: 1.2 }]}>
                <Text style={styles.label}>ZIP</Text>
                <TextInput
                  style={styles.input}
                  value={zipCode}
                  onChangeText={setZipCode}
                  placeholder="12345"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="number-pad"
                  maxLength={5}
                />
              </View>
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
  row: {
    flexDirection: 'row',
  },
  inputGroup: {
    marginBottom: spacing.md,
    marginRight: spacing.sm,
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
