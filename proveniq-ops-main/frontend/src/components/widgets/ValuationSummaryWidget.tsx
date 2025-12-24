
export function ValuationSummaryWidget({ data }: { data: any }) {
    // Convert micros
    const amount = (parseInt(data.amount_micros) / 1000000).toLocaleString('en-US', {
        style: 'currency',
        currency: data.currency
    });

    return (
        <div className="bg-gray-800 rounded border border-gray-700 p-6">
            <h3 className="text-sm uppercase tracking-wider text-gray-400 mb-4 font-semibold">Asset Capital</h3>

            <div className="text-4xl font-bold text-white mb-2">{amount}</div>
            <div className="flex justify-between items-center text-sm">
                <span className="text-gray-500">Confidence Score: {(data.confidence_score * 100).toFixed(0)}%</span>
                <span className="text-gray-400">Valued: {new Date(data.valuation_date).toLocaleDateString()}</span>
            </div>

            <div className="mt-4 w-full bg-gray-700 h-1.5 rounded-full overflow-hidden">
                <div className="bg-emerald-500 h-full" style={{ width: `${data.confidence_score * 100}%` }}></div>
            </div>
        </div>
    );
}
