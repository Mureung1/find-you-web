"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { requestApi } from "@/lib/find-you";

type Session = {
  google_client_id: string | null;
  origin: string | null;
  user: { user_id: string; display_name: string; is_admin: boolean } | null;
  demo_mode: boolean;
};

export function useSession(enabled = true) {
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>();

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    requestApi<Session>("auth/session", { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setSession(value); })
      .catch(() => { if (!controller.signal.aborted) setSession(null); });
    return () => controller.abort();
  }, [enabled, pathname]);

  return session;
}
