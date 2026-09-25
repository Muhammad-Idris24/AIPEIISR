"use client";

import { Auth0Provider } from "@auth0/auth0-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { AuthControls } from "./auth-controls";

const domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN;
const clientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;
const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;

/**
 * Keeps public citizen pages usable when local Auth0 configuration has not
 * been supplied. Protected screens will be converted to require this provider
 * in the next step; we never substitute a browser-supplied role header.
 */
export default function AppAuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  if (!domain || !clientId || !audience) return <>{children}</>;

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        audience,
        redirect_uri: typeof window === "undefined" ? undefined : window.location.origin,
      }}
      onRedirectCallback={(appState) => {
        // Auth0 always returns to the allowlisted root URL. Restore only an
        // internal, path-based destination captured immediately before login.
        const candidate = typeof appState?.returnTo === "string" ? appState.returnTo : "/";
        const returnTo = candidate.startsWith("/") && !candidate.startsWith("//") ? candidate : "/";
        // Keep the SDK's freshly acquired token in memory. A full browser
        // reload here would discard it and make the protected route appear
        // signed out. The destination is validated before client navigation.
        router.replace(returnTo);
      }}
    >
      <AuthControls />
      {children}
    </Auth0Provider>
  );
}
