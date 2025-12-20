/**
 * PROVENIQ Ops - Inventory API Service
 * Connects mobile app to backend inventory endpoints
 */

import { API_URL } from '../config';

// Types
export interface Product {
  id: string;
  name: string;
  barcode: string | null;
  par_level: number;
  risk_category: 'standard' | 'perishable' | 'hazardous' | 'controlled';
  created_at: string;
  updated_at: string;
}

export interface ProductCreate {
  name: string;
  barcode?: string;
  par_level?: number;
  risk_category?: 'standard' | 'perishable' | 'hazardous' | 'controlled';
}

export interface InventorySnapshot {
  id: string;
  product_id: string;
  quantity: number;
  confidence_score: number | null;
  scanned_by: string;
  scan_method: 'manual' | 'barcode' | 'silhouette' | 'volumetric';
  location_tag: string | null;
  scanned_at: string;
}

export interface SnapshotCreate {
  product_id: string;
  quantity: number;
  confidence_score?: number;
  scanned_by?: string;
  scan_method?: 'manual' | 'barcode' | 'silhouette' | 'volumetric';
  location_tag?: string;
}

export interface BelowParItem {
  product_id: string;
  product_name: string;
  barcode: string | null;
  par_level: number;
  current_quantity: number;
  shortage: number;
  last_scanned: string | null;
}

export interface OrderItem {
  product_id: string;
  quantity: number;
  unit_price_micros: number;
  vendor_product_id?: string;
}

export interface OrderCreate {
  vendor_id: string;
  items: OrderItem[];
}

// API Functions

/**
 * Get all products
 */
export async function getProducts(riskCategory?: string): Promise<Product[]> {
  const params = riskCategory ? `?risk_category=${riskCategory}` : '';
  const response = await fetch(`${API_URL}/inventory/products${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch products: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Get product by ID
 */
export async function getProduct(productId: string): Promise<Product> {
  const response = await fetch(`${API_URL}/inventory/products/${productId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch product: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Get product by barcode (for scanner)
 */
export async function getProductByBarcode(barcode: string): Promise<Product | null> {
  try {
    const response = await fetch(`${API_URL}/inventory/products/barcode/${barcode}`);
    
    if (response.status === 404) {
      return null; // Product not found
    }
    
    if (!response.ok) {
      throw new Error(`Failed to fetch product: ${response.status}`);
    }
    
    return response.json();
  } catch (error) {
    console.error('Error fetching product by barcode:', error);
    return null;
  }
}

/**
 * Create a new product
 */
export async function createProduct(product: ProductCreate): Promise<Product> {
  const response = await fetch(`${API_URL}/inventory/products`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(product),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to create product: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Update product par level
 */
export async function updateParLevel(productId: string, parLevel: number): Promise<Product> {
  const response = await fetch(`${API_URL}/inventory/products/${productId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ par_level: parLevel }),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to update par level: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Record an inventory snapshot (scan result)
 */
export async function createSnapshot(snapshot: SnapshotCreate): Promise<InventorySnapshot> {
  const response = await fetch(`${API_URL}/inventory/snapshots`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(snapshot),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to create snapshot: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Get latest snapshot for a product
 */
export async function getLatestSnapshot(productId: string): Promise<InventorySnapshot | null> {
  try {
    const response = await fetch(`${API_URL}/inventory/snapshots/latest/${productId}`);
    
    if (response.status === 404) {
      return null;
    }
    
    if (!response.ok) {
      throw new Error(`Failed to fetch snapshot: ${response.status}`);
    }
    
    return response.json();
  } catch (error) {
    console.error('Error fetching latest snapshot:', error);
    return null;
  }
}

/**
 * Get all snapshots with optional filters
 */
export async function getSnapshots(
  productId?: string,
  scannedBy?: string,
  limit: number = 100
): Promise<InventorySnapshot[]> {
  const params = new URLSearchParams();
  if (productId) params.append('product_id', productId);
  if (scannedBy) params.append('scanned_by', scannedBy);
  params.append('limit', limit.toString());
  
  const response = await fetch(`${API_URL}/inventory/snapshots?${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch snapshots: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Get products below par level (for reorder recommendations)
 */
export async function getProductsBelowPar(): Promise<BelowParItem[]> {
  const response = await fetch(`${API_URL}/inventory/below-par`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch below-par products: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Create an order
 */
export async function createOrder(order: OrderCreate): Promise<any> {
  const response = await fetch(`${API_URL}/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(order),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to create order: ${response.status}`);
  }
  
  return response.json();
}

/**
 * Get vendors
 */
export async function getVendors(): Promise<any[]> {
  const response = await fetch(`${API_URL}/vendors`);
  
  if (!response.ok) {
    throw new Error(`Failed to fetch vendors: ${response.status}`);
  }
  
  return response.json();
}
