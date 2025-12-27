
export function VendorReconciliationWidget({ data }: { data: any }) {
    const hasDiscrepancy = data.discrepancies && data.discrepancies.length > 0;

    return (
        <div className="bg-gray-800 rounded border border-gray-700 p-6">
            <div className="flex justify-between items-start mb-6">
                <div>
                    <h3 className="text-sm uppercase tracking-wider text-gray-400 font-semibold">Vendor Reconciliation</h3>
                    <div className="text-2xl font-bold text-white mt-1">{data.vendor_name}</div>
                    <div className="text-xs text-gray-500 font-mono">INV #{data.invoice_id} • {new Date(data.delivery_date).toLocaleDateString()}</div>
                </div>
                <div className={`px-3 py-1 rounded text-xs font-bold border ${hasDiscrepancy ? 'bg-red-900/30 text-red-400 border-red-800' : 'bg-emerald-900/30 text-emerald-400 border-emerald-800'}`}>
                    {hasDiscrepancy ? 'DISCREPANCY DETECTED' : 'MATCH VERIFIED'}
                </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-gray-700/50 p-3 rounded">
                    <div className="text-xs text-gray-400 uppercase">Invoiced items</div>
                    <div className="text-xl font-bold text-white">{data.expected_items_count}</div>
                </div>
                <div className="bg-gray-700/50 p-3 rounded">
                    <div className="text-xs text-gray-400 uppercase">Scanned items</div>
                    <div className={`text-xl font-bold ${data.scanned_items_count !== data.expected_items_count ? 'text-yellow-400' : 'text-white'}`}>
                        {data.scanned_items_count}
                    </div>
                </div>
                <div className="bg-gray-700/50 p-3 rounded">
                    <div className="text-xs text-gray-400 uppercase">Value At Risk</div>
                    <div className="text-xl font-bold text-red-400">${data.discrepancy_value.toFixed(2)}</div>
                </div>
            </div>

            {hasDiscrepancy && (
                <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-gray-500 uppercase">Flagged Items</h4>
                    {data.discrepancies.map((item: any, idx: number) => (
                        <div key={idx} className="flex justify-between items-center text-sm p-3 bg-red-950/20 border border-red-900/30 rounded">
                            <span className="text-gray-300 font-medium">{item.item_name}</span>
                            <div className="text-right">
                                <div className="text-red-400 font-mono">{item.issue} ({item.quantity_diff})</div>
                                <div className="text-xs text-gray-500">Auto-Credit Request Generated</div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
