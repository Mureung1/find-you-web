"use client";

import { useEffect, useState } from "react";
import { type Location, requestApi } from "@/lib/find-you";

type LocationResult = { attempt: number; data: Location[] | null };

export function useLocations(initial?: Location[] | null) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<LocationResult>();

  useEffect(() => {
    if (attempt === 0 && initial !== undefined) return;
    const controller = new AbortController();
    requestApi<Location[]>("locations", { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ attempt, data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ attempt, data: null });
      });
    return () => controller.abort();
  }, [attempt, initial]);

  const current = attempt === 0 && initial !== undefined
    ? initial
    : result?.attempt === attempt ? result.data : undefined;
  return {
    locations: current ?? [],
    loading: current === undefined,
    error: current === null,
    retry: () => setAttempt((previous) => previous + 1),
  };
}
