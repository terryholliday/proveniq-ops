/**
 * PROVENIQ Ops - API Service Layer
 * Backend integration for Bishop FSM and operations
 */

const API_BASE_URL = __DEV__ 
  ? 'http://10.0.2.2:8000/api/v1'  // Android emulator
  : 'https://api.proveniq.com/api/v1';

interface ApiResponse<T> {
  data: T | null;
  error: string | null;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        data: null,
        error: errorData.detail || `Request failed: ${response.status}`,
      };
    }
    
    const data = await response.json();
    return { data, error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : 'Network error',
    };
  }
}

// Bishop FSM endpoints
export const bishopApi = {
  getStatus: () => 
    request<BishopResponse>('/bishop/status'),
  
  reset: () => 
    request<BishopResponse>('/bishop/reset', { method: 'POST' }),
  
  beginScan: (location?: string) => 
    request<BishopResponse>(
      `/bishop/scan/begin${location ? `?location=${encodeURIComponent(location)}` : ''}`,
      { method: 'POST' }
    ),
  
  completeScan: (itemsDetected: number, products: any[]) =>
    request<BishopResponse>(
      `/bishop/scan/complete?items_detected=${itemsDetected}`,
      { 
        method: 'POST',
        body: JSON.stringify(products),
      }
    ),
  
  checkRisk: (productId: string, quantity: number, expiryDate?: string) =>
    request<BishopResponse>('/bishop/risk/check', {
      method: 'POST',
      body: JSON.stringify({
        product_id: productId,
        quantity,
        expiry_date: expiryDate,
      }),
    }),
  
  checkFunds: (orderTotal: number) =>
    request<BishopResponse>(
      `/bishop/funds/check?order_total=${orderTotal}`,
      { method: 'POST' }
    ),
  
  queueOrder: (vendorId: string, vendorName: string, eta?: number) =>
    request<BishopResponse>(
      `/bishop/order/queue?vendor_id=${vendorId}&vendor_name=${encodeURIComponent(vendorName)}${eta ? `&estimated_delivery_hours=${eta}` : ''}`,
      { method: 'POST' }
    ),
  
  getTransitionLog: () =>
    request<BishopStateTransition[]>('/bishop/log'),
};

// Inventory endpoints
export const inventoryApi = {
  getProducts: (riskCategory?: string) =>
    request<Product[]>(
      `/inventory/products${riskCategory ? `?risk_category=${riskCategory}` : ''}`
    ),
  
  getProductByBarcode: (barcode: string) =>
    request<Product>(`/inventory/products/barcode/${encodeURIComponent(barcode)}`),
  
  createSnapshot: (snapshot: InventorySnapshotCreate) =>
    request<InventorySnapshot>('/inventory/snapshots', {
      method: 'POST',
      body: JSON.stringify(snapshot),
    }),
  
  getLatestSnapshot: (productId: string) =>
    request<InventorySnapshot>(`/inventory/snapshots/latest/${productId}`),
  
  getBelowPar: () =>
    request<BelowParItem[]>('/inventory/below-par'),
};

// Vendor endpoints
export const vendorApi = {
  list: () => request<Vendor[]>('/vendors/'),
  
  queryAvailability: (productId: string, quantity: number, preferPrice = false) =>
    request<ProductAvailability>(
      `/vendors/query/availability?product_id=${productId}&quantity_needed=${quantity}&prefer_price=${preferPrice}`,
      { method: 'POST' }
    ),
  
  comparePrices: (productId: string, quantity: number) =>
    request<ProductAvailability>(
      `/vendors/compare-prices?product_id=${productId}&quantity_needed=${quantity}`,
      { method: 'POST' }
    ),
};

// Type definitions
export interface BishopResponse {
  state: string;
  message: string;
  context: Record<string, any> | null;
  timestamp: string;
}

export interface BishopStateTransition {
  previous_state: string | null;
  current_state: string;
  trigger_event: string;
  context_data: Record<string, any> | null;
  output_message: string;
}

export interface Product {
  id: string;
  name: string;
  barcode: string | null;
  par_level: number;
  risk_category: string;
  created_at: string;
  updated_at: string;
}

export interface InventorySnapshotCreate {
  product_id: string;
  quantity: number;
  confidence_score?: number;
  scanned_by?: string;
  scan_method?: 'manual' | 'barcode' | 'silhouette' | 'volumetric';
  location_tag?: string;
}

export interface InventorySnapshot extends InventorySnapshotCreate {
  id: string;
  scanned_at: string;
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

export interface Vendor {
  id: string;
  name: string;
  api_endpoint: string | null;
  priority_level: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductAvailability {
  product_id: string;
  vendor_results: VendorQueryResult[];
  recommended_vendor_id: string | null;
  recommendation_rationale: string;
  queried_at: string;
}

export interface VendorQueryResult {
  vendor_id: string;
  vendor_name: string;
  in_stock: boolean;
  available_quantity: number;
  unit_price: number;
  estimated_delivery_hours: number | null;
  queried_at: string;
}
