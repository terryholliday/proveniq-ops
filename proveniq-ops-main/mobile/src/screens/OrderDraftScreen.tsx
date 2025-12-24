/**
 * PROVENIQ Ops - Order Draft Screen
 * Create and submit orders for below-par items
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  FlatList,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { colors, typography, spacing } from '../theme';
import { HudButton } from '../components';
import { vendorApi } from '../services';
import type { BelowParItem, Vendor } from '../services';

interface OrderDraftScreenProps {
  items: BelowParItem[];
  onBack: () => void;
  onOrderComplete: () => void;
}

interface OrderLineItem extends BelowParItem {
  orderQuantity: number;
  unitPrice: number;
  selected: boolean;
}

export function OrderDraftScreen({
  items,
  onBack,
  onOrderComplete,
}: OrderDraftScreenProps) {
  const [orderItems, setOrderItems] = useState<OrderLineItem[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [selectedVendor, setSelectedVendor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      // Load vendors
      const { data: vendorData } = await vendorApi.list();
      if (vendorData) {
        setVendors(vendorData);
        if (vendorData.length > 0) {
          setSelectedVendor(vendorData[0].id);
        }
      }

      // Initialize order items with shortage quantities
      const initialItems: OrderLineItem[] = items.map(item => ({
        ...item,
        orderQuantity: item.shortage,
        unitPrice: 0, // Would be fetched from vendor
        selected: true,
      }));
      setOrderItems(initialItems);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleItem = (productId: string) => {
    setOrderItems(prev =>
      prev.map(item =>
        item.product_id === productId
          ? { ...item, selected: !item.selected }
          : item
      )
    );
  };

  const updateQuantity = (productId: string, quantity: string) => {
    const qty = parseInt(quantity, 10) || 0;
    setOrderItems(prev =>
      prev.map(item =>
        item.product_id === productId
          ? { ...item, orderQuantity: qty }
          : item
      )
    );
  };

  const selectedItems = orderItems.filter(item => item.selected && item.orderQuantity > 0);
  const totalItems = selectedItems.reduce((sum, item) => sum + item.orderQuantity, 0);
  const totalLines = selectedItems.length;

  const handleSubmitOrder = async () => {
    if (selectedItems.length === 0) {
      Alert.alert('No Items', 'Please select at least one item to order');
      return;
    }

    if (!selectedVendor) {
      Alert.alert('No Vendor', 'Please select a vendor');
      return;
    }

    setSubmitting(true);
    try {
      // In production, would call the order API
      // For now, simulate success
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      Alert.alert(
        'Order Submitted',
        `Order for ${totalItems} units across ${totalLines} products has been queued.`,
        [
          {
            text: 'OK',
            onPress: onOrderComplete,
          },
        ]
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to submit order');
    } finally {
      setSubmitting(false);
    }
  };

  const renderItem = ({ item }: { item: OrderLineItem }) => (
    <View style={styles.itemCard}>
      <TouchableOpacity
        style={styles.checkbox}
        onPress={() => toggleItem(item.product_id)}
      >
        <Text style={styles.checkboxIcon}>
          {item.selected ? '☑️' : '⬜'}
        </Text>
      </TouchableOpacity>

      <View style={styles.itemInfo}>
        <Text style={styles.itemName}>{item.product_name}</Text>
        <Text style={styles.itemMeta}>
          Current: {item.current_quantity} | Par: {item.par_level} | Need: {item.shortage}
        </Text>
      </View>

      <View style={styles.quantityInput}>
        <TextInput
          style={[
            styles.input,
            !item.selected && styles.inputDisabled,
          ]}
          value={item.orderQuantity.toString()}
          onChangeText={(text) => updateQuantity(item.product_id, text)}
          keyboardType="numeric"
          editable={item.selected}
        />
      </View>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Preparing order...</Text>
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
        <Text style={styles.title}>Create Order</Text>
        <View style={{ width: 60 }} />
      </View>

      {/* Vendor Selector */}
      <View style={styles.vendorSection}>
        <Text style={styles.sectionTitle}>SELECT VENDOR</Text>
        <View style={styles.vendorList}>
          {vendors.map(vendor => (
            <TouchableOpacity
              key={vendor.id}
              style={[
                styles.vendorChip,
                selectedVendor === vendor.id && styles.vendorChipSelected,
              ]}
              onPress={() => setSelectedVendor(vendor.id)}
            >
              <Text style={[
                styles.vendorChipText,
                selectedVendor === vendor.id && styles.vendorChipTextSelected,
              ]}>
                {vendor.name}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Order Summary */}
      <View style={styles.summaryBar}>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryValue}>{totalLines}</Text>
          <Text style={styles.summaryLabel}>Products</Text>
        </View>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryValue}>{totalItems}</Text>
          <Text style={styles.summaryLabel}>Units</Text>
        </View>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryValue}>
            {selectedVendor ? vendors.find(v => v.id === selectedVendor)?.name || '-' : '-'}
          </Text>
          <Text style={styles.summaryLabel}>Vendor</Text>
        </View>
      </View>

      {/* Items List */}
      <FlatList
        data={orderItems}
        keyExtractor={(item) => item.product_id}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No items to order</Text>
          </View>
        }
      />

      {/* Submit Button */}
      <View style={styles.footer}>
        <HudButton
          title={submitting ? 'SUBMITTING...' : `SUBMIT ORDER (${totalItems} units)`}
          onPress={handleSubmitOrder}
          size="large"
          disabled={submitting || totalItems === 0}
        />
      </View>
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
  vendorSection: {
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  sectionTitle: {
    ...typography.labelSmall,
    color: colors.textMuted,
    marginBottom: spacing.sm,
    letterSpacing: 1,
  },
  vendorList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  vendorChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 20,
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    marginRight: spacing.sm,
    marginBottom: spacing.xs,
  },
  vendorChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  vendorChipText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  vendorChipTextSelected: {
    color: colors.bgPrimary,
    fontWeight: '600',
  },
  summaryBar: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.bgSecondary,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  summaryItem: {
    flex: 1,
    alignItems: 'center',
  },
  summaryValue: {
    ...typography.headingSmall,
    color: colors.textPrimary,
  },
  summaryLabel: {
    ...typography.labelSmall,
    color: colors.textMuted,
  },
  listContent: {
    padding: spacing.md,
  },
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgSecondary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 12,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  checkbox: {
    marginRight: spacing.sm,
  },
  checkboxIcon: {
    fontSize: 24,
  },
  itemInfo: {
    flex: 1,
  },
  itemName: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  itemMeta: {
    ...typography.labelSmall,
    color: colors.textMuted,
  },
  quantityInput: {
    width: 70,
  },
  input: {
    backgroundColor: colors.bgPrimary,
    borderWidth: 1,
    borderColor: colors.hudBorder,
    borderRadius: 8,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textAlign: 'center',
    color: colors.textPrimary,
    ...typography.bodyMedium,
  },
  inputDisabled: {
    opacity: 0.5,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  emptyText: {
    ...typography.bodyMedium,
    color: colors.textMuted,
  },
  footer: {
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.hudBorder,
  },
});
