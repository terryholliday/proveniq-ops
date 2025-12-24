
import { ComponentType } from "react";
// Import Widgets
import { ProvenanceTimelineWidget } from "./ProvenanceTimelineWidget";
import { CustodyStatusWidget } from "./CustodyStatusWidget";
import { ValuationSummaryWidget } from "./ValuationSummaryWidget";

// Telemetry Gauge for industrial sensors
const TelemetryGaugeWidget: ComponentType<{ data: any }> = ({ data }) => (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide">Telemetry</h3>
            <span className={`px-2 py-0.5 rounded text-xs font-mono ${
                data.status === 'NORMAL' ? 'bg-green-900 text-green-400' :
                data.status === 'WARNING' ? 'bg-yellow-900 text-yellow-400' :
                'bg-red-900 text-red-400'
            }`}>
                {data.status}
            </span>
        </div>
        <div className="grid grid-cols-2 gap-4">
            {data.current_temp_c !== undefined && (
                <div>
                    <p className="text-xs text-gray-500">Temperature</p>
                    <p className="text-xl font-bold text-cyan-400">{data.current_temp_c}°C</p>
                </div>
            )}
            {data.humidity_pct !== undefined && (
                <div>
                    <p className="text-xs text-gray-500">Humidity</p>
                    <p className="text-xl font-bold text-blue-400">{data.humidity_pct}%</p>
                </div>
            )}
            {data.battery_pct !== undefined && (
                <div>
                    <p className="text-xs text-gray-500">Battery</p>
                    <p className="text-xl font-bold text-green-400">{data.battery_pct}%</p>
                </div>
            )}
        </div>
        <p className="text-xs text-gray-600 mt-3">
            Last reading: {new Date(data.last_reading_at).toLocaleTimeString()}
        </p>
    </div>
);

// Risk Badge for fraud/risk scoring
const RiskBadgeWidget: ComponentType<{ data: any }> = ({ data }) => (
    <div className={`rounded-lg p-4 border ${
        data.risk_level === 'LOW' ? 'bg-green-900/20 border-green-700' :
        data.risk_level === 'MEDIUM' ? 'bg-yellow-900/20 border-yellow-700' :
        data.risk_level === 'HIGH' ? 'bg-orange-900/20 border-orange-700' :
        'bg-red-900/20 border-red-700'
    }`}>
        <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide">Risk Assessment</h3>
            <span className={`px-2 py-1 rounded text-sm font-bold ${
                data.risk_level === 'LOW' ? 'bg-green-800 text-green-300' :
                data.risk_level === 'MEDIUM' ? 'bg-yellow-800 text-yellow-300' :
                data.risk_level === 'HIGH' ? 'bg-orange-800 text-orange-300' :
                'bg-red-800 text-red-300'
            }`}>
                {data.risk_level}
            </span>
        </div>
        <div className="text-3xl font-bold text-white mb-2">{data.fraud_score}/100</div>
        {data.signals && data.signals.length > 0 && (
            <div className="space-y-1">
                {data.signals.slice(0, 3).map((s: any, i: number) => (
                    <p key={i} className="text-xs text-gray-400">• {s.description}</p>
                ))}
            </div>
        )}
    </div>
);

// Service Timeline for maintenance records
const ServiceTimelineWidget: ComponentType<{ data: any }> = ({ data }) => (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Service History</h3>
        <div className="space-y-3">
            {data.records?.slice(0, 3).map((r: any, i: number) => (
                <div key={i} className="flex items-center gap-3">
                    <span className={`w-2 h-2 rounded-full ${
                        r.status === 'completed' ? 'bg-green-500' :
                        r.status === 'in_progress' ? 'bg-yellow-500' : 'bg-gray-500'
                    }`} />
                    <div>
                        <p className="text-sm text-white">{r.service_type}</p>
                        <p className="text-xs text-gray-500">{r.provider_name}</p>
                    </div>
                </div>
            ))}
        </div>
        {data.total_service_cost_cents && (
            <p className="text-xs text-gray-500 mt-3">
                Total: ${(data.total_service_cost_cents / 100).toLocaleString()}
            </p>
        )}
    </div>
);

// Map String (Enum) to Component
export const WIDGET_REGISTRY: Record<string, ComponentType<any>> = {
    "PROVENANCE_TIMELINE": ProvenanceTimelineWidget,
    "CUSTODY_STATUS": CustodyStatusWidget,
    "VALUATION_SUMMARY": ValuationSummaryWidget,
    "TELEMETRY_GAUGE": TelemetryGaugeWidget,
    "RISK_BADGE": RiskBadgeWidget,
    "SERVICE_TIMELINE": ServiceTimelineWidget,
};
