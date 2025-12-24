/**
 * PROVENIQ Ops - Settings Screen
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
  Alert,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudContainer, HudButton } from '../components';
import { useAuthStore } from '../store/authStore';
import { getApiUrl, setRuntimeApiUrl } from '../config';

interface SettingsScreenProps {
  onBack: () => void;
  onOpenFAQ?: () => void;
}

export function SettingsScreen({ onBack, onOpenFAQ }: SettingsScreenProps) {
  const { user, currentLocation, logout } = useAuthStore();
  const [apiUrl, setApiUrl] = useState(getApiUrl());
  const [isSaving, setIsSaving] = useState(false);

  const handleSaveApiUrl = () => {
    if (!apiUrl.startsWith('http')) {
      Alert.alert('Invalid URL', 'API URL must start with http:// or https://');
      return;
    }
    
    setIsSaving(true);
    setRuntimeApiUrl(apiUrl);
    
    setTimeout(() => {
      setIsSaving(false);
      Alert.alert('Saved', 'API URL updated. Restart the app to apply changes.');
    }, 500);
  };

  const handleLogout = () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Logout', 
          style: 'destructive',
          onPress: logout,
        },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack} style={styles.backButton}>
          <Text style={styles.backText}>← BACK</Text>
        </TouchableOpacity>
        <Text style={styles.title}>SETTINGS</Text>
        <View style={styles.placeholder} />
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.scrollContent}>
        {/* User Info */}
        <HudContainer style={styles.section}>
          <Text style={styles.sectionTitle}>OPERATOR</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Email</Text>
            <Text style={styles.infoValue}>{user?.email || 'Not logged in'}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Role</Text>
            <Text style={styles.infoValue}>{user?.role?.toUpperCase() || '-'}</Text>
          </View>
        </HudContainer>

        {/* Current Location */}
        <HudContainer style={styles.section}>
          <Text style={styles.sectionTitle}>CURRENT LOCATION</Text>
          {currentLocation ? (
            <>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Name</Text>
                <Text style={styles.infoValue}>{currentLocation.name}</Text>
              </View>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Type</Text>
                <Text style={styles.infoValue}>{currentLocation.type}</Text>
              </View>
              {currentLocation.address && (
                <View style={styles.infoRow}>
                  <Text style={styles.infoLabel}>Address</Text>
                  <Text style={styles.infoValue}>{currentLocation.address}</Text>
                </View>
              )}
            </>
          ) : (
            <Text style={styles.noLocation}>No location selected</Text>
          )}
        </HudContainer>

        {/* API Configuration */}
        <HudContainer style={styles.section}>
          <Text style={styles.sectionTitle}>API CONFIGURATION</Text>
          <Text style={styles.hint}>
            Set the backend server URL. Use your machine's IP for local development.
          </Text>
          <TextInput
            style={styles.input}
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="http://192.168.1.100:8000"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <HudButton
            title={isSaving ? 'SAVING...' : 'SAVE API URL'}
            onPress={handleSaveApiUrl}
            disabled={isSaving}
            variant="secondary"
            style={styles.saveButton}
          />
        </HudContainer>

        {/* Help & Support */}
        <HudContainer style={styles.section}>
          <Text style={styles.sectionTitle}>HELP & SUPPORT</Text>
          {onOpenFAQ && (
            <TouchableOpacity style={styles.menuItem} onPress={onOpenFAQ}>
              <Text style={styles.menuItemText}>❓ FAQ</Text>
              <Text style={styles.menuItemArrow}>→</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuItemText}>📖 User Guide</Text>
            <Text style={styles.menuItemArrow}>→</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.menuItem}>
            <Text style={styles.menuItemText}>📧 Contact Support</Text>
            <Text style={styles.menuItemArrow}>→</Text>
          </TouchableOpacity>
        </HudContainer>

        {/* App Info */}
        <HudContainer style={styles.section}>
          <Text style={styles.sectionTitle}>ABOUT</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>App</Text>
            <Text style={styles.infoValue}>PROVENIQ Ops</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Version</Text>
            <Text style={styles.infoValue}>1.0.0</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Support</Text>
            <Text style={styles.infoValue}>support@proveniq.io</Text>
          </View>
        </HudContainer>

        {/* Logout */}
        <HudButton
          title="LOGOUT"
          onPress={handleLogout}
          variant="ghost"
          style={styles.logoutButton}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  backButton: {
    padding: spacing.sm,
  },
  backText: {
    ...typography.labelSmall,
    color: colors.primary,
    letterSpacing: 1,
  },
  title: {
    ...typography.labelMedium,
    color: colors.textPrimary,
    letterSpacing: 2,
  },
  placeholder: {
    width: 60,
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  section: {
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    ...typography.labelSmall,
    color: colors.primary,
    letterSpacing: 2,
    marginBottom: spacing.md,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  infoLabel: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  infoValue: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
  },
  noLocation: {
    ...typography.bodyMedium,
    color: colors.textMuted,
    fontStyle: 'italic',
  },
  hint: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 4,
    padding: spacing.md,
    color: colors.textPrimary,
    ...typography.mono,
    fontSize: 14,
  },
  saveButton: {
    marginTop: spacing.md,
  },
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  menuItemText: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
  },
  menuItemArrow: {
    ...typography.bodyMedium,
    color: colors.textMuted,
  },
  logoutButton: {
    marginTop: spacing.lg,
  },
});
