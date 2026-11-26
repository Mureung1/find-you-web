"use client";

import { useEffect, useState } from "react";
import { type Location, requestApi } from "@/lib/find-you";

type LocationResult = { attempt: number; data: Location[] | null };

export function useLocations() {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<LocationResult>();

  useEffect(() => {
    const controller = new AbortController();
    requestApi<Location[]>("locations", { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ attempt, data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ attempt, data: null });
      });
    return () => controller.abort();
  }, [attempt]);

  const current = result?.attempt === attempt ? result.data : undefined;
  return {
    locations: current ?? [],
    loading: current === undefined,
    error: current === null,
    retry: () => setAttempt((previous) => previous + 1),
  };
}
