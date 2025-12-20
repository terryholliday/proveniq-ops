/**
 * PROVENIQ Ops - Team Invite Screen
 * Invite team members with role assignment
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
import { colors, typography, spacing } from '../../theme';
import { HudButton } from '../../components';

interface TeamInviteScreenProps {
  onContinue: (invites: TeamInvite[]) => void;
  onSkip: () => void;
  onBack: () => void;
}

export type UserRole = 'MANAGER' | 'OPERATOR' | 'VIEWER';

export interface TeamInvite {
  email: string;
  role: UserRole;
}

interface RoleOption {
  value: UserRole;
  label: string;
  description: string;
}

const ROLES: RoleOption[] = [
  { value: 'MANAGER', label: 'Manager', description: 'Approve orders, manage team' },
  { value: 'OPERATOR', label: 'Operator', description: 'Scan inventory, create orders' },
  { value: 'VIEWER', label: 'Viewer', description: 'View reports only' },
];

export function TeamInviteScreen({ onContinue, onSkip, onBack }: TeamInviteScreenProps) {
  const [invites, setInvites] = useState<TeamInvite[]>([
    { email: '', role: 'OPERATOR' },
  ]);

  const addInvite = () => {
    setInvites([...invites, { email: '', role: 'OPERATOR' }]);
  };

  const removeInvite = (index: number) => {
    if (invites.length > 1) {
      setInvites(invites.filter((_, i) => i !== index));
    }
  };

  const updateInvite = (index: number, field: keyof TeamInvite, value: string) => {
    const updated = [...invites];
    updated[index] = { ...updated[index], [field]: value };
    setInvites(updated);
  };

  const handleContinue = () => {
    const validInvites = invites.filter(inv => inv.email.trim());
    
    // Validate emails
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const invalidEmails = validInvites.filter(inv => !emailRegex.test(inv.email));
    
    if (invalidEmails.length > 0) {
      Alert.alert('Invalid Email', 'Please enter valid email addresses');
      return;
    }

    onContinue(validInvites);
  };

  const hasValidInvites = invites.some(inv => inv.email.trim());

  return (
    <SafeAreaView style={styles.container}>
      {/* Progress */}
      <View style={styles.progress}>
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={styles.progressDot} />
        <View style={[styles.progressDot, styles.progressDotActive]} />
        <View style={styles.progressDot} />
      </View>

      <ScrollView 
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.step}>STEP 5 OF 6</Text>
          <Text style={styles.title}>Invite your team</Text>
          <Text style={styles.subtitle}>
            Add team members who will use the app. You can invite more later.
          </Text>
        </View>

        {/* Role Legend */}
        <View style={styles.roleLegend}>
          {ROLES.map((role) => (
            <View key={role.value} style={styles.roleItem}>
              <Text style={styles.roleLabel}>{role.label}</Text>
              <Text style={styles.roleDesc}>{role.description}</Text>
            </View>
          ))}
        </View>

        {/* Invite List */}
        <View style={styles.inviteList}>
          {invites.map((invite, index) => (
            <View key={index} style={styles.inviteCard}>
              <View style={styles.inviteHeader}>
                <Text style={styles.inviteNumber}>Team Member {index + 1}</Text>
                {invites.length > 1 && (
                  <TouchableOpacity onPress={() => removeInvite(index)}>
                    <Text style={styles.removeButton}>Remove</Text>
                  </TouchableOpacity>
                )}
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>EMAIL</Text>
                <TextInput
                  style={styles.input}
                  value={invite.email}
                  onChangeText={(text) => updateInvite(index, 'email', text)}
                  placeholder="team@example.com"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>ROLE</Text>
                <View style={styles.roleSelector}>
                  {ROLES.map((role) => (
                    <TouchableOpacity
                      key={role.value}
                      style={[
                        styles.roleOption,
                        invite.role === role.value && styles.roleOptionSelected,
                      ]}
                      onPress={() => updateInvite(index, 'role', role.value)}
                    >
                      <Text style={[
                        styles.roleOptionText,
                        invite.role === role.value && styles.roleOptionTextSelected,
                      ]}>
                        {role.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            </View>
          ))}

          <TouchableOpacity style={styles.addButton} onPress={addInvite}>
            <Text style={styles.addButtonText}>+ Add Another Team Member</Text>
          </TouchableOpacity>
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
        {hasValidInvites ? (
          <HudButton
            title="SEND INVITES"
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
  roleLegend: {
    backgroundColor: colors.bgSecondary,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  roleItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  roleLabel: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  roleDesc: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  inviteList: {
    marginTop: spacing.sm,
  },
  inviteCard: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  inviteHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  inviteNumber: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    letterSpacing: 1,
  },
  removeButton: {
    ...typography.bodySmall,
    color: colors.primary,
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
    backgroundColor: colors.bgPrimary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    padding: spacing.md,
    color: colors.textPrimary,
    ...typography.bodyMedium,
  },
  roleSelector: {
    flexDirection: 'row',
  },
  roleOption: {
    flex: 1,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  roleOptionSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  roleOptionText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  roleOptionTextSelected: {
    color: colors.bgPrimary,
  },
  addButton: {
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  addButtonText: {
    ...typography.bodyMedium,
    color: colors.primary,
    fontWeight: '600',
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
