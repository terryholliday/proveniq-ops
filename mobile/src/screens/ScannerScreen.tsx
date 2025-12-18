/**
 * PROVENIQ Ops - Scanner Screen
 * Synthetic Eye AR inventory scanning interface
 */

import React, { useState, useEffect, useRef } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  SafeAreaView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { CameraView, CameraType, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import { colors, typography, spacing } from '../theme';
import { useBishopStore } from '../store';
import { 
  HudContainer, 
  HudButton, 
  BishopStatus, 
  ScanOverlay 
} from '../components';
import { inventoryApi } from '../services';

export function ScannerScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [facing, setFacing] = useState<CameraType>('back');
  const cameraRef = useRef<CameraView>(null);
  
  const { 
    state, 
    context,
    beginScan, 
    addScannedProduct, 
    completeScan,
    reset,
  } = useBishopStore();
  
  const isScanning = state === 'SCANNING';
  const products = context.products ?? [];

  useEffect(() => {
    if (!permission?.granted) {
      requestPermission();
    }
  }, []);

  const handleBarCodeScanned = async (result: BarcodeScanningResult) => {
    if (!isScanning) return;
    
    const { data: barcode } = result;
    
    // Check if already scanned
    const alreadyScanned = products.some(p => p.barcode === barcode);
    if (alreadyScanned) return;
    
    // Look up product by barcode
    const { data: product, error } = await inventoryApi.getProductByBarcode(barcode);
    
    if (product) {
      addScannedProduct({
        id: product.id,
        name: product.name,
        barcode: product.barcode ?? undefined,
        quantity: 1,
        confidence: 0.95,
        boundingBox: {
          x: result.bounds?.origin.x ?? 100,
          y: result.bounds?.origin.y ?? 100,
          width: result.bounds?.size.width ?? 150,
          height: result.bounds?.size.height ?? 80,
        },
      });
    } else {
      // Unknown barcode - could prompt to add new product
      addScannedProduct({
        id: `unknown-${Date.now()}`,
        name: `Unknown (${barcode.slice(0, 8)}...)`,
        barcode,
        quantity: 1,
        confidence: 0.5,
      });
    }
  };

  const handleStartScan = () => {
    beginScan('Warehouse A');
  };

  const handleCompleteScan = () => {
    completeScan();
  };

  const handleReset = () => {
    reset();
  };

  // Permission not granted
  if (!permission?.granted) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.permissionContainer}>
          <HudContainer>
            <Text style={styles.permissionTitle}>CAMERA ACCESS REQUIRED</Text>
            <Text style={styles.permissionText}>
              Synthetic Eye requires camera access for inventory scanning.
            </Text>
            <HudButton 
              title="GRANT ACCESS" 
              onPress={requestPermission}
              style={{ marginTop: spacing.md }}
            />
          </HudContainer>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.container}>
      {/* Camera View */}
      <CameraView
        ref={cameraRef}
        style={styles.camera}
        facing={facing}
        barcodeScannerSettings={{
          barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128', 'code39', 'qr'],
        }}
        onBarcodeScanned={isScanning ? handleBarCodeScanned : undefined}
      >
        {/* HUD Overlay */}
        <ScanOverlay products={products} isScanning={isScanning} />
        
        {/* Top Bar */}
        <SafeAreaView style={styles.topBar}>
          <View style={styles.topBarContent}>
            <Text style={styles.logo}>PROVENIQ</Text>
            <Text style={styles.subtitle}>SYNTHETIC EYE</Text>
          </View>
        </SafeAreaView>
        
        {/* Bottom Controls */}
        <SafeAreaView style={styles.bottomBar}>
          {/* Bishop Status */}
          <BishopStatus />
          
          {/* Scan Controls */}
          <View style={styles.controls}>
            {state === 'IDLE' && (
              <HudButton 
                title="BEGIN SCAN" 
                onPress={handleStartScan}
                size="large"
              />
            )}
            
            {isScanning && (
              <View style={styles.scanControls}>
                <HudButton 
                  title="CANCEL" 
                  onPress={handleReset}
                  variant="ghost"
                />
                <HudButton 
                  title={`COMPLETE (${products.length})`}
                  onPress={handleCompleteScan}
                  variant="primary"
                  size="large"
                  disabled={products.length === 0}
                />
              </View>
            )}
            
            {(state === 'ANALYZING_RISK' || state === 'CHECKING_FUNDS' || state === 'ORDER_QUEUED') && (
              <HudButton 
                title="RESET" 
                onPress={handleReset}
                variant="secondary"
              />
            )}
          </View>
          
          {/* Scanned Items List */}
          {products.length > 0 && (
            <HudContainer variant="overlay" style={styles.itemsList}>
              <Text style={styles.itemsTitle}>DETECTED ITEMS</Text>
              {products.slice(0, 3).map((product) => (
                <View key={product.id} style={styles.itemRow}>
                  <Text style={styles.itemName} numberOfLines={1}>
                    {product.name}
                  </Text>
                  <Text style={[
                    styles.itemConfidence,
                    { color: product.confidence >= 0.8 
                      ? colors.confidenceHigh 
                      : colors.confidenceMedium 
                    }
                  ]}>
                    {Math.round(product.confidence * 100)}%
                  </Text>
                </View>
              ))}
              {products.length > 3 && (
                <Text style={styles.moreItems}>
                  +{products.length - 3} more items
                </Text>
              )}
            </HudContainer>
          )}
        </SafeAreaView>
      </CameraView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bgPrimary,
  },
  camera: {
    flex: 1,
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  permissionTitle: {
    ...typography.headingLarge,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  permissionText: {
    ...typography.bodyMedium,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  topBar: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
  topBarContent: {
    alignItems: 'center',
    paddingTop: spacing.md,
  },
  logo: {
    ...typography.labelLarge,
    color: colors.primary,
    letterSpacing: 4,
  },
  subtitle: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    letterSpacing: 2,
  },
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: spacing.md,
    gap: spacing.md,
  },
  controls: {
    alignItems: 'center',
  },
  scanControls: {
    flexDirection: 'row',
    gap: spacing.md,
    alignItems: 'center',
  },
  itemsList: {
    maxHeight: 150,
  },
  itemsTitle: {
    ...typography.labelSmall,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  itemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudBorder,
  },
  itemName: {
    ...typography.bodyMedium,
    color: colors.textPrimary,
    flex: 1,
    marginRight: spacing.sm,
  },
  itemConfidence: {
    ...typography.mono,
  },
  moreItems: {
    ...typography.bodySmall,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});
