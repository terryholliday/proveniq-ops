
import { getAssetProfile } from "@/lib/coreClient";
import { WidgetRenderer } from "@/components/widgets/WidgetRenderer";

export default async function Home({ searchParams }: { searchParams: Promise<{ asset_id?: string }> }) {
  const { asset_id } = await searchParams;

  // Golden Spike Mock ID if none provided
  const targetId = asset_id || "LOC-FREEZER-01";

  // Fetch Data (Server Side)
  let profile = null;
  let error = null;

  try {
    profile = await getAssetProfile(targetId);
  } catch (e: any) {
    error = e.message;
  }

  return (
    <div className="flex h-screen bg-gray-900 text-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-800 p-4 bg-gray-950 flex flex-col">
        <div className="mb-10">
          <h1 className="text-xl font-bold text-emerald-400 tracking-tight">PROVENIQ OPS</h1>
          <div className="text-xs text-gray-500 font-mono mt-1">V4.2.0 • BISHOP RETAIL</div>
        </div>

        <nav className="space-y-2 flex-1">
          <div className="p-2 bg-gray-800 rounded text-sm font-medium">Single Asset View</div>
          <div className="p-2 text-gray-400 hover:text-white text-sm">Fleet Status</div>
          <div className="p-2 text-gray-400 hover:text-white text-sm">Escalations</div>
        </nav>

        <div className="pt-4 border-t border-gray-800">
          <div className="text-xs text-gray-600 mb-2">TARGET ASSET</div>
          <form className="flex gap-2">
            <input
              name="asset_id"
              defaultValue={targetId}
              className="bg-gray-900 text-xs p-2 rounded w-full border border-gray-700 text-gray-300 font-mono"
            />
            <button className="bg-emerald-600 text-white p-2 rounded text-xs">GO</button>
          </form>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-6">
          <div>
            <h2 className="text-2xl font-bold text-white">Inventory Command Center</h2>
            <div className="text-sm text-gray-400 font-mono mt-1">CONTEXT: {targetId === 'LOC-FREEZER-01' ? 'Cold Storage Unit 1' : targetId}</div>
          </div>
          <div className="flex gap-4">
            <span className="px-3 py-1 bg-blue-900/30 text-blue-400 border border-blue-800 rounded text-xs tracking-wide">
              LIVE STREAM
            </span>
            <span className="px-3 py-1 bg-purple-900/30 text-purple-400 border border-purple-800 rounded text-xs tracking-wide">
              CORE CONNECTED
            </span>
          </div>
        </header>

        {error ? (
          <div className="p-6 bg-red-900/20 border border-red-800 rounded text-red-400">
            ERROR: {error}
          </div>
        ) : !profile ? (
          <div className="p-12 text-center text-gray-500 border border-dashed border-gray-800 rounded">
            Asset Not Found in Core.
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column: Main Status & Timeline */}
            <div className="lg:col-span-2 space-y-8">
              <WidgetRenderer widgets={profile.widgets} />
            </div>

            {/* Right Column: Metadata / Actions */}
            <div className="space-y-8">
              <div className="p-6 bg-gray-800/50 border border-gray-700 rounded">
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-4">Capabilities Detected</h4>
                <div className="flex flex-wrap gap-2">
                  {profile.capabilities?.map((cap: string) => (
                    <span key={cap} className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded border border-gray-600">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
