"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, type Location, requestApi } from "@/lib/find-you";

const mobileQuery = "(pointer: coarse), (max-width: 640px)";

export function useNeighborhoodPosition(enabled: boolean, select: (id: string) => void) {
  const [status, setStatus] = useState({ pending: false, message: "" });
  const lookup = useRef<AbortController | null>(null);
  const manual = useRef(false);

  const find = useCallback(() => {
    if (!window.isSecureContext || !navigator.geolocation) {
      setStatus({ pending: false, message: "현재 위치는 HTTPS에서 사용할 수 있어요. 동네 이름으로 검색해 주세요." });
      return;
    }

    lookup.current?.abort();
    const controller = new AbortController();
    lookup.current = controller;
    setStatus({ pending: true, message: "현재 위치를 확인하고 있어요." });

    function finish(message: string) {
      if (controller.signal.aborted) return;
      lookup.current = null;
      setStatus({ pending: false, message });
    }

    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      if (controller.signal.aborted) return;
      if (coords.accuracy > 1000) {
        finish("현재 위치가 정확하지 않아요. 동네 이름으로 검색해 주세요.");
        return;
      }
      try {
        const location = await requestApi<Location>("locations/nearby", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ latitude: coords.latitude, longitude: coords.longitude }),
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        select(location.location_id);
        finish(`${location.region} ${location.dong}을(를) 선택했어요.`);
      } catch (error) {
        finish(error instanceof ApiError ? error.message : "현재 동네를 확인하지 못했어요. 이름으로 검색해 주세요.");
      }
    }, (error) => {
      finish(error.code === error.PERMISSION_DENIED
        ? "위치 권한을 허용하거나 동네 이름으로 검색해 주세요."
        : "현재 위치를 확인하지 못했어요. 다시 시도하거나 동네 이름으로 검색해 주세요.");
    }, { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 });
  }, [select]);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    if (window.isSecureContext && window.matchMedia(mobileQuery).matches) {
      const permission = navigator.permissions?.query({ name: "geolocation" }).catch(() => null);
      void (permission ?? Promise.resolve(null)).then((result) => {
        if (active && !manual.current && !lookup.current && result?.state !== "denied") find();
      });
    }
    return () => {
      active = false;
      lookup.current?.abort();
      lookup.current = null;
    };
  }, [enabled, find]);

  function cancel() {
    manual.current = true;
    lookup.current?.abort();
    lookup.current = null;
    setStatus({ pending: false, message: "" });
  }

  return { ...status, find, cancel };
}
