"use client";

import { CircleCheck, LocateFixed, Plus, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import { useLocations } from "@/hooks/use-locations";
import { ApiError, postApi } from "@/lib/find-you";
import { CategorySelect, NeighborhoodSelect } from "./select-fields";

const modes = {
  lost: { title: "분실물 등록", icon: Plus, intro: "잃어버린 물건과 마지막으로 본 동네를 알려 주세요.", action: "분실물 등록", endpoint: "lost-items" },
  found: { title: "습득물 비공개 등록", icon: ShieldCheck, intro: "물건을 주운 동네와 주인만 알 수 있는 특징을 남겨 주세요. 등록한 내용은 서버에 비공개로 보관됩니다.", action: "비공개로 등록", endpoint: "found-items" },
  match: { title: "특징으로 찾기", icon: LocateFixed, intro: "분실한 동네와 물건 종류, 기억나는 특징으로 후보가 있는지 확인할 수 있어요.", action: "후보 확인", endpoint: "candidates/check" },
};

type Outcome = { message: string; candidate?: boolean };

export function ItemForm({ mode }: { mode: keyof typeof modes }) {
  const { locations, loading, error: locationsError, retry } = useLocations();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [outcome, setOutcome] = useState<Outcome>();
  const isMatch = mode === "match";
  const isLost = mode === "lost";
  const settings = modes[mode];
  const Icon = settings.icon;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;

    const form = event.currentTarget;
    const fields = new FormData(form);
    const title = String(fields.get("title") ?? "").trim();
    const features = String(fields.get("features") ?? "").trim();
    const eventDate = String(fields.get("event_date") ?? "");
    const today = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());
    const consent = fields.has("consent_to_publish");
    setError("");
    setOutcome(undefined);

    if (!isMatch && title.length < 2) return setError("물건 이름을 두 글자 이상 입력해 주세요.");
    if (!isLost && features.length < 2) return setError("물건 특징을 두 글자 이상 입력해 주세요.");
    if (!isMatch && eventDate > today) return setError("오늘 또는 이전 날짜를 선택해 주세요.");

    const scope = { location_id: fields.get("location_id"), category: fields.get("category") };
    setBusy(true);
    try {
      if (isMatch) {
        const { has_candidate } = await postApi<{ has_candidate: boolean }>(settings.endpoint, { ...scope, features });
        setOutcome({
          candidate: has_candidate,
          message: has_candidate ? "입력한 조건에 맞는 후보가 있어요." : "입력한 조건에 맞는 후보가 없어요.",
        });
      } else {
        const details = { ...scope, title, event_date: eventDate };
        await postApi<{ item_id: string }>(settings.endpoint, isLost
          ? { ...details, consent_to_publish: consent }
          : { ...details, features });
        setOutcome({ message: isLost && consent ? "분실글을 공개 목록에 등록했어요." : "비공개로 등록했어요." });
      }
    } catch (failure) {
      setError(failure instanceof ApiError && failure.status === 422
        ? failure.message
        : isMatch ? "후보 확인에 실패했습니다. 다시 시도해 주세요." : "등록에 실패했습니다. 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell form-page">
      <div className="form-intro">
        <span className="form-icon"><Icon size={25} aria-hidden /></span>
        <h1>{settings.title}</h1>
        <p>{settings.intro}</p>
      </div>
      {isMatch && <aside className="demo-panel">
        <strong>데모 검색</strong>
        <p>서울 마포구 성산동 · 생활용품 · 손잡이에 별 스티커</p>
        <p>위 조건은 후보가 있어요. 동네를 연남동으로 바꾸면 후보가 없어요.</p>
      </aside>}
      {!isMatch && outcome ? (
        <section className="form-panel completion" role="status">
          <CircleCheck size={31} aria-hidden />
          <p>{outcome.message}</p>
          <Link href="/" className="primary-button">분실글 탐색</Link>
        </section>
      ) : (
        <form className="form-panel" onSubmit={submit} onChange={() => { setError(""); setOutcome(undefined); }} aria-busy={busy}>
          <fieldset className="form-fields" disabled={busy}>
            <div className="field-grid">
              <label className="form-field">동네
                <NeighborhoodSelect name="location_id" locations={locations} required disabled={loading || locationsError}
                  placeholder={loading ? "동네 불러오는 중" : "동네 선택"} />
              </label>
              <label className="form-field">물건 종류
                <CategorySelect name="category" placeholder="물건 종류 선택" required />
              </label>
            </div>
            {locationsError && <p className="input-error" role="alert">
              동네 목록을 불러오지 못했습니다. <button className="text-button" type="button" onClick={retry}>다시 불러오기</button>
            </p>}
            {!loading && !locationsError && !locations.length && <p role="status">선택할 수 있는 동네가 없습니다.</p>}
            {!isMatch && <div className="field-grid name-date-grid">
              <label className="form-field">물건 이름
                <input name="title" placeholder="예: 흰색 무선 이어폰" required minLength={2} maxLength={80} />
              </label>
              <label className="form-field">{isLost ? "분실일" : "습득일"}
                <input name="event_date" type="date" required />
              </label>
            </div>}
            {!isLost && <label className="form-field">{isMatch ? "기억나는 특징" : "비공개 식별 특징"}
              <textarea name="features" placeholder="예: 손잡이에 별 스티커" rows={4} required minLength={2} maxLength={500} />
            </label>}
            {isLost && <label className="consent-box">
              <input type="checkbox" name="consent_to_publish" />
              <span><strong>공개 분실글 목록에 표시하는 데 동의해요.</strong>
                <span>동의하면 물건 이름, 종류, 동네, 날짜, 상태가 공개됩니다.</span></span>
            </label>}
          </fieldset>
          {error && <p role="alert" className="input-error">{error}</p>}
          {isMatch && outcome && <div className={`match-outcome${outcome.candidate ? " has-candidate" : ""}`} role="status">
            <strong>데모 결과</strong><p>{outcome.message}</p>
          </div>}
          <div className="form-actions">
            <Link className="secondary-button" href="/">분실글 탐색</Link>
            <button className="primary-button" type="submit" disabled={busy || loading || locationsError || !locations.length}>
              {busy ? (isMatch ? "확인 중…" : "등록 중…") : settings.action}
            </button>
          </div>
        </form>
      )}
    </main>
  );
}
