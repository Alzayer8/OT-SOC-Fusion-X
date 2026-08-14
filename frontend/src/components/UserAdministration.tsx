import { useState } from "react";

import {
  createLocalUser,
  getLocalUsers,
  resetLocalUserPassword,
  updateLocalUser,
  type LocalRole,
  type LocalUser,
} from "../api/client";
import { useApiResource } from "../hooks/useApiResource";
import { DataTable, ExactStatusBadge, LoadingSkeleton, ProductError } from "./ProductComponents";

const ROLES: LocalRole[] = ["ADMIN", "SOC_ANALYST", "OT_ENGINEER", "READ_ONLY"];

export function UserAdministration() {
  const [revision, setRevision] = useState(0);
  const state = useApiResource(`local-users:${revision}`, getLocalUsers);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<LocalRole>("READ_ONLY");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const create = async () => {
    if (!username.trim() || !displayName.trim() || password.length < 12) return;
    setMessage(null);
    try {
      await createLocalUser({
        username: username.trim(),
        display_name: displayName.trim(),
        role,
        password,
      });
      setUsername("");
      setDisplayName("");
      setPassword("");
      setRole("READ_ONLY");
      setMessage("Local user created. The password was not retained in the browser.");
      setRevision((value) => value + 1);
    } catch (error) {
      setPassword("");
      setMessage(error instanceof Error ? error.message : "Local user creation failed.");
    }
  };

  return (
    <section className="panel admin-users">
      <div className="panel__header">
        <h2>Local Users &amp; Roles</h2>
      </div>
      <div className="panel__content">
        <div className="user-create-grid">
          <label>
            Username
            <input
              autoComplete="off"
              maxLength={64}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label>
            Display name
            <input
              autoComplete="off"
              maxLength={120}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
          <label>
            Role
            <select value={role} onChange={(event) => setRole(event.target.value as LocalRole)}>
              {ROLES.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Initial password
            <input
              autoComplete="new-password"
              maxLength={128}
              minLength={12}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button
            className="button"
            disabled={!username.trim() || !displayName.trim() || password.length < 12}
            type="button"
            onClick={() => void create()}
          >
            Create local user
          </button>
        </div>
        {message ? <p role="status">{message}</p> : null}
        {state.status === "loading" ? <LoadingSkeleton label="Loading local users" /> : null}
        {state.status === "error" ? <ProductError {...state} /> : null}
        {state.status === "success" ? (
          <DataTable label="Local authenticated users">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>State</th>
                <th>Administration</th>
              </tr>
            </thead>
            <tbody>
              {state.data.items.map((user) => (
                <UserRow
                  key={user.user_id}
                  user={user}
                  onChanged={() => setRevision((value) => value + 1)}
                />
              ))}
            </tbody>
          </DataTable>
        ) : null}
        <p className="safety-copy">
          Password hashes are never returned. The backend prevents disabling the final active
          administrator.
        </p>
      </div>
    </section>
  );
}

function UserRow({ user, onChanged }: { user: LocalUser; onChanged: () => void }) {
  const [role, setRole] = useState<LocalRole>(user.role);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const update = async (payload: { active?: boolean; role?: LocalRole }) => {
    try {
      await updateLocalUser(user.user_id, { ...payload, expected_version: user.version });
      setPassword("");
      setMessage("User updated.");
      onChanged();
    } catch (error) {
      setPassword("");
      setMessage(error instanceof Error ? error.message : "User update failed.");
    }
  };
  const resetPassword = async () => {
    try {
      await resetLocalUserPassword(user.user_id, password, user.version);
      setPassword("");
      setMessage("Password reset. The password was not retained in the browser.");
      onChanged();
    } catch (error) {
      setPassword("");
      setMessage(error instanceof Error ? error.message : "Password reset failed.");
    }
  };
  return (
    <tr>
      <td>
        <strong>{user.display_name}</strong>
        <small>{user.username}</small>
      </td>
      <td>
        <select
          aria-label={`Role for ${user.display_name}`}
          value={role}
          onChange={(event) => setRole(event.target.value as LocalRole)}
        >
          {ROLES.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </td>
      <td>
        <ExactStatusBadge value={user.active ? "ACTIVE" : "DISABLED"} />
      </td>
      <td>
        <div className="user-admin-actions">
          <button type="button" onClick={() => void update({ role })}>
            Save role
          </button>
          <button type="button" onClick={() => void update({ active: !user.active })}>
            {user.active ? "Disable user" : "Enable user"}
          </button>
          <label>
            New password
            <input
              aria-label={`New password for ${user.display_name}`}
              autoComplete="new-password"
              maxLength={128}
              minLength={12}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button
            disabled={password.length < 12}
            type="button"
            onClick={() => void resetPassword()}
          >
            Reset password
          </button>
        </div>
        {message ? <small role="status">{message}</small> : null}
      </td>
    </tr>
  );
}
