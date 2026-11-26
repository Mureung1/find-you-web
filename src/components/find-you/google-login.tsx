"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { useSession } from "@/hooks/use-session";
import styles from "./google-login.module.css";

type GoogleIdentity = {
  accounts: { id: {
    initialize: (config: { client_id: string; ux_mode: "redirect"; login_uri: string }) => void;
    renderButton: (element: HTMLElement, config: { theme: "outline"; size: "large"; locale: "ko"; width: number }) => void;
  } };
};

const loopbackHosts = new Set(["localhost", "127.0.0.1", "[::1]"]);

function GoogleButton({ clientId, origin }: { clientId: string; origin: string }) {
  const buttonContainer = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const loginUrl = new URL("/login", origin);
  const currentUrl = typeof window === "undefined" ? loginUrl : new URL(window.location.origin);
  const differentOrigin = currentUrl.origin !== loginUrl.origin;
  const isLocalAlias = differentOrigin
    && currentUrl.protocol === loginUrl.protocol && currentUrl.port === loginUrl.port
    && loopbackHosts.has(currentUrl.hostname) && loopbackHosts.has(loginUrl.hostname);
  const redirectUrl = isLocalAlias ? loginUrl.href : null;

  useEffect(() => {
    if (redirectUrl) window.location.replace(redirectUrl);
  }, [redirectUrl]);

  function renderButton() {
    const google = (window as Window & { google?: GoogleIdentity }).google;
    if (!google || !buttonContainer.current) {
      setError("Google 로그인 버튼을 불러오지 못했습니다.");
      return;
    }
    google.accounts.id.initialize({
      client_id: clientId,
      ux_mode: "redirect",
      login_uri: new URL("/api/auth/google", origin).href,
    });
    buttonContainer.current.replaceChildren();
    google.accounts.id.renderButton(buttonContainer.current, { theme: "outline", size: "large", locale: "ko", width: 240 });
  }

  if (differentOrigin) {
    if (!isLocalAlias && loginUrl.protocol === "http:") {
      return (
        <>
          <button className={`secondary-button ${styles.unavailableButton}`} type="button" disabled aria-describedby="google-login-availability">
            Google 계정으로 로그인
          </button>
          <p id="google-login-availability" className={styles.availabilityMessage}>
            이 주소에서 Google 로그인을 사용하려면 등록된 HTTPS 주소가 필요해요.
          </p>
        </>
      );
    }
    return (
      <div>
        <p role="status">{isLocalAlias ? "Google 로그인 주소로 이동하고 있어요." : "등록된 사이트에서 Google 로그인을 이용할 수 있어요."}</p>
        <a className="text-button" href={loginUrl.href}>로그인 페이지 열기</a>
      </div>
    );
  }

  return (
    <>
      <div ref={buttonContainer} />
      <Script src="https://accounts.google.com/gsi/client" onReady={renderButton}
        onError={() => setError("Google 로그인 버튼을 불러오지 못했습니다.")} />
      {error && <p className="input-error" role="alert">{error}</p>}
    </>
  );
}

export function GoogleLoginPanel({ googleError }: { googleError: boolean }) {
  const router = useRouter();
  const session = useSession();
  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState(false);

  async function logout() {
    setLogoutPending(true);
    setLogoutError(false);
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error("Logout failed");
      router.replace("/");
    } catch {
      setLogoutError(true);
      setLogoutPending(false);
    }
  }

  return (
    <section className={styles.panel} aria-label="로그인 상태">
      {session === undefined && <p role="status">로그인 상태를 확인하고 있어요.</p>}
      {session === null && <p className="input-error" role="alert">로그인 상태를 불러오지 못했습니다. 새로고침해 주세요.</p>}
      {session && !session.google_client_id && <p>Google 로그인 설정을 준비 중입니다.</p>}
      {session?.user && (
        <>
          <p><strong>{session.user.display_name}</strong> 계정으로 로그인했어요.</p>
          {logoutError && <p className="input-error" role="alert">로그아웃에 실패했습니다. 다시 시도해 주세요.</p>}
          <div className="form-actions">
            <Link href="/my-items" className="secondary-button">내 글</Link>
            {session.user.is_admin && <Link href="/claims/review" className="secondary-button">소유 확인 검토</Link>}
            <button className="primary-button" type="button" disabled={logoutPending} onClick={logout}>로그아웃</button>
          </div>
        </>
      )}
      {session?.google_client_id && session.origin && !session.user && (
        <>
          {googleError && <p className="input-error" role="alert">Google 로그인을 완료하지 못했습니다. 다시 시도해 주세요.</p>}
          <GoogleButton clientId={session.google_client_id} origin={session.origin} />
        </>
      )}
    </section>
  );
}
