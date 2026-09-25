"use client";

import { useAuth0 } from "@auth0/auth0-react";

/** Visible login state; it renders only inside a configured Auth0Provider. */
export function AuthControls() {
  const { isAuthenticated, isLoading, loginWithRedirect, logout, user } = useAuth0();

  if (isLoading) return <div className="auth-controls" aria-live="polite">Checking sign-in…</div>;

  if (!isAuthenticated) {
    return (
      <div className="auth-controls">
        <button
          className="auth-button"
          onClick={() => loginWithRedirect({
            appState: { returnTo: `${window.location.pathname}${window.location.search}` },
          })}
        >
          Sign in for analyst access
        </button>
      </div>
    );
  }

  return (
    <div className="auth-controls">
      <span className="auth-user">Signed in as {user?.email || user?.name || "authorized user"}</span>
      <button
        className="auth-button"
        onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
      >
        Sign out
      </button>
    </div>
  );
}
