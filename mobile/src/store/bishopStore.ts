/**
 * PROVENIQ Ops - Bishop FSM State Store
 * Zustand store mirroring backend Bishop state
 */

import { create } from 'zustand';

export type BishopState = 
  | 'IDLE'
  | 'SCANNING'
  | 'ANALYZING_RISK'
  | 'CHECKING_FUNDS'
  | 'ORDER_QUEUED';

export interface BishopContext {
  location?: string;
  itemsDetected?: number;
  products?: ScannedProduct[];
  riskLevel?: string;
  liabilityFlags?: string[];
  orderTotal?: number;
  vendorName?: string;
  orderId?: string;
  eta?: string;
}

export interface ScannedProduct {
  id: string;
  name: string;
  barcode?: string;
  quantity: number;
  confidence: number;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

interface BishopStore {
  state: BishopState;
  message: string;
  context: BishopContext;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setState: (state: BishopState, message: string, context?: BishopContext) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
  
  // Scan operations
  beginScan: (location?: string) => void;
  addScannedProduct: (product: ScannedProduct) => void;
  completeScan: () => void;
}

const STATE_MESSAGES: Record<BishopState, string> = {
  IDLE: 'Awaiting directive.',
  SCANNING: 'Inventory capture in progress.',
  ANALYZING_RISK: 'Risk evaluation in progress.',
  CHECKING_FUNDS: 'Ledger verification in progress.',
  ORDER_QUEUED: 'Order queued. Awaiting confirmation.',
};

export const useBishopStore = create<BishopStore>((set, get) => ({
  state: 'IDLE',
  message: STATE_MESSAGES.IDLE,
  context: {},
  isLoading: false,
  error: null,
  
  setState: (state, message, context) => {
    set({
      state,
      message,
      context: context ?? get().context,
      error: null,
    });
  },
  
  setLoading: (isLoading) => set({ isLoading }),
  
  setError: (error) => set({ error, isLoading: false }),
  
  reset: () => set({
    state: 'IDLE',
    message: STATE_MESSAGES.IDLE,
    context: {},
    isLoading: false,
    error: null,
  }),
  
  beginScan: (location) => {
    set({
      state: 'SCANNING',
      message: STATE_MESSAGES.SCANNING,
      context: {
        location,
        products: [],
        itemsDetected: 0,
      },
      error: null,
    });
  },
  
  addScannedProduct: (product) => {
    const { context } = get();
    const existingProducts = context.products ?? [];
    const existingIndex = existingProducts.findIndex(p => p.id === product.id);
    
    let updatedProducts: ScannedProduct[];
    if (existingIndex >= 0) {
      updatedProducts = [...existingProducts];
      updatedProducts[existingIndex] = product;
    } else {
      updatedProducts = [...existingProducts, product];
    }
    
    set({
      context: {
        ...context,
        products: updatedProducts,
        itemsDetected: updatedProducts.length,
      },
    });
  },
  
  completeScan: () => {
    const { context } = get();
    const itemCount = context.products?.length ?? 0;
    
    if (itemCount > 0) {
      set({
        state: 'ANALYZING_RISK',
        message: `${itemCount} item(s) detected. Initiating risk evaluation.`,
      });
    } else {
      set({
        state: 'IDLE',
        message: 'Scan complete. No items detected.',
        context: {},
      });
    }
  },
}));
