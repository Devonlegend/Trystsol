"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useWallet } from "@solana/wallet-adapter-react";

import {
  API_URL,
  apiFetch,
  clearSession,
  getSession,
  restoreSession,
  saveSession,
  subscribeSession,
  type Session,
  type SessionUser,
} from "./api";

interface Challenge {
  domain: string;
  uri: string;
  version: string;
  chainId: string;
  nonce: string;
  statement: string;
  issuedAt: string;
  expirationTime: string;
}

interface AuthContextValue {
  session: Session | null;
  user: SessionUser | null;
  busy: boolean;
  error: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

export function buildSiwsMessage(challenge: Challenge, address: string): string {
  let message = `${challenge.domain} wants you to sign in with your Solana account:\n${address}`;
  if (challenge.statement) message += `\n\n${challenge.statement}`;
  const fields = [
    `URI: ${challenge.uri}`,
    `Version: ${challenge.version}`,
    `Chain ID: ${challenge.chainId}`,
    `Nonce: ${challenge.nonce}`,
    `Issued At: ${challenge.issuedAt}`,
    `Expiration Time: ${challenge.expirationTime}`,
  ];
  return `${message}\n\n${fields.join("\n")}`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { publicKey, signMessage, wallet } = useWallet();
  const [session, setSession] = useState<Session | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = subscribeSession(() => setSession(getSession()));
    setSession(getSession());
    void restoreSession();
    return unsubscribe;
  }, []);

  const signIn = useCallback(async () => {
    setError(null);
    if (!publicKey) {
      setError("Connect a wallet first.");
      return;
    }
    setBusy(true);
    try {
      const challenge = await apiFetch<Challenge>(
        "/api/auth/nonce/",
        { method: "POST", body: "{}" },
        { retry: false },
      );

      const adapter = wallet?.adapter as
        | { signIn?: (input: Challenge) => Promise<any> }
        | undefined;

      let message: string;
      let signature: string;

      if (adapter?.signIn) {
        const output = await adapter.signIn(challenge);
        const result = Array.isArray(output) ? output[0] : output;
        message = new TextDecoder().decode(result.signedMessage);
        signature = toBase64(new Uint8Array(result.signature));
      } else {
        if (!signMessage) {
          throw new Error("This wallet cannot sign messages.");
        }
        message = buildSiwsMessage(challenge, publicKey.toBase58());
        const signed = await signMessage(new TextEncoder().encode(message));
        signature = toBase64(new Uint8Array(signed));
      }

      const result = await apiFetch<{
        access: string;
        refresh: string;
        user: SessionUser;
        wallet: { address: string; is_primary: boolean };
      }>(
        "/api/auth/verify/",
        {
          method: "POST",
          body: JSON.stringify({ message, signature }),
        },
        { retry: false },
      );

      saveSession({
        access: result.access,
        refresh: "",
        user: result.user,
        wallet: result.wallet,
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }, [publicKey, signMessage, wallet]);

  const signOut = useCallback(async () => {
    try {
      await fetch(`${API_URL}/api/auth/logout/`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
        credentials: "include",
      });
    } catch {
      // Local sign-out still proceeds if the network call fails.
    }
    clearSession();
  }, []);

  const value = useMemo(
    () => ({
      session,
      user: session?.user ?? null,
      busy,
      error,
      signIn,
      signOut,
      clearError: () => setError(null),
    }),
    [session, busy, error, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
