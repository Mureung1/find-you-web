"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";
import { useLocations } from "@/hooks/use-locations";
import { useSession } from "@/hooks/use-session";
import { categories, requestApi } from "@/lib/find-you";
import { claimLabels, type Claim, type OwnedItem } from "@/lib/management";
import { NeighborhoodPicker } from "./neighborhood-picker";
import { PrivatePhotos } from "./private-photos";
import { CategorySelect } from "./select-fields";
import styles from "./management.module.css";

function EditForm({ item, busy, onSave, onCancel }: {
  item: OwnedItem;
  busy: boolean;
  onSave: (data: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const { locations, loading, error, retry } = useLocations();
  const [locationId, setLocationId] = useState(item.location_id);
  const fieldId = "edit-neighborhood-" + item.item_id;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!locationId || busy) return;
    const data = new FormData(event.currentTarget);
    const common = {
      kind: item.kind, location_id: locationId, title: data.get("title"),
      category: data.get("category"), event_date: data.get("event_date"),
    };
    onSave(item.kind === "lost"
      ? { ...common, consent_to_publish: data.has("consent"), status: data.get("status") }
      : { ...common, features: data.get("features") });
  }

  return (
    <form className={styles.inlineForm} onSubmit={submit} aria-busy={busy}>
      <fieldset disabled={busy}>
        <div className="field-grid">
          <div className="form-field">
            <label htmlFor={fieldId}>동네</label>
            <NeighborhoodPicker id={fieldId} value={locationId} locations={locations} onChange={setLocationId}
              placeholder={loading ? "동네 불러오는 중" : "예: 마포구 성산동"} disabled={loading || error} required />
          </div>
          <label className="form-field">종류
            <CategorySelect name="category" defaultValue={item.category} placeholder="종류 선택" required />
          </label>
        </div>
        {error && <p role="alert">동네를 불러오지 못했습니다. <button className="text-button" type="button" onClick={retry}>다시 불러오기</button></p>}
        <div className="field-grid">
          <label className="form-field">물건 이름
            <input name="title" defaultValue={item.title} minLength={2} maxLength={80} required />
          </label>
          <label className="form-field">{item.kind === "lost" ? "분실일" : "습득일"}
            <input name="event_date" type="date" defaultValue={item.event_date} required />
          </label>
        </div>
        {item.kind === "lost" ? (
          <>
            <label className="form-field">상태
              <CategoryStatus defaultValue={item.status === "returned" ? "returned" : "searching"} />
            </label>
            <label className="consent-box"><input name="consent" type="checkbox" defaultChecked={item.consent_to_publish} />
              공개 분실글 목록에 표시하는 데 동의해요.</label>
          </>
        ) : (
          <label className="form-field">비공개 식별 특징
            <textarea name="features" defaultValue={item.features ?? ""} minLength={2} maxLength={500} required rows={3} />
          </label>
        )}
      </fieldset>
      <div className={styles.actions}>
        <button type="submit" className="primary-button" disabled={busy || loading || error || !locationId}>수정 저장</button>
        <button type="button" className="secondary-button" disabled={busy} onClick={onCancel}>취소</button>
      </div>
    </form>
  );
}

function CategoryStatus({ defaultValue }: { defaultValue: string }) {
  return (
    <select className="secondary-button" name="status" defaultValue={defaultValue}>
      <option value="searching">찾는 중</option>
      <option value="returned">찾았어요</option>
    </select>
  );
}

function ItemCard({ item, reload }: { item: OwnedItem; reload: () => void }) {
  const [mode, setMode] = useState<"view" | "edit" | "delete">("view");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = "my/items/" + encodeURIComponent(item.item_id);

  async function change(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
      setMode("view");
      reload();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "저장하지 못했어요.");
    } finally {
      setBusy(false);
    }
  }

  function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const file = new FormData(form).get("photo");
    if (!(file instanceof File) || !file.size) {
      setError("추가할 사진을 선택해 주세요.");
      return;
    }
    void change(async () => {
      await requestApi(path + "/photos", { method: "POST", headers: { "Content-Type": file.type }, body: file });
      form.reset();
    });
  }

  const status = item.status === "returned" ? (item.kind === "lost" ? "찾았어요" : "반환 완료")
    : item.status === "held" ? "보관 중" : "찾는 중";

  return (
    <li id={item.item_id} className={["form-panel", styles.panel].join(" ")}>
      <div>
        <h3>{item.title}</h3>
        <p className={styles.meta}>{item.kind === "lost" ? "분실물" : "습득물"} · {categories[item.category].label} · {status}</p>
        <p className={styles.meta}>{item.region} {item.dong} · <time dateTime={item.event_date}>{item.event_date}</time></p>
        <p className={styles.meta}>{item.consent_to_publish ? "공개" : "비공개"}</p>
      </div>
      {error && <p role="alert" className="input-error">{error}</p>}
      {item.locked && <p className={styles.meta}>소유 확인이 승인된 게시글입니다. 반환을 마친 뒤 수정할 수 있어요.</p>}
      {mode === "edit" ? (
        <EditForm item={item} busy={busy} onCancel={() => setMode("view")}
          onSave={(data) => void change(() => requestApi(path, {
            method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
          }))} />
      ) : mode === "delete" ? (
        <>
          <p>이 게시글과 첨부 사진을 삭제할까요?</p>
          <div className={styles.actions}>
            <button type="button" className="secondary-button" disabled={busy} onClick={() => setMode("view")}>취소</button>
            <button type="button" className="primary-button" disabled={busy}
              onClick={() => void change(() => requestApi(path, { method: "DELETE" }))}>게시글 삭제</button>
          </div>
        </>
      ) : (
        <>
          {item.kind === "found" && (
            <>
              <div className={styles.details}><p>{item.features}</p></div>
              <PrivatePhotos itemId={item.item_id} positions={item.photo_positions} removing={busy}
                onRemove={item.locked ? undefined : (position) =>
                  void change(() => requestApi(path + "/photos/" + position, { method: "DELETE" }))} />
              {!item.locked && item.photo_positions.length < 4 && (
                <form className={styles.upload} onSubmit={upload} aria-busy={busy}>
                  <label>비공개 사진
                    <input type="file" name="photo" accept="image/jpeg,image/png,image/webp" disabled={busy} required />
                  </label>
                  <button type="submit" className="secondary-button" disabled={busy}>사진 추가</button>
                </form>
              )}
            </>
          )}
          {!item.locked && (
            <div className={styles.actions}>
              <button type="button" className="secondary-button" disabled={busy} onClick={() => setMode("edit")}>수정</button>
              <button type="button" className="quiet-button" disabled={busy} onClick={() => setMode("delete")}>삭제</button>
            </div>
          )}
        </>
      )}
    </li>
  );
}

type Content = { items: OwnedItem[]; claims: Claim[] };

export function MyItemsPanel() {
  const session = useSession();
  const userId = session?.user?.user_id;
  const [version, refresh] = useState(0);
  const [loaded, setLoaded] = useState<{ owner: string; data: Content | null }>();
  const current = loaded?.owner === userId ? loaded?.data : undefined;

  useEffect(() => {
    if (!userId) return;
    const controller = new AbortController();
    Promise.all([
      requestApi<OwnedItem[]>("my/items", { signal: controller.signal }),
      requestApi<Claim[]>("claims/mine", { signal: controller.signal }),
    ]).then(([items, claims]) => {
      if (!controller.signal.aborted) setLoaded({ owner: userId, data: { items, claims } });
    }).catch(() => {
      if (!controller.signal.aborted) setLoaded({ owner: userId, data: null });
    });
    return () => controller.abort();
  }, [userId, version]);

  const reload = () => refresh((value) => value + 1);
  if (session === undefined) return <p role="status">로그인 상태를 확인하고 있어요.</p>;
  if (session === null) return <p role="alert">로그인 상태를 불러오지 못했습니다.</p>;
  if (!userId) return <Link className="primary-button" href="/login">로그인</Link>;
  if (current === undefined) return <p role="status">내 글을 불러오고 있어요.</p>;
  if (current === null) return <p role="alert">내 글을 불러오지 못했습니다. <button className="text-button" onClick={reload}>다시 시도</button></p>;

  return (
    <>
      {session.user?.is_admin && <Link href="/claims/review" className="secondary-button">소유 확인 검토</Link>}
      <section className={styles.section} aria-labelledby="my-posts">
        <h2 id="my-posts">등록한 글</h2>
        {current.items.length ? <ul className={styles.list}>{current.items.map((item) =>
          <ItemCard key={item.item_id} item={item} reload={reload} />)}</ul> : <p>등록한 분실물이나 습득물이 없어요.</p>}
      </section>
      <section className={styles.section} aria-labelledby="my-claims">
        <h2 id="my-claims">소유 확인 요청</h2>
        {current.claims.length ? (
          <ul className={styles.list}>{current.claims.map((claim) => (
            <li key={claim.claim_id} className={["form-panel", styles.panel].join(" ")}>
              <h3>{claimLabels[claim.status]}</h3>
              <p className={styles.meta}>{claim.region} {claim.dong} · {categories[claim.category].label}</p>
              <div className={styles.details}><p>{claim.features}</p>{claim.reply && <p><strong>담당자 안내</strong> {claim.reply}</p>}</div>
            </li>
          ))}</ul>
        ) : <p>보낸 요청이 없어요.</p>}
      </section>
    </>
  );
}
