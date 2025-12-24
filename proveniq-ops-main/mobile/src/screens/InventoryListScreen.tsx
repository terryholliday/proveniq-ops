/**
 * PROVENIQ Ops - Inventory List Screen
 * View all products with current quantities and par levels
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  FlatList,
  TouchableOpacity,
  TextInput,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudButton } from '../components';
import {
  getProducts,
  getProductsBelowPar,
  getLatestSnapshot,
  Product,
  BelowParItem,
} from '../services/inventoryApi';

interface InventoryListScreenProps {
  onBack: () => void;
  onScanItem: () => void;
  onViewProduct: (productId: string) => void;
  onCreateOrder: (items: BelowParItem[]) => void;
}

type FilterMode = 'all' | 'below_par' | 'perishable';

interface ProductWithQuantity extends Product {
  current_quantity: number;
  shortage: number;
}

export function InventoryListScreen({
  onBack,
  onScanItem,
  onViewProduct,
  onCreateOrder,
}: InventoryListScreenProps) {
  const [products, setProducts] = useState<ProductWithQuantity[]>([]);
  const [belowParItems, setBelowParItems] = useState<BelowParItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [productsData, belowParData] = await Promise.all([
        getProducts(),
        getProductsBelowPar(),
      ]);

      // Enrich products with quantity data
      const enrichedProducts: ProductWithQuantity[] = await Promise.all(
        productsData.map(async (product) => {
          const belowPar = belowParData.find(b => b.product_id === product.id);
          if (belowPar) {
            return {
              ...product,
              current_quantity: belowPar.current_quantity,
              shortage: belowPar.shortage,
            };
          }
          
          // Get latest snapshot for products not below par
          const snapshot = await getLatestSnapshot(product.id);
          return {
            ...product,
            current_quantity: snapshot?.quantity ?? 0,
            shortage: 0,
          };
        })
      );

      setProducts(enrichedProducts);
      setBelowParItems(belowParData);
    } catch (error) {
      console.error('Error loading inventory:', error);
      Alert.alert('Error', 'Failed to load inventory data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  const filteredProducts = products.filter(product => {
    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      if (!product.name.toLowerCase().includes(query) &&
          !product.barcode?.toLowerCase().includes(query)) {
        return false;
      }
    }

    // Apply category filter
    switch (filterMode) {
      case 'below_par':
        return product.shortage > 0;
      case 'perishable':
        return product.risk_category === 'perishable';
      default:
        return true;
    }
  });

  const getQuantityColor = (product: ProductWithQuantity) => {
    if (product.shortage > 0) return colors.danger;
    if (product.current_quantity <= product.par_level * 1.2) return colors.warning;
    return colors.accent; // Green for healthy stock
  };

  const renderProduct = ({ item }: { item: ProductWithQuantity }) => (
    <TouchableOpacity
      style={styles.productCard}
      onPress={() => onViewProduct(item.id)}
      activeOpacity={0.7}
    >
      <View style={styles.productInfo}>
        <Text style={styles.productName}>{item.name}</Text>
        {item.barcode && (
          <Text style={styles.productBarcode}>{item.barcode}</Text>
        )}
        <View style={styles.productMeta}>
          <Text style={[styles.riskBadge, styles[`risk_${item.risk_category}`]]}>
            {item.risk_category.toUpperCase()}
          </Text>
        </View>
      </View>
      
      <View style={styles.quantitySection}>
        <Text style={[styles.quantityValue, { color: getQuantityColor(item) }]}>
          {item.current_quantity}
        </Text>
        <Text style={styles.parLevel}>Par: {item.par_level}</Text>
        {item.shortage > 0 && (
          <Text style={styles.shortage}>-{item.shortage}</Text>
        )}
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Loading inventory...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Inventory</Text>
        <TouchableOpacity onPress={onScanItem} style={styles.scanButton}>
          <Text style={styles.scanText}>📷 Scan</Text>
        </TouchableOpacity>
      </View>

      {/* Search */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search by name or barcode..."
          placeholderTextColor={colors.textMuted}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterTabs}>
        {(['all', 'below_par', 'perishable'] as FilterMode[]).map((mode) => (
          <TouchableOpacity
            key={mode}
            style={[
              styles.filterTab,
              filterMode === mode && styles.filterTabActive,
            ]}
            onPress={() => setFilterMode(mode)}
          >
            <Text style={[
              styles.filterTabText,
              filterMode === mode && styles.filterTabTextActive,
            ]}>
              {mode === 'all' ? 'All' : mode === 'below_par' ? '⚠️ Low Stock' : '🥬 Perishable'}
            </Text>
            {mode === 'below_par' && belowParItems.length > 0 && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{belowParItems.length}</Text>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {/* Stats Bar */}
      <View style={styles.statsBar}>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{products.length}</Text>
          <Text style={styles.statLabel}>Products</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statValue, { color: colors.danger }]}>
            {belowParItems.length}
          </Text>
          <Text style={styles.statLabel}>Below Par</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statValue, { color: colors.warning }]}>
            {products.filter(p => p.risk_category === 'perishable').length}
          </Text>
          <Text style={styles.statLabel}>Perishable</Text>
        </View>
      </View>

      {/* Product List */}
      <FlatList
        data={filteredProducts}
        keyExtractor={(item) => item.id}
        renderItem={renderProduct}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>📦</Text>
            <Text style={styles.emptyText}>No products found</Text>
            <Text style={styles.emptySubtext}>
              {searchQuery ? 'Try a different search' : 'Scan items to add inventory'}
            </Text>
          </View>
        }
      />

      {/* Order Button (when items are below par) */}
      {belowParItems.length > 0 && filterMode === 'below_par' && (
        <View style={styles.orderFooter}>
          <HudButton
            title={`CREATE ORDER (${belowParItems.length} items)`}
            onPress={() => onCreateOrder(belowParItems)}
            size="large"
          />
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    ...typography.bodyMedium,
    color: colors.textMuted,
    marginTop: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  backButton: {
    padding: spacing.sm,
  },
  backText: {
    ...typography.bodyMedium,
    color: colors.primary,
  },
  title: {
    ...typography.headingMedium,
    color: colors.textPrimary,
  },
  scanButton: {
    padding: spacing.sm,
  },
  scanText: {
    ...typography.bodyMedium,
    color: colors.primary,
  },
  searchContainer: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  searchInput: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.textPrimary,
    ...typography.bodyMedium,
  },
  filterTabs: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  filterTab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginRight: spacing.sm,
    borderRadius: 20,
    backgroundColor: colors.bgSecondary,
  },
  filterTabActive: {
    backgroundColor: colors.primary,
  },
  filterTabText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  filterTabTextActive: {
    color: colors.bgPrimary,
    fontWeight: '600',
  },
  badge: {
    backgroundColor: colors.danger,
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginLeft: spacing.xs,
  },
  badgeText: {
    ...typography.labelSmall,
    color: colors.textPrimary,
    fontSize: 10,
  },
  statsBar: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  stat: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    ...typography.headingMedium,
    color: colors.textPrimary,
  },
  statLabel: {
    ...typography.labelSmall,
    color: colors.textMuted,
  },
  listContent: {
    padding: spacing.md,
  },
  productCard: {
    flexDirection: 'row',
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  productInfo: {
    flex: 1,
  },
  productName: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    fontWeight: '600',
    marginBottom: 2,
  },
  productBarcode: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  productMeta: {
    flexDirection: 'row',
  },
  riskBadge: {
    ...typography.labelSmall,
    fontSize: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    overflow: 'hidden',
  },
  risk_standard: {
    backgroundColor: colors.bgSecondary,
    color: colors.textMuted,
  },
  risk_perishable: {
    backgroundColor: `${colors.warning}30`,
    color: colors.warning,
  },
  risk_hazardous: {
    backgroundColor: `${colors.danger}30`,
    color: colors.danger,
  },
  risk_controlled: {
    backgroundColor: `${colors.primary}30`,
    color: colors.primary,
  },
  quantitySection: {
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  quantityValue: {
    ...typography.headingMedium,
    fontWeight: '700',
  },
  parLevel: {
    ...typography.labelSmall,
    color: colors.textMuted,
  },
  shortage: {
    ...typography.bodySmall,
    color: colors.danger,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: spacing.md,
  },
  emptyText: {
    ...typography.bodyLarge,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  emptySubtext: {
    ...typography.bodyMedium,
    color: colors.textMuted,
  },
  orderFooter: {
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.hudBorder,
  },
});
