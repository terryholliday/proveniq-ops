
export function ShrinkageAnalysisWidget({ data }: { data: any }) {
    const variance = ((data.actual_usage - data.theoretical_usage) / data.theoretical_usage) * 100;
    const isHighRisk = Math.abs(variance) > 2;

    return (
        <div className="bg-gray-800 rounded border border-gray-700 p-6">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-sm uppercase tracking-wider text-gray-400 font-semibold">Shrinkage Analysis</h3>
                <span className="text-xs text-gray-500 font-mono">SYNC: {data.pos_system}</span>
            </div>

            <div className="flex items-end gap-4 mb-6">
                <div>
                    <div className="text-4xl font-bold text-white">{Math.abs(variance).toFixed(1)}%</div>
                    <div className="text-xs text-gray-400 uppercase mt-1">Variance</div>
                </div>
                <div className={`mb-1 px-2 py-0.5 rounded text-xs font-bold ${isHighRisk ? 'bg-red-900/50 text-red-500' : 'bg-emerald-900/50 text-emerald-500'}`}>
                    {variance > 0 ? 'OVER-POURING' : 'MISSING STOCK'}
                </div>
            </div>

            <div className="relative h-2 bg-gray-700 rounded-full mb-2 overflow-hidden">
                <div className="absolute top-0 bottom-0 bg-blue-500" style={{ left: '0%', width: `${(data.theoretical_usage / (Math.max(data.theoretical_usage, data.actual_usage))) * 100}%` }}></div>
                <div className="absolute top-0 bottom-0 bg-red-500 opacity-50" style={{ left: `${(data.theoretical_usage / (Math.max(data.theoretical_usage, data.actual_usage))) * 100}%`, width: `${(Math.abs(data.actual_usage - data.theoretical_usage) / (Math.max(data.theoretical_usage, data.actual_usage))) * 100}%` }}></div>
            </div>

            <div className="flex justify-between text-xs text-gray-500 mb-6">
                <span>Theoretical (POS): {data.theoretical_usage} {data.unit}</span>
                <span>Actual (Scan): {data.actual_usage} {data.unit}</span>
            </div>

            <div className="p-4 bg-gray-700/30 rounded border border-gray-700">
                <div className="flexitems-start gap-3">
                    <div className="flex-1">
                        <div className="text-sm font-medium text-white">Projected Annual Loss</div>
                        <div className="text-xs text-gray-400">Based on current variances for {data.category}</div>
                    </div>
                    <div className="text-lg font-bold text-red-400">-${data.projected_loss.toLocaleString()}</div>
                </div>
            </div>
        </div>
    );
}
