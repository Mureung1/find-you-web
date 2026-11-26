"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";
import { useSession } from "@/hooks/use-session";
import { categories, postApi, requestApi } from "@/lib/find-you";
import { claimLabels, type ReviewClaim } from "@/lib/management";
import { PrivatePhotos } from "./private-photos";
import styles from "./management.module.css";

function ReviewCard({ claim, onDecision }: { claim: ReviewClaim; onDecision: (message: string) => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function decide(data: Record<string, unknown>, message: string) {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await postApi("claims/" + encodeURIComponent(claim.claim_id) + "/review", data);
      onDecision(message);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "요청을 처리하지 못했어요.");
    } finally {
      setPending(false);
    }
  }

  function approve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void decide({ action: "approve", item_id: data.get("item_id"), reply: data.get("reply") }, "소유 확인을 승인했어요.");
  }

  return (
    <li className={["form-panel", styles.panel].join(" ")}>
      <h3>{claim.claimant} · {claimLabels[claim.status]}</h3>
      <p className={styles.meta}>{claim.region} {claim.dong} · {categories[claim.category].label}</p>
      <div className={styles.details}>
        <p><strong>검색 특징</strong> {claim.features}</p>
        <p><strong>소유 확인 설명</strong> {claim.proof}</p>
      </div>
      {error && <p role="alert" className="input-error">{error}</p>}
      <form className={styles.inlineForm} onSubmit={approve} aria-busy={pending}>
        {claim.candidates.length ? (
          <fieldset disabled={pending}>
            <legend>{claim.status === "pending" ? "검토할 습득물" : "반환할 습득물"}</legend>
            {claim.candidates.map((item) => (
              <div key={item.item_id} className={styles.candidate}>
                {claim.status === "pending" ? (
                  <label><input type="radio" name="item_id" value={item.item_id} required />{item.title}</label>
                ) : <strong>{item.title}</strong>}
                <p className={styles.meta}><time dateTime={item.event_date}>{item.event_date}</time> 습득</p>
                <p>{item.features}</p>
                <PrivatePhotos itemId={item.item_id} positions={item.photo_positions} />
              </div>
            ))}
          </fieldset>
        ) : <p>현재 승인할 수 있는 습득물이 없어요.</p>}
        {claim.status === "pending" && claim.candidates.length > 0 && (
          <label className="form-field">요청자에게 보낼 수령 안내 (선택)
            <textarea name="reply" rows={3} maxLength={500} disabled={pending} />
          </label>
        )}
        {claim.reply && <p><strong>보낸 안내</strong> {claim.reply}</p>}
        <div className={styles.actions}>
          {claim.status === "pending" ? (
            <>
              {claim.candidates.length > 0 && <button type="submit" className="primary-button" disabled={pending}>소유 확인 승인</button>}
              <button type="button" className="secondary-button" disabled={pending}
                onClick={() => void decide({ action: "reject" }, "확인 요청을 종료했어요.")}>요청 종료</button>
            </>
          ) : (
            <button type="button" className="primary-button" disabled={pending}
              onClick={() => void decide({ action: "return" }, "반환 완료로 처리했어요.")}>반환 완료 처리</button>
          )}
        </div>
      </form>
    </li>
  );
}

export function ReviewPanel() {
  const session = useSession();
  const adminId = session?.user?.is_admin ? session.user.user_id : undefined;
  const [version, refresh] = useState(0);
  const [notice, setNotice] = useState("");
  const [loaded, setLoaded] = useState<{ admin: string; data: ReviewClaim[] | null }>();
  const claims = loaded?.admin === adminId ? loaded?.data : undefined;

  useEffect(() => {
    if (!adminId) return;
    const controller = new AbortController();
    requestApi<ReviewClaim[]>("claims/review", { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setLoaded({ admin: adminId, data }); })
      .catch(() => { if (!controller.signal.aborted) setLoaded({ admin: adminId, data: null }); });
    return () => controller.abort();
  }, [adminId, version]);

  if (session === undefined) return <p role="status">로그인 상태를 확인하고 있어요.</p>;
  if (session === null) return <p role="alert">로그인 상태를 불러오지 못했습니다.</p>;
  if (!session.user) return <Link href="/login" className="primary-button">로그인</Link>;
  if (!adminId) return <p role="alert">담당자 권한이 필요해요.</p>;
  if (claims === undefined) return <p role="status">확인 요청을 불러오고 있어요.</p>;
  if (claims === null) return <p role="alert">확인 요청을 불러오지 못했습니다. <button className="text-button"
    onClick={() => refresh((value) => value + 1)}>다시 시도</button></p>;

  return (
    <div className={styles.section}>
      {notice && <p role="status">{notice}</p>}
      {claims.length ? <ul className={styles.list}>{claims.map((claim) => (
        <ReviewCard key={claim.claim_id} claim={claim} onDecision={(message) => {
          setNotice(message);
          refresh((value) => value + 1);
        }} />
      ))}</ul> : <p>검토하거나 반환 처리할 요청이 없어요.</p>}
    </div>
  );
}
