/**
 * PROVENIQ Ops - Location Picker Screen
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  FlatList,
  TouchableOpacity,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudContainer } from '../components';
import { useAuthStore, Location } from '../store/authStore';

interface LocationPickerScreenProps {
  onLocationSelected: () => void;
}

const LOCATION_ICONS: Record<string, string> = {
  RESTAURANT: '🍽️',
  RETAIL: '🏪',
  WAREHOUSE: '📦',
  KITCHEN: '👨‍🍳',
};

export function LocationPickerScreen({ onLocationSelected }: LocationPickerScreenProps) {
  const { locations, currentLocation, setCurrentLocation, user, logout } = useAuthStore();

  const handleSelectLocation = (location: Location) => {
    setCurrentLocation(location);
    onLocationSelected();
  };

  const renderLocation = ({ item }: { item: Location }) => {
    const isSelected = currentLocation?.id === item.id;
    
    return (
      <TouchableOpacity
        style={[styles.locationCard, isSelected && styles.locationCardSelected]}
        onPress={() => handleSelectLocation(item)}
        activeOpacity={0.7}
      >
        <View style={styles.locationIcon}>
          <Text style={styles.iconText}>{LOCATION_ICONS[item.type] || '📍'}</Text>
        </View>
        <View style={styles.locationInfo}>
          <Text style={styles.locationName}>{item.name}</Text>
          <Text style={styles.locationType}>{item.type}</Text>
          {item.address && (
            <Text style={styles.locationAddress}>{item.address}</Text>
          )}
        </View>
        {isSelected && (
          <View style={styles.selectedBadge}>
            <Text style={styles.selectedText}>✓</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.logo}>PROVENIQ OPS</Text>
        <Text style={styles.greeting}>Welcome, {user?.displayName}</Text>
      </View>

      {/* Location Selection */}
      <HudContainer style={styles.content}>
        <Text style={styles.title}>SELECT LOCATION</Text>
        <Text style={styles.subtitle}>
          Choose where you're operating today
        </Text>

        <FlatList
          data={locations}
          renderItem={renderLocation}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
        />
      </HudContainer>

      {/* Footer */}
      <View style={styles.footer}>
        <TouchableOpacity onPress={logout} style={styles.logoutButton}>
          <Text style={styles.logoutText}>LOGOUT</Text>
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
    alignItems: 'center',
    paddingVertical: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  logo: {
    ...typography.labelMedium,
    color: colors.primary,
    letterSpacing: 4,
  },
  greeting: {
    ...typography.bodyMedium,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  content: {
    flex: 1,
    margin: spacing.md,
    padding: spacing.lg,
  },
  title: {
    ...typography.headingMedium,
    color: colors.textPrimary,
    textAlign: 'center',
    letterSpacing: 2,
  },
  subtitle: {
    ...typography.bodySmall,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.xs,
    marginBottom: spacing.lg,
  },
  list: {
    paddingVertical: spacing.sm,
  },
  locationCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  locationCardSelected: {
    borderColor: colors.primary,
    backgroundColor: `${colors.primary}15`,
  },
  locationIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.bgPrimary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  iconText: {
    fontSize: 24,
  },
  locationInfo: {
    flex: 1,
  },
  locationName: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  locationType: {
    ...typography.labelSmall,
    color: colors.primary,
    marginTop: 2,
  },
  locationAddress: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: 2,
  },
  selectedBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  selectedText: {
    color: colors.bgPrimary,
    fontWeight: 'bold',
    fontSize: 16,
  },
  footer: {
    alignItems: 'center',
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.hudBorder,
  },
  logoutButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  logoutText: {
    ...typography.labelSmall,
    color: colors.textMuted,
    letterSpacing: 2,
  },
});
