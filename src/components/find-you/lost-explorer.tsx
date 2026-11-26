"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useLocations } from "@/hooks/use-locations";
import { categories, type Category, type LostItem, requestApi } from "@/lib/find-you";
import { AccountLink } from "./account-link";
import { NeighborhoodPicker, regionPrefix } from "./neighborhood-picker";
import styles from "./lost-explorer.module.css";

const defaults = { q: "", region: "", location_id: "" };
const categoryGroups: { label: string; categories: Category[] }[] = [
  { label: "전자기기", categories: ["electronics"] },
  { label: "지갑·카드", categories: ["wallet", "card"] },
  { label: "열쇠·소지품", categories: ["accessory"] },
  { label: "가방·의류", categories: ["bag", "clothing"] },
  { label: "기타", categories: ["other"] },
];
const navigation = [
  { href: "/", label: "홈", icon: "home" },
  { href: "/match", label: "특징으로 찾기", icon: "manage_search" },
  { href: "/my-items", label: "내 글", icon: "article" },
];

type SearchRequest = { filters: typeof defaults };
type SearchResult = { request: SearchRequest; items: LostItem[] | null };

function Symbol({ children }: { children: string }) {
  return <span className={styles.symbol} aria-hidden="true">{children}</span>;
}

function HomeNavigation({ mobile = false }: { mobile?: boolean }) {
  return (
    <nav className={mobile ? styles.bottomNav : styles.topNav} aria-label="주요 메뉴">
      {navigation.map(({ href, label, icon }) => (
        <Link key={href} href={href} aria-current={href === "/" ? "page" : undefined}>
          {mobile && <Symbol>{icon}</Symbol>}
          {label}
        </Link>
      ))}
    </nav>
  );
}

function dateLabel(value: string, today: string) {
  if (value === today) return "오늘";
  if (Date.parse(today) - Date.parse(value) === 86_400_000) return "어제";
  const [year, month, day] = value.split("-");
  return today.startsWith(year + "-") ? `${Number(month)}.${day}` : `${year}.${month}.${day}`;
}

function LostStatus({ status }: { status: LostItem["status"] }) {
  return <span className={styles.status} data-state={status}>{status === "searching" ? "찾는 중" : "찾음 완료"}</span>;
}

function LostCard({ item, today, onOpen }: { item: LostItem; today: string; onOpen: () => void }) {
  const category = categoryGroups.find((group) => group.categories.includes(item.category))?.label;
  return (
    <li>
      <button className={styles.card} type="button" onClick={onOpen} aria-haspopup="dialog">
        <span className={styles.cardContent}>
          <span className={styles.cardMeta}>
            <span className={styles.cardCategory}>{category}</span>
            <span>{item.location.dong}</span>
            <span><time dateTime={item.event_date}>{dateLabel(item.event_date, today)}</time></span>
          </span>
          <span className={styles.cardTitle}>{item.title}</span>
        </span>
        <span className={styles.cardAction}>
          <LostStatus status={item.status} />
          <Symbol>chevron_right</Symbol>
        </span>
      </button>
    </li>
  );
}

export function LostExplorer({ initialItems, date, fontClasses }: {
  initialItems: LostItem[] | null;
  date: string;
  fontClasses: string;
}) {
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState<(typeof categoryGroups)[number] | null>(null);
  const [request, setRequest] = useState<SearchRequest>();
  const [result, setResult] = useState<SearchResult>();
  const [selected, setSelected] = useState<LostItem>();
  const dialog = useRef<HTMLDialogElement>(null);
  const keywordInput = useRef<HTMLInputElement>(null);
  const { locations, loading: locationsLoading, error: locationsError, retry: retryLocations } = useLocations();
  const filters = request?.filters ?? defaults;

  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const params = new URLSearchParams(Object.entries(request.filters).filter(([, value]) => value));
    requestApi<LostItem[]>(`lost-items?${params}`, { signal: controller.signal })
      .then((items) => {
        if (!controller.signal.aborted) setResult({ request, items });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ request, items: null });
      });
    return () => controller.abort();
  }, [request]);

  const searchTerm = keyword.trim();
  useEffect(() => {
    if (searchTerm === filters.q) return;
    const timer = window.setTimeout(() => {
      setRequest((previous) => ({ filters: { ...(previous?.filters ?? defaults), q: searchTerm } }));
    }, 280);
    return () => window.clearTimeout(timer);
  }, [searchTerm, filters.q]);

  useEffect(() => {
    if (selected) dialog.current?.showModal();
  }, [selected]);

  const current = !request ? { items: initialItems } : result?.request === request ? result : undefined;
  const items = category ? current?.items?.filter((item) => category.categories.includes(item.category)) : current?.items;
  const neighborhood = filters.region ? `${regionPrefix}${filters.region}` : filters.location_id;
  const neighborhoodName = filters.region || locations.find(({ location_id }) => location_id === filters.location_id)?.dong;
  const hasFilters = Boolean(neighborhood || category || filters.q);
  const resultsSubject = [neighborhoodName, category?.label].filter(Boolean).join(" ");
  const resultsTitle = filters.q ? `‘${filters.q}’ 검색 결과` : `${resultsSubject ? resultsSubject + " " : ""}공개 분실글`;

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRequest({ filters: { ...filters, q: searchTerm } });
  }

  function reset() {
    setKeyword("");
    setCategory(null);
    setRequest({ filters: defaults });
    keywordInput.current?.focus();
  }

  function changeNeighborhood(value: string) {
    const isRegion = value.startsWith(regionPrefix);
    setRequest({ filters: {
      q: searchTerm, region: isRegion ? value.slice(regionPrefix.length) : "", location_id: isRegion ? "" : value,
    } });
  }

  return (
    <div className={`${styles.home} ${fontClasses}`}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.headerStart}>
            <Link className={styles.brand} href="/" aria-label="Find you 홈">Find you</Link>
            <div className={styles.neighborhood}>
              <label className="sr-only" htmlFor="filter-neighborhood">동네</label>
              <NeighborhoodPicker id="filter-neighborhood" value={neighborhood} locations={locations}
                placeholder={locationsLoading ? "불러오는 중" : "전체 동네"} includeRegions compact
                disabled={locationsLoading || locationsError} onChange={changeNeighborhood} />
            </div>
          </div>
          <HomeNavigation />
          <AccountLink className={styles.account} showIcon={false} />
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.controls} aria-label="검색, 필터 및 등록">
          <form className={styles.search} role="search" aria-label="공개 분실글" onSubmit={search}>
            <Symbol>search</Symbol>
            <label className="sr-only" htmlFor="keyword">공개 분실글 검색어</label>
            <input ref={keywordInput} id="keyword" name="q" type="search" value={keyword} maxLength={100}
              enterKeyHint="search" placeholder="물건 이름이나 특징 검색" onChange={(event) => setKeyword(event.target.value)} />
            <button type="submit">검색</button>
          </form>

          <div className={styles.filters}>
            <div className={styles.chips} role="group" aria-label="물건 종류">
              <button type="button" aria-pressed={!category} onClick={() => setCategory(null)}>전체</button>
              {categoryGroups.map((group) => (
                <button type="button" key={group.label} aria-pressed={category === group} onClick={() => setCategory(group)}>
                  {group.label}
                </button>
              ))}
            </div>
            <Link className={styles.featureLink} href="/match"><Symbol>manage_search</Symbol>비공개 습득물 특징으로 찾기</Link>
          </div>

          <div className={styles.registration}>
            <Link href="/lost/new"><Symbol>add_circle</Symbol>분실물 등록</Link>
            <Link href="/found/new"><Symbol>volunteer_activism</Symbol>습득물 등록</Link>
          </div>
        </section>
        {locationsError && <p className={styles.locationError} role="alert">
          동네 목록을 불러오지 못했습니다. <button className="text-button" type="button" onClick={retryLocations}>다시 불러오기</button>
        </p>}

        <section aria-labelledby="results-heading">
          <div className={styles.resultsHeading}>
            <h1 id="results-heading">{resultsTitle}</h1>
            <div className={styles.resultsTools}>
              {(hasFilters || keyword) && <button type="button" onClick={reset}>초기화</button>}
              <span role="status">{items && `총 ${items.length}건`}</span>
            </div>
          </div>
          <div aria-busy={!current}>
            {!current && <p className={styles.resultMessage} role="status">분실글을 불러오는 중입니다.</p>}
            {current?.items === null && <div className={styles.resultMessage} role="alert">
              <p>분실글 검색에 실패했습니다.</p>
              <button type="button" className="secondary-button" onClick={() => setRequest({ filters })}>다시 검색</button>
            </div>}
            {items?.length === 0 && <div className={styles.resultMessage} role="status">
              <p>{hasFilters ? "조건에 맞는 분실글이 없어요." : "등록된 공개 분실글이 없어요."}</p>
              {hasFilters && <button type="button" className="secondary-button" onClick={reset}>검색·필터 초기화</button>}
            </div>}
            {items && items.length > 0 && (
              <ul className={styles.cards} role="list">
                {items.map((item) => <LostCard key={item.item_id} item={item} today={date} onOpen={() => setSelected(item)} />)}
              </ul>
            )}
          </div>
        </section>
      </main>

      <HomeNavigation mobile />
      <dialog ref={dialog} className={styles.details} aria-labelledby="lost-details-title" onClose={() => setSelected(undefined)}>
        {selected && <>
          <h2 id="lost-details-title">{selected.title}</h2>
          <LostStatus status={selected.status} />
          <dl>
            <div><dt>물건 종류</dt><dd>{categories[selected.category].label}</dd></div>
            <div><dt>동네</dt><dd>{selected.location.region} {selected.location.dong}</dd></div>
            <div><dt>분실일</dt><dd><time dateTime={selected.event_date}>{selected.event_date}</time></dd></div>
          </dl>
          <form method="dialog"><button className="secondary-button" type="submit">닫기</button></form>
        </>}
      </dialog>
    </div>
  );
}
