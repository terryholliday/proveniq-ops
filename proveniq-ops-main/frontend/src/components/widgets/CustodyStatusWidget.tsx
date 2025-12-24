
export function CustodyStatusWidget({ data }: { data: any }) {
    const isCrisis = data.status === 'DISPUTED' || data.status === 'LOST';
    const bgColor = isCrisis ? 'bg-red-900/30 border-red-800' : 'bg-gray-800 border-gray-700';
    const statusColor = isCrisis ? 'text-red-400' : 'text-green-400';

    return (
        <div className={`rounded border p-6 ${bgColor}`}>
            <h3 className="text-sm uppercase tracking-wider text-gray-400 mb-4 font-semibold">Chain of Custody</h3>

            <div className="grid grid-cols-2 gap-4">
                <div>
                    <div className="text-xs text-gray-500 uppercase">Current Status</div>
                    <div className={`text-xl font-bold ${statusColor}`}>{data.status}</div>
                </div>
                <div>
                    <div className="text-xs text-gray-500 uppercase">Custodian</div>
                    <div className="text-lg text-white">{data.current_custodian || "Unknown"}</div>
                </div>
                <div>
                    <div className="text-xs text-gray-500 uppercase">Location</div>
                    <div className="text-sm text-gray-300 font-mono">
                        {data.lat ? `${data.lat.toFixed(4)}, ${data.lon.toFixed(4)}` : "No GPS signal"}
                    </div>
                </div>
                <div>
                    <div className="text-xs text-gray-500 uppercase">Last Update</div>
                    <div className="text-sm text-gray-300">
                        {data.last_update ? new Date(data.last_update).toLocaleTimeString() : "--:--"}
                    </div>
                </div>
            </div>
        </div>
    );
}
