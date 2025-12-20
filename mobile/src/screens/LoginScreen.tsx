/**
 * PROVENIQ Ops - Login Screen
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

interface LoginScreenProps {
  onLoginSuccess: () => void;
}

export function LoginScreen({ onLoginSuccess }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login, isLoading } = useAuthStore();

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Error', 'Please enter email and password');
      return;
    }

    const success = await login(email, password);
    if (success) {
      onLoginSuccess();
    } else {
      Alert.alert('Error', 'Login failed. Please try again.');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.content}
      >
        {/* Logo */}
        <View style={styles.header}>
          <Text style={styles.logo}>PROVENIQ</Text>
          <Text style={styles.productName}>OPS</Text>
          <Text style={styles.tagline}>Restaurant & Retail Operations</Text>
        </View>

        {/* Login Form */}
        <HudContainer style={styles.form}>
          <Text style={styles.formTitle}>OPERATOR LOGIN</Text>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>EMAIL</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="operator@restaurant.com"
              placeholderTextColor={colors.textMuted}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>PASSWORD</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
            />
          </View>

          <HudButton
            title={isLoading ? 'AUTHENTICATING...' : 'LOGIN'}
            onPress={handleLogin}
            disabled={isLoading}
            size="large"
            style={styles.loginButton}
          />
        </HudContainer>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Bishop Inventory Intelligence
          </Text>
          <Text style={styles.version}>v1.0.0</Text>
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
    ...typography.labelLarge,
    color: colors.primary,
    letterSpacing: 6,
    fontSize: 28,
  },
  productName: {
    ...typography.headingLarge,
    color: colors.textPrimary,
    letterSpacing: 8,
    marginTop: spacing.xs,
  },
  tagline: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  form: {
    padding: spacing.lg,
  },
  formTitle: {
    ...typography.labelMedium,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
    letterSpacing: 2,
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
  loginButton: {
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
  version: {
    ...typography.mono,
    color: colors.textMuted,
    fontSize: 10,
    marginTop: spacing.xs,
  },
});
