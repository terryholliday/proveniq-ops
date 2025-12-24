
export default function Home() {
  return (
    <div className="flex h-screen bg-gray-900 text-white">
      {/* Sidebar Placeholder */}
      <aside className="w-64 border-r border-gray-800 p-4">
        <h1 className="text-xl font-bold mb-8">PROVENIQ OPS</h1>
        <nav className="space-y-4">
          <div className="p-2 bg-gray-800 rounded">Dashboard</div>
          <div className="p-2 text-gray-400 hover:text-white">Audit Log</div>
          <div className="p-2 text-gray-400 hover:text-white">Work Orders</div>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8">
        <header className="flex justify-between items-center mb-8">
          <h2 className="text-2xl font-semibold">Operational Overview</h2>
          <div className="text-sm text-green-400 font-mono">BISHOP ENGINE: ONLINE</div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gray-800 p-6 rounded border border-gray-700">
            <h3 className="text-gray-400 text-sm mb-2">Pending Approvals</h3>
            <div className="text-3xl font-bold">0</div>
          </div>
          <div className="bg-gray-800 p-6 rounded border border-gray-700">
            <h3 className="text-gray-400 text-sm mb-2">Active Work Orders</h3>
            <div className="text-3xl font-bold">0</div>
          </div>
          <div className="bg-gray-800 p-6 rounded border border-gray-700">
            <h3 className="text-gray-400 text-sm mb-2">System Health</h3>
            <div className="text-3xl font-bold text-green-500">NOMINAL</div>
          </div>
        </div>
      </main>
    </div>
  );
}
