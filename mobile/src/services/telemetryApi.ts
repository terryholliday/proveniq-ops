/**
 * PROVENIQ Ops - Telemetry API Service
 * P3: Mobile → Backend telemetry event ingestion
 * 
 * Connects scanner events to the Data Gravity moat
 */

import { apiClient } from './apiClient';

// Event types matching backend EventType enum
export type TelemetryEventType = 
  | 'TEMPERATURE_READING'
  | 'HUMIDITY_READING'
  | 'DOOR_OPEN'
  | 'DOOR_CLOSE'
  | 'POWER_LOSS'
  | 'POWER_RESTORED'
  | 'INVENTORY_SCAN'
  | 'BARCODE_SCAN'
  | 'MANUAL_COUNT'
  | 'ORDER_CREATED'
  | 'ORDER_SUBMITTED'
  | 'ORDER_DELIVERED'
  | 'DELIVERY_RECEIVED'
  | 'BISHOP_STATE_CHANGE'
  | 'BISHOP_RECOMMENDATION'
  | 'BISHOP_RECOMMENDATION_ACCEPTED'
  | 'BISHOP_RECOMMENDATION_REJECTED'
  | 'ANOMALY_DETECTED'
  | 'ANOMALY_RESOLVED'
  | 'WASTE_RECORDED'
  | 'SHRINKAGE_DETECTED'
  | 'ATTESTATION_ISSUED'
  | 'ATTESTATION_VERIFIED';

export interface TelemetryEvent {
  event_type: TelemetryEventType;
  wallet_id?: string;
  correlation_id?: string;
  idempotency_key?: string;
  payload: Record<string, unknown>;
  source_app?: string;
  version?: string;
}

export interface TelemetryEventResponse {
  id: string;
  event_type: string;
  timestamp: string;
  wallet_id?: string;
  correlation_id?: string;
  payload: Record<string, unknown>;
  payload_hash: string;
  ledger_synced: boolean;
  created_at: string;
}

export interface SensorReading {
  sensor_id: string;
  sensor_type: 'temperature' | 'humidity' | 'door' | 'power';
  location_id?: string;
  asset_id?: string;
  value: number;
  unit: string;
  wallet_id?: string;
}

export interface BishopRecommendation {
  org_id: string;
  recommendation_type: string;
  recommendation_text: string;
  context?: Record<string, unknown>;
  confidence_score: number;
  related_product_ids?: string[];
  related_order_ids?: string[];
}

export interface BishopAcceptance {
  recommendation_event_id: string;
  accepted: boolean;
  user_id?: string;
  rejection_reason?: string;
  notes?: string;
}

export interface ShrinkageRecord {
  org_id: string;
  product_id: string;
  expected_quantity: number;
  actual_quantity: number;
  location_id?: string;
  notes?: string;
}

/**
 * Telemetry API for Data Gravity
 */
export const telemetryApi = {
  /**
   * Ingest a telemetry event
   */
  async ingestEvent(event: TelemetryEvent): Promise<{ data?: TelemetryEventResponse; error?: string }> {
    try {
      const response = await apiClient.post<TelemetryEventResponse>('/telemetry/events', event);
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to ingest event' };
    }
  },

  /**
   * Record a barcode scan event
   */
  async recordBarcodeScan(
    barcode: string,
    productId: string,
    productName: string,
    quantity: number,
    confidence: number,
    locationTag?: string,
    walletId?: string,
  ): Promise<{ data?: TelemetryEventResponse; error?: string }> {
    return this.ingestEvent({
      event_type: 'BARCODE_SCAN',
      wallet_id: walletId,
      payload: {
        barcode,
        product_id: productId,
        product_name: productName,
        quantity,
        confidence,
        location_tag: locationTag,
        scan_method: 'barcode',
        device_type: 'mobile',
      },
      idempotency_key: `barcode:${barcode}:${Date.now()}`,
    });
  },

  /**
   * Record an inventory scan session
   */
  async recordInventoryScan(
    locationTag: string,
    productCount: number,
    products: Array<{ id: string; name: string; quantity: number; confidence: number }>,
    walletId?: string,
  ): Promise<{ data?: TelemetryEventResponse; error?: string }> {
    return this.ingestEvent({
      event_type: 'INVENTORY_SCAN',
      wallet_id: walletId,
      payload: {
        location_tag: locationTag,
        product_count: productCount,
        products: products.map(p => ({
          product_id: p.id,
          product_name: p.name,
          quantity: p.quantity,
          confidence: p.confidence,
        })),
        scan_method: 'batch',
        device_type: 'mobile',
      },
      correlation_id: `scan:${locationTag}:${Date.now()}`,
    });
  },

  /**
   * Record a Bishop state change
   */
  async recordBishopStateChange(
    previousState: string,
    currentState: string,
    trigger: string,
    context?: Record<string, unknown>,
    walletId?: string,
  ): Promise<{ data?: TelemetryEventResponse; error?: string }> {
    return this.ingestEvent({
      event_type: 'BISHOP_STATE_CHANGE',
      wallet_id: walletId,
      payload: {
        previous_state: previousState,
        current_state: currentState,
        trigger,
        context,
        device_type: 'mobile',
      },
    });
  },

  /**
   * Ingest a sensor reading
   */
  async ingestSensorReading(reading: SensorReading): Promise<{ data?: TelemetryEventResponse; error?: string }> {
    try {
      const response = await apiClient.post<TelemetryEventResponse>('/telemetry/sensors', reading);
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to ingest sensor reading' };
    }
  },

  /**
   * Record a Bishop recommendation
   */
  async recordBishopRecommendation(recommendation: BishopRecommendation): Promise<{ data?: TelemetryEventResponse; error?: string }> {
    try {
      const response = await apiClient.post<TelemetryEventResponse>('/telemetry/bishop/recommendations', recommendation);
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to record recommendation' };
    }
  },

  /**
   * Record acceptance/rejection of a Bishop recommendation
   */
  async recordBishopAcceptance(acceptance: BishopAcceptance): Promise<{ data?: TelemetryEventResponse; error?: string }> {
    try {
      const response = await apiClient.post<TelemetryEventResponse>('/telemetry/bishop/acceptance', acceptance);
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to record acceptance' };
    }
  },

  /**
   * Get pending Bishop recommendations
   */
  async getPendingRecommendations(orgId: string): Promise<{ data?: Array<{ event_id: string; timestamp: string; recommendation: Record<string, unknown> }>; error?: string }> {
    try {
      const response = await apiClient.get<Array<{ event_id: string; timestamp: string; recommendation: Record<string, unknown> }>>(
        `/telemetry/bishop/recommendations/pending?org_id=${orgId}`
      );
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to get pending recommendations' };
    }
  },

  /**
   * Record shrinkage detection
   */
  async recordShrinkage(shrinkage: ShrinkageRecord): Promise<{ data?: { event_id: string; shrinkage_quantity: number; shrinkage_percentage: number; severity: string; claimsiq_eligible: boolean }; error?: string }> {
    try {
      const response = await apiClient.post<{ event_id: string; shrinkage_quantity: number; shrinkage_percentage: number; severity: string; claimsiq_eligible: boolean }>(
        '/telemetry/shrinkage',
        shrinkage
      );
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to record shrinkage' };
    }
  },

  /**
   * Get telemetry statistics
   */
  async getStats(walletId?: string, hours: number = 24): Promise<{ data?: { period_hours: number; total_events: number; by_type: Array<{ event_type: string; count: number }> }; error?: string }> {
    try {
      const params = new URLSearchParams({ hours: hours.toString() });
      if (walletId) params.append('wallet_id', walletId);
      
      const response = await apiClient.get<{ period_hours: number; total_events: number; by_type: Array<{ event_type: string; count: number }> }>(
        `/telemetry/stats?${params.toString()}`
      );
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to get stats' };
    }
  },

  /**
   * Verify event integrity
   */
  async verifyIntegrity(eventId: string): Promise<{ data?: { event_id: string; integrity_valid: boolean; stored_hash: string; recomputed_hash: string }; error?: string }> {
    try {
      const response = await apiClient.get<{ event_id: string; integrity_valid: boolean; stored_hash: string; recomputed_hash: string }>(
        `/telemetry/verify/${eventId}`
      );
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to verify integrity' };
    }
  },

  /**
   * Get Ledger sync status
   */
  async getLedgerSyncStats(): Promise<{ data?: { total_events: number; synced_to_ledger: number; pending_sync: number; sync_percentage: number }; error?: string }> {
    try {
      const response = await apiClient.get<{ total_events: number; synced_to_ledger: number; pending_sync: number; sync_percentage: number }>(
        '/telemetry/ledger/stats'
      );
      return { data: response.data };
    } catch (error: any) {
      return { error: error.message || 'Failed to get Ledger sync stats' };
    }
  },
};
