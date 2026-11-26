"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import { useSession } from "@/hooks/use-session";
import { postApi } from "@/lib/find-you";
import type { ClaimQuery } from "@/lib/management";
import styles from "./management.module.css";

export function ClaimForm({ query }: { query: ClaimQuery }) {
  const session = useSession();
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const proof = String(new FormData(event.currentTarget).get("proof") ?? "").trim();
    if (proof.length < 5) { setError("소유 확인에 쓸 설명을 다섯 글자 이상 입력해 주세요."); return; }
    setPending(true);
    setError("");
    try {
      await postApi("claims", { ...query, proof });
      setSent(true);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "요청을 보내지 못했어요.");
    } finally {
      setPending(false);
    }
  }

  const className = ["form-panel", styles.claimForm].join(" ");
  if (sent) return <section className={className} role="status">
    <p>소유 확인을 요청했어요.</p>
    <div><Link href="/my-items#my-claims" className="secondary-button">내 요청 보기</Link></div>
  </section>;
  if (session === undefined) return null;
  if (!session?.user) return <section className={className}>
    <div><Link href="/login" className="secondary-button">로그인하고 소유 확인 요청</Link></div>
  </section>;

  return (
    <form className={className} onSubmit={submit} aria-busy={pending} aria-label="소유 확인 요청">
      <label className="form-field">담당자에게 전달할 소유 확인 설명
        <textarea name="proof" required minLength={5} maxLength={1000} rows={3} disabled={pending}
          placeholder="물건을 잃어버린 경위나 주인만 알 수 있는 특징을 적어 주세요." />
      </label>
      {error && <p role="alert" className="input-error">{error}</p>}
      <div><button className="primary-button" type="submit" disabled={pending}>소유 확인 요청</button></div>
    </form>
  );
}
