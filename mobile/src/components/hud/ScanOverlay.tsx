/**
 * PROVENIQ Ops - Scan Overlay
 * HUD overlay for camera view with bounding boxes and scan info
 */

import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { colors, typography, spacing } from '../../theme';
import { ScannedProduct } from '../../store';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

interface ScanOverlayProps {
  products: ScannedProduct[];
  isScanning: boolean;
}

export function ScanOverlay({ products, isScanning }: ScanOverlayProps) {
  return (
    <View style={styles.container} pointerEvents="none">
      {/* Scanline effect */}
      {isScanning && <View style={styles.scanline} />}
      
      {/* Corner brackets */}
      <View style={styles.cornerTL} />
      <View style={styles.cornerTR} />
      <View style={styles.cornerBL} />
      <View style={styles.cornerBR} />
      
      {/* Center reticle */}
      <View style={styles.reticle}>
        <View style={styles.reticleH} />
        <View style={styles.reticleV} />
      </View>
      
      {/* Bounding boxes for detected items */}
      {products.map((product) => (
        product.boundingBox && (
          <BoundingBox 
            key={product.id} 
            product={product} 
          />
        )
      ))}
      
      {/* Item count badge */}
      {products.length > 0 && (
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{products.length}</Text>
          <Text style={styles.countLabel}>ITEMS</Text>
        </View>
      )}
    </View>
  );
}

interface BoundingBoxProps {
  product: ScannedProduct;
}

function BoundingBox({ product }: BoundingBoxProps) {
  const { boundingBox, name, confidence } = product;
  if (!boundingBox) return null;
  
  const confidenceColor = 
    confidence >= 0.8 ? colors.confidenceHigh :
    confidence >= 0.5 ? colors.confidenceMedium :
    colors.confidenceLow;
  
  return (
    <View style={[
      styles.boundingBox,
      {
        left: boundingBox.x,
        top: boundingBox.y,
        width: boundingBox.width,
        height: boundingBox.height,
        borderColor: confidenceColor,
      }
    ]}>
      <View style={[styles.boxLabel, { backgroundColor: confidenceColor }]}>
        <Text style={styles.boxLabelText} numberOfLines={1}>
          {name}
        </Text>
        <Text style={styles.boxConfidence}>
          {Math.round(confidence * 100)}%
        </Text>
      </View>
      
      {/* Corner accents */}
      <View style={[styles.boxCornerTL, { borderColor: confidenceColor }]} />
      <View style={[styles.boxCornerTR, { borderColor: confidenceColor }]} />
      <View style={[styles.boxCornerBL, { borderColor: confidenceColor }]} />
      <View style={[styles.boxCornerBR, { borderColor: confidenceColor }]} />
    </View>
  );
}

const CORNER_SIZE = 24;
const BOX_CORNER_SIZE = 8;

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
  },
  scanline: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 2,
    backgroundColor: colors.primary,
    opacity: 0.6,
    top: '50%',
  },
  cornerTL: {
    position: 'absolute',
    top: spacing.xl,
    left: spacing.xl,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderTopWidth: 2,
    borderLeftWidth: 2,
    borderColor: colors.primary,
  },
  cornerTR: {
    position: 'absolute',
    top: spacing.xl,
    right: spacing.xl,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderTopWidth: 2,
    borderRightWidth: 2,
    borderColor: colors.primary,
  },
  cornerBL: {
    position: 'absolute',
    bottom: spacing.xl,
    left: spacing.xl,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    borderColor: colors.primary,
  },
  cornerBR: {
    position: 'absolute',
    bottom: spacing.xl,
    right: spacing.xl,
    width: CORNER_SIZE,
    height: CORNER_SIZE,
    borderBottomWidth: 2,
    borderRightWidth: 2,
    borderColor: colors.primary,
  },
  reticle: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    width: 40,
    height: 40,
    marginLeft: -20,
    marginTop: -20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  reticleH: {
    position: 'absolute',
    width: 40,
    height: 1,
    backgroundColor: colors.primary,
    opacity: 0.5,
  },
  reticleV: {
    position: 'absolute',
    width: 1,
    height: 40,
    backgroundColor: colors.primary,
    opacity: 0.5,
  },
  boundingBox: {
    position: 'absolute',
    borderWidth: 1,
    borderStyle: 'dashed',
  },
  boxLabel: {
    position: 'absolute',
    top: -20,
    left: -1,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    gap: spacing.xs,
  },
  boxLabelText: {
    ...typography.labelSmall,
    color: colors.textInverse,
    maxWidth: 80,
  },
  boxConfidence: {
    ...typography.monoSmall,
    color: colors.textInverse,
  },
  boxCornerTL: {
    position: 'absolute',
    top: -1,
    left: -1,
    width: BOX_CORNER_SIZE,
    height: BOX_CORNER_SIZE,
    borderTopWidth: 2,
    borderLeftWidth: 2,
  },
  boxCornerTR: {
    position: 'absolute',
    top: -1,
    right: -1,
    width: BOX_CORNER_SIZE,
    height: BOX_CORNER_SIZE,
    borderTopWidth: 2,
    borderRightWidth: 2,
  },
  boxCornerBL: {
    position: 'absolute',
    bottom: -1,
    left: -1,
    width: BOX_CORNER_SIZE,
    height: BOX_CORNER_SIZE,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
  },
  boxCornerBR: {
    position: 'absolute',
    bottom: -1,
    right: -1,
    width: BOX_CORNER_SIZE,
    height: BOX_CORNER_SIZE,
    borderBottomWidth: 2,
    borderRightWidth: 2,
  },
  countBadge: {
    position: 'absolute',
    top: spacing.xl,
    alignSelf: 'center',
    backgroundColor: colors.bgOverlay,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  countText: {
    ...typography.displayMedium,
    color: colors.primary,
  },
  countLabel: {
    ...typography.labelSmall,
    color: colors.textSecondary,
  },
});
