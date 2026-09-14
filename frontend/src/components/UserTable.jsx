/**
 * The user list: fetches nothing itself — App passes users + callbacks down.
 *
 * Why a dumb component: data ownership stays in App, so a refresh after
 * create/edit/delete automatically re-renders this table.
 */
export default function UserTable({ users, error, onAdd, onEdit, onDelete }) {
  if (error) {
    return <p className="text-red-400">Failed to load users: {error}</p>
  }
  if (users === null) {
    return <p className="text-gray-400">Loading users…</p>
  }
  return (
    <div className="space-y-3">
      <button
        onClick={onAdd}
        className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded text-sm font-medium"
      >
        + Add User
      </button>
      {users.length === 0 ? (
        <p className="text-gray-400">No users yet.</p>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-gray-400 border-b border-gray-700">
              <Th>Username</Th>
              <Th>Status</Th>
              <Th>Expire</Th>
              <Th>Inbounds</Th>
              <Th>Outbounds</Th>
              <Th>Note</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username} className="border-b border-gray-800">
                <Td className="font-mono">{u.username}</Td>
                <Td>
                  <StatusBadge status={u.status} />
                </Td>
                <Td>{fmtExpire(u.expire)}</Td>
                <Td>{u.allowed_inbounds.join(', ') || '—'}</Td>
                <Td>{u.allowed_outbounds.join(', ') || '—'}</Td>
                <Td className="max-w-40 truncate" title={u.note || ''}>
                  {u.note || '—'}
                </Td>
                <Td>
                  <button
                    onClick={() => onEdit(u)}
                    className="text-blue-400 hover:text-blue-300 mr-3"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => onDelete(u.username)}
                    className="text-red-400 hover:text-red-300"
                  >
                    Delete
                  </button>
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/** Consistent cell padding for header and body cells. */
function Th({ children }) {
  return <th className="py-2 pr-4 font-medium">{children}</th>
}
function Td({ children, className = '', ...rest }) {
  return (
    <td className={`py-2 pr-4 ${className}`} {...rest}>
      {children}
    </td>
  )
}

/** Green "active" / gray "disabled" pill. */
function StatusBadge({ status }) {
  const cls =
    status === 'active'
      ? 'bg-green-900/60 text-green-300'
      : 'bg-gray-700 text-gray-300'
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

/** Human-readable expiry: null = unset, 0 = never, otherwise a date. */
function fmtExpire(expire) {
  if (expire == null) return '—'
  if (expire === 0) return 'never'
  return new Date(expire * 1000).toLocaleDateString()
}
