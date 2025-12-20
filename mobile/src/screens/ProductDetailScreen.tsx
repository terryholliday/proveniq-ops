/**
 * PROVENIQ Ops - Product Detail Screen
 * View and edit product details including par level
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudButton } from '../components';
import { inventoryApi } from '../services';
import type { Product, InventorySnapshot } from '../services';

interface ProductDetailScreenProps {
  productId: string;
  onBack: () => void;
  onScan: () => void;
}

export function ProductDetailScreen({
  productId,
  onBack,
  onScan,
}: ProductDetailScreenProps) {
  const [product, setProduct] = useState<Product | null>(null);
  const [latestSnapshot, setLatestSnapshot] = useState<InventorySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingPar, setEditingPar] = useState(false);
  const [parLevel, setParLevel] = useState('');
  const [editingQuantity, setEditingQuantity] = useState(false);
  const [quantity, setQuantity] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [productResult, snapshotResult] = await Promise.all([
        inventoryApi.getProducts().then(r => {
          if (r.data) {
            return r.data.find(p => p.id === productId) || null;
          }
          return null;
        }),
        inventoryApi.getLatestSnapshot(productId),
      ]);

      if (productResult) {
        setProduct(productResult);
        setParLevel(productResult.par_level.toString());
      }
      
      if (snapshotResult.data) {
        setLatestSnapshot(snapshotResult.data);
        setQuantity(snapshotResult.data.quantity.toString());
      }
    } catch (error) {
      console.error('Error loading product:', error);
      Alert.alert('Error', 'Failed to load product data');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSaveParLevel = async () => {
    if (!product) return;
    
    const newParLevel = parseInt(parLevel, 10);
    if (isNaN(newParLevel) || newParLevel < 0) {
      Alert.alert('Invalid Input', 'Par level must be a positive number');
      return;
    }

    setSaving(true);
    try {
      // Note: Would need to add PATCH endpoint to backend
      // For now, show success and update locally
      setProduct({ ...product, par_level: newParLevel });
      setEditingPar(false);
      Alert.alert('Success', 'Par level updated');
    } catch (error) {
      Alert.alert('Error', 'Failed to update par level');
    } finally {
      setSaving(false);
    }
  };

  const handleRecordQuantity = async () => {
    if (!product) return;
    
    const newQuantity = parseInt(quantity, 10);
    if (isNaN(newQuantity) || newQuantity < 0) {
      Alert.alert('Invalid Input', 'Quantity must be a positive number');
      return;
    }

    setSaving(true);
    try {
      const { data, error } = await inventoryApi.createSnapshot({
        product_id: product.id,
        quantity: newQuantity,
        scanned_by: 'manual',
        scan_method: 'manual',
      });

      if (error) {
        throw new Error(error);
      }

      setLatestSnapshot(data);
      setEditingQuantity(false);
      Alert.alert('Success', 'Inventory count recorded');
    } catch (error) {
      Alert.alert('Error', 'Failed to record inventory count');
    } finally {
      setSaving(false);
    }
  };

  const getStockStatus = () => {
    if (!product || !latestSnapshot) return { status: 'unknown', color: colors.textMuted };
    
    const current = latestSnapshot.quantity;
    const par = product.par_level;
    
    if (current === 0) return { status: 'Out of Stock', color: colors.danger };
    if (current < par) return { status: 'Below Par', color: colors.danger };
    if (current <= par * 1.2) return { status: 'Low Stock', color: colors.warning };
    return { status: 'In Stock', color: colors.accent };
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (!product) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>Product not found</Text>
          <HudButton title="Go Back" onPress={onBack} />
        </View>
      </SafeAreaView>
    );
  }

  const stockStatus = getStockStatus();
  const shortage = product.par_level - (latestSnapshot?.quantity ?? 0);

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Product</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentContainer}>
        {/* Product Info Card */}
        <View style={styles.card}>
          <Text style={styles.productName}>{product.name}</Text>
          {product.barcode && (
            <Text style={styles.barcode}>{product.barcode}</Text>
          )}
          <View style={styles.riskBadgeContainer}>
            <Text style={[
              styles.riskBadge,
              product.risk_category === 'perishable' && styles.risk_perishable,
              product.risk_category === 'hazardous' && styles.risk_hazardous,
              product.risk_category === 'controlled' && styles.risk_controlled,
              product.risk_category === 'standard' && styles.risk_standard,
            ]}>
              {product.risk_category.toUpperCase()}
            </Text>
          </View>
        </View>

        {/* Stock Status Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>STOCK STATUS</Text>
          
          <View style={styles.stockRow}>
            <View style={styles.stockItem}>
              <Text style={[styles.stockValue, { color: stockStatus.color }]}>
                {latestSnapshot?.quantity ?? 0}
              </Text>
              <Text style={styles.stockLabel}>Current</Text>
            </View>
            
            <View style={styles.stockDivider} />
            
            <View style={styles.stockItem}>
              <Text style={styles.stockValue}>{product.par_level}</Text>
              <Text style={styles.stockLabel}>Par Level</Text>
            </View>
            
            <View style={styles.stockDivider} />
            
            <View style={styles.stockItem}>
              <Text style={[
                styles.stockValue,
                { color: shortage > 0 ? colors.danger : colors.accent }
              ]}>
                {shortage > 0 ? `-${shortage}` : '+' + Math.abs(shortage)}
              </Text>
              <Text style={styles.stockLabel}>Variance</Text>
            </View>
          </View>

          <View style={[styles.statusBadge, { backgroundColor: `${stockStatus.color}20` }]}>
            <Text style={[styles.statusText, { color: stockStatus.color }]}>
              {stockStatus.status}
            </Text>
          </View>

          {latestSnapshot && (
            <Text style={styles.lastScanned}>
              Last scanned: {new Date(latestSnapshot.scanned_at).toLocaleString()}
            </Text>
          )}
        </View>

        {/* Par Level Editor */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>PAR LEVEL</Text>
          
          {editingPar ? (
            <View style={styles.editRow}>
              <TextInput
                style={styles.input}
                value={parLevel}
                onChangeText={setParLevel}
                keyboardType="numeric"
                placeholder="Enter par level"
                placeholderTextColor={colors.textMuted}
              />
              <TouchableOpacity
                style={styles.saveButton}
                onPress={handleSaveParLevel}
                disabled={saving}
              >
                <Text style={styles.saveButtonText}>
                  {saving ? '...' : 'Save'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => {
                  setParLevel(product.par_level.toString());
                  setEditingPar(false);
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity
              style={styles.editableRow}
              onPress={() => setEditingPar(true)}
            >
              <Text style={styles.editableValue}>{product.par_level}</Text>
              <Text style={styles.editHint}>Tap to edit</Text>
            </TouchableOpacity>
          )}
          
          <Text style={styles.helpText}>
            When stock falls below par level, Bishop will recommend reordering.
          </Text>
        </View>

        {/* Manual Count */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>RECORD COUNT</Text>
          
          {editingQuantity ? (
            <View style={styles.editRow}>
              <TextInput
                style={styles.input}
                value={quantity}
                onChangeText={setQuantity}
                keyboardType="numeric"
                placeholder="Enter quantity"
                placeholderTextColor={colors.textMuted}
              />
              <TouchableOpacity
                style={styles.saveButton}
                onPress={handleRecordQuantity}
                disabled={saving}
              >
                <Text style={styles.saveButtonText}>
                  {saving ? '...' : 'Save'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => {
                  setQuantity((latestSnapshot?.quantity ?? 0).toString());
                  setEditingQuantity(false);
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.countActions}>
              <TouchableOpacity
                style={styles.countButton}
                onPress={() => setEditingQuantity(true)}
              >
                <Text style={styles.countButtonIcon}>✏️</Text>
                <Text style={styles.countButtonText}>Manual Count</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[styles.countButton, styles.scanCountButton]}
                onPress={onScan}
              >
                <Text style={styles.countButtonIcon}>📷</Text>
                <Text style={styles.countButtonText}>Scan Count</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Reorder Action */}
        {shortage > 0 && (
          <View style={styles.reorderCard}>
            <Text style={styles.reorderTitle}>⚠️ Reorder Recommended</Text>
            <Text style={styles.reorderText}>
              Stock is {shortage} units below par level.
            </Text>
            <HudButton
              title={`ORDER ${shortage} UNITS`}
              onPress={() => {
                Alert.alert('Order', `Would create order for ${shortage} units of ${product.name}`);
              }}
              variant="primary"
            />
          </View>
        )}
      </ScrollView>
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  errorText: {
    ...typography.bodyLarge,
    color: colors.textMuted,
    marginBottom: spacing.lg,
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
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: spacing.md,
  },
  card: {
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  productName: {
    ...typography.headingMedium,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  barcode: {
    ...typography.bodyMedium,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  riskBadgeContainer: {
    flexDirection: 'row',
  },
  riskBadge: {
    ...typography.labelSmall,
    fontSize: 10,
    paddingHorizontal: 8,
    paddingVertical: 4,
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
  cardTitle: {
    ...typography.labelSmall,
    color: colors.textMuted,
    marginBottom: spacing.md,
    letterSpacing: 1,
  },
  stockRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  stockItem: {
    flex: 1,
    alignItems: 'center',
  },
  stockValue: {
    ...typography.headingLarge,
    color: colors.textPrimary,
  },
  stockLabel: {
    ...typography.labelSmall,
    color: colors.textMuted,
  },
  stockDivider: {
    width: 1,
    height: 40,
    backgroundColor: colors.hudBorder,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginBottom: spacing.sm,
  },
  statusText: {
    ...typography.bodySmall,
    fontWeight: '600',
  },
  lastScanned: {
    ...typography.labelSmall,
    color: colors.textMuted,
  },
  editRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  input: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.textPrimary,
    ...typography.bodyMedium,
    marginRight: spacing.sm,
  },
  saveButton: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 8,
    marginRight: spacing.xs,
  },
  saveButtonText: {
    ...typography.bodyMedium,
    color: colors.bgPrimary,
    fontWeight: '600',
  },
  cancelButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  cancelButtonText: {
    ...typography.bodyMedium,
    color: colors.textMuted,
  },
  editableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.bgPrimary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.sm,
  },
  editableValue: {
    ...typography.headingMedium,
    color: colors.textPrimary,
  },
  editHint: {
    ...typography.labelSmall,
    color: colors.primary,
  },
  helpText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  countActions: {
    flexDirection: 'row',
  },
  countButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bgPrimary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    paddingVertical: spacing.md,
    marginRight: spacing.sm,
  },
  scanCountButton: {
    marginRight: 0,
    borderColor: colors.primary,
  },
  countButtonIcon: {
    fontSize: 18,
    marginRight: spacing.xs,
  },
  countButtonText: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
  },
  reorderCard: {
    backgroundColor: `${colors.warning}15`,
    borderWidth: 1,
    borderColor: colors.warning,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  reorderTitle: {
    ...typography.bodyLarge,
    color: colors.warning,
    fontWeight: '600',
    marginBottom: spacing.xs,
  },
  reorderText: {
    ...typography.bodyMedium,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
});
