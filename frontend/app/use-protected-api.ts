"use client";

import { useAuth0 } from "@auth0/auth0-react";
import { useCallback } from "react";

const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;
export type SafeTokenInfo = { alg?: string; iss?: string; aud?: string; rolesClaimPresent: boolean };

function decodeSegment(segment: string): Record<string, unknown> {
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="))) as Record<string, unknown>;
}

/**
 * Makes a protected API request using an in-memory Auth0 access token.
 * Tokens are never written to localStorage or attached to public endpoints.
 */
export function useProtectedApi() {
  const { isAuthenticated, isLoading, getAccessTokenSilently } = useAuth0();

  const apiFetch = useCallback(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    if (!isAuthenticated) throw new Error("Sign in is required for this workspace.");
    const token = await getAccessTokenSilently({
      authorizationParams: audience ? { audience } : undefined,
    });
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    return fetch(input, { ...init, headers });
  }, [getAccessTokenSilently, isAuthenticated]);

  const getSafeTokenInfo = useCallback(async (): Promise<SafeTokenInfo> => {
    if (!isAuthenticated) throw new Error("Sign in is required for this workspace.");
    const token = await getAccessTokenSilently({ authorizationParams: audience ? { audience } : undefined });
    if (!token) throw new Error("Auth0 did not return an access token.");
    const [header, payload] = token.split(".");
    if (!header || !payload) throw new Error("The access token is not a JWT for this API.");
    const h = decodeSegment(header);
    const p = decodeSegment(payload);
    return {
      alg: typeof h.alg === "string" ? h.alg : undefined,
      iss: typeof p.iss === "string" ? p.iss : undefined,
      aud: Array.isArray(p.aud) ? p.aud.join(", ") : typeof p.aud === "string" ? p.aud : undefined,
      rolesClaimPresent: Object.prototype.hasOwnProperty.call(p, "https://api.aipeiisr.local/roles"),
    };
  }, [getAccessTokenSilently, isAuthenticated]);

  return { apiFetch, getSafeTokenInfo, isAuthenticated, isLoading };
}
