
import { ComponentType } from "react";
// Import Widgets (Will create next)
import { ProvenanceTimelineWidget } from "./ProvenanceTimelineWidget";
import { CustodyStatusWidget } from "./CustodyStatusWidget";
import { ValuationSummaryWidget } from "./ValuationSummaryWidget";

// Map String (Enum) to Component
export const WIDGET_REGISTRY: Record<string, ComponentType<any>> = {
    "PROVENANCE_TIMELINE": ProvenanceTimelineWidget,
    "CUSTODY_STATUS": CustodyStatusWidget,
    "VALUATION_SUMMARY": ValuationSummaryWidget,
    // Fallbacks
    "TEMP_GAUGE": () => <div className="p-4 bg-gray-800 text-yellow-500"> Temp Gauge Placeholder</ div >,
"RISK_BADGE": () => <div className="p-4 bg-gray-800 text-red-500" > Risk Badge Placeholder </div>
};
