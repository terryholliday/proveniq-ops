
interface TimelineEvent {
    occurred_at: string;
    title: string;
    description: string;
    actor: string;
}

export function ProvenanceTimelineWidget({ data }: { data: { events: TimelineEvent[] } }) {
    return (
        <div className="bg-gray-800 rounded border border-gray-700 p-6">
            <h3 className="text-sm uppercase tracking-wider text-gray-400 mb-4 font-semibold">Asset Provenance</h3>
            <div className="space-y-6 max-h-[400px] overflow-y-auto">
                {data.events?.map((evt, i) => (
                    <div key={i} className="flex gap-4">
                        <div className="flex flex-col items-center">
                            <div className="w-2 h-2 rounded-full bg-blue-500 mt-2"></div>
                            {i < data.events.length - 1 && <div className="w-px h-full bg-gray-700 my-1"></div>}
                        </div>
                        <div className="pb-2">
                            <div className="text-white font-medium">{evt.title}</div>
                            <div className="text-gray-400 text-sm">{evt.description}</div>
                            <div className="text-xs text-gray-500 mt-1 flex gap-2">
                                <span>{new Date(evt.occurred_at).toLocaleString()}</span>
                                <span>•</span>
                                <span className="font-mono text-blue-400">{evt.actor}</span>
                            </div>
                        </div>
                    </div>
                ))}
                {(!data.events || data.events.length === 0) && (
                    <div className="text-gray-500 text-sm italic">No events recorded.</div>
                )}
            </div>
        </div>
    );
}
