/**
 * PROVENIQ Ops - Home/Dashboard Screen
 * Main hub after onboarding
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudContainer } from '../components';
import { useAuthStore } from '../store/authStore';
import { useBishopStore } from '../store/bishopStore';

interface HomeScreenProps {
  onNavigate: (screen: string) => void;
}

export function HomeScreen({ onNavigate }: HomeScreenProps) {
  const { currentLocation, businessType, user } = useAuthStore();
  const { state: bishopState } = useBishopStore();

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.greeting}>{getGreeting()}, {user?.displayName}</Text>
          <Text style={styles.location}>📍 {currentLocation?.name || 'No location'}</Text>
        </View>
        <TouchableOpacity 
          style={styles.settingsButton}
          onPress={() => onNavigate('settings')}
        >
          <Text style={styles.settingsIcon}>⚙️</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.scrollContent}>
        {/* Bishop Status Card */}
        <HudContainer style={styles.statusCard}>
          <View style={styles.statusHeader}>
            <Text style={styles.statusTitle}>BISHOP STATUS</Text>
            <View style={[styles.statusBadge, bishopState === 'IDLE' && styles.statusIdle]}>
              <Text style={styles.statusBadgeText}>{bishopState}</Text>
            </View>
          </View>
          <Text style={styles.statusMessage}>
            {bishopState === 'IDLE' ? 'Ready for inventory scan' : 'Processing...'}
          </Text>
        </HudContainer>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>QUICK ACTIONS</Text>
        <View style={styles.actionsGrid}>
          <TouchableOpacity 
            style={styles.actionCard}
            onPress={() => onNavigate('scan')}
          >
            <Text style={styles.actionIcon}>📷</Text>
            <Text style={styles.actionTitle}>Scan Inventory</Text>
            <Text style={styles.actionSubtitle}>Start Bishop scan</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.actionCard}
            onPress={() => onNavigate('inventory')}
          >
            <Text style={styles.actionIcon}>📦</Text>
            <Text style={styles.actionTitle}>View Inventory</Text>
            <Text style={styles.actionSubtitle}>Check stock levels</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.actionCard}
            onPress={() => onNavigate('orders')}
          >
            <Text style={styles.actionIcon}>🛒</Text>
            <Text style={styles.actionTitle}>Orders</Text>
            <Text style={styles.actionSubtitle}>Pending & history</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.actionCard}
            onPress={() => onNavigate('alerts')}
          >
            <Text style={styles.actionIcon}>⚠️</Text>
            <Text style={styles.actionTitle}>Alerts</Text>
            <Text style={styles.actionSubtitle}>Below par items</Text>
          </TouchableOpacity>
        </View>

        {/* Stats Overview */}
        <Text style={styles.sectionTitle}>TODAY'S OVERVIEW</Text>
        <HudContainer style={styles.statsCard}>
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>--</Text>
              <Text style={styles.statLabel}>Items Scanned</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statValue}>--</Text>
              <Text style={styles.statLabel}>Orders Queued</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text style={styles.statValue}>--</Text>
              <Text style={styles.statLabel}>Below Par</Text>
            </View>
          </View>
        </HudContainer>

        {/* Recent Activity */}
        <Text style={styles.sectionTitle}>RECENT ACTIVITY</Text>
        <HudContainer style={styles.activityCard}>
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📋</Text>
            <Text style={styles.emptyText}>No recent activity</Text>
            <Text style={styles.emptySubtext}>Start a scan to see activity here</Text>
          </View>
        </HudContainer>
      </ScrollView>

      {/* Bottom Nav */}
      <View style={styles.bottomNav}>
        <TouchableOpacity 
          style={[styles.navItem, styles.navItemActive]}
          onPress={() => onNavigate('home')}
        >
          <Text style={styles.navIcon}>🏠</Text>
          <Text style={[styles.navLabel, styles.navLabelActive]}>Home</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => onNavigate('scan')}
        >
          <Text style={styles.navIcon}>📷</Text>
          <Text style={styles.navLabel}>Scan</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => onNavigate('inventory')}
        >
          <Text style={styles.navIcon}>📦</Text>
          <Text style={styles.navLabel}>Inventory</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => onNavigate('orders')}
        >
          <Text style={styles.navIcon}>🛒</Text>
          <Text style={styles.navLabel}>Orders</Text>
        </TouchableOpacity>
      </View>
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
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  location: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: 2,
  },
  settingsButton: {
    padding: spacing.sm,
  },
  settingsIcon: {
    fontSize: 24,
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  statusCard: {
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  statusHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  statusTitle: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    letterSpacing: 2,
  },
  statusBadge: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: 4,
  },
  statusIdle: {
    backgroundColor: '#22c55e',
  },
  statusBadgeText: {
    ...typography.labelSmall,
    color: colors.bgPrimary,
    fontWeight: '600',
  },
  statusMessage: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
  },
  sectionTitle: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    letterSpacing: 2,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  actionCard: {
    width: '48%',
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    padding: spacing.md,
  },
  actionIcon: {
    fontSize: 28,
    marginBottom: spacing.xs,
  },
  actionTitle: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  actionSubtitle: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  statsCard: {
    padding: spacing.md,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    ...typography.headingLarge,
    color: colors.textPrimary,
  },
  statLabel: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  statDivider: {
    width: 1,
    height: 40,
    backgroundColor: colors.hudBorder,
  },
  activityCard: {
    padding: spacing.lg,
  },
  emptyState: {
    alignItems: 'center',
  },
  emptyIcon: {
    fontSize: 32,
    marginBottom: spacing.sm,
  },
  emptyText: {
    ...typography.bodyMedium,
    color: colors.textSecondary,
  },
  emptySubtext: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  bottomNav: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: colors.hudBorder,
    backgroundColor: colors.bgSecondary,
  },
  navItem: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  navItemActive: {
    borderTopWidth: 2,
    borderTopColor: colors.primary,
  },
  navIcon: {
    fontSize: 20,
    marginBottom: 2,
  },
  navLabel: {
    ...typography.labelSmall,
    color: colors.textMuted,
    fontSize: 10,
  },
  navLabelActive: {
    color: colors.primary,
  },
});
