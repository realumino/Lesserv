/**
 * Header bar showing panel health from GET /api/status.
 *
 * Why a separate component: the status refreshes after every user mutation,
 * so it re-renders often — keeping it small keeps that cheap.
 */
export default function StatusBar({ status }) {
  return (
    <header className="flex flex-wrap items-center gap-4 bg-apple-card rounded-2xl px-5 py-3 text-sm shadow-sm border border-apple-border">
      <h1 className="text-lg font-bold tracking-tight text-apple-text">Lesserv</h1>
      <Badge ok={status?.template_loaded} label="Template" />
      <Badge ok={status?.xray_running} label="Xray" />
      {status?.xray_pid != null && (
        <span className="text-apple-muted">PID {status.xray_pid}</span>
      )}
      <span className="text-apple-muted ml-auto">
        Users: {status?.user_count ?? '—'}
      </span>
    </header>
  )
}

/** Colored dot + label: green when ok, red when known-bad, gray when unknown. */
function Badge({ ok, label }) {
  const color =
    ok == null ? 'text-apple-muted' : ok ? 'text-apple-green' : 'text-apple-red'
  const dot =
    ok == null ? 'bg-apple-gray' : ok ? 'bg-apple-green' : 'bg-apple-red'
  return (
    <span className={`flex items-center gap-1.5 ${color}`}>
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-apple-muted">{label}</span>
    </span>
  )
}
