/**
 * Header bar showing panel health from GET /api/status.
 *
 * Why a separate component: the status refreshes after every user mutation,
 * so it re-renders often — keeping it small keeps that cheap.
 */
export default function StatusBar({ status }) {
  return (
    <header className="flex flex-wrap items-center gap-4 bg-gray-800 rounded-lg px-4 py-2.5 text-sm">
      <h1 className="text-lg font-bold tracking-wide">Lesserv</h1>
      <Badge ok={status?.template_loaded} label="Template" />
      <Badge ok={status?.xray_running} label="Xray" />
      {status?.xray_pid != null && (
        <span className="text-gray-400">PID {status.xray_pid}</span>
      )}
      <span className="text-gray-400 ml-auto">
        Users: {status?.user_count ?? '—'}
      </span>
    </header>
  )
}

/** Colored dot + label: green when ok, red when known-bad, gray when unknown. */
function Badge({ ok, label }) {
  const color =
    ok == null ? 'text-gray-500' : ok ? 'text-green-400' : 'text-red-400'
  return (
    <span className={`flex items-center gap-1.5 ${color}`}>
      <span>{ok ? '●' : '○'}</span>
      <span className="text-gray-300">{label}</span>
    </span>
  )
}
