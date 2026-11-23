"use client";

import { CalendarDays, ChevronDown, LayoutGrid, MapPin, PackageSearch, RotateCcw, Search, TriangleAlert } from "lucide-react";
import Image from "next/image";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useLocations } from "@/hooks/use-locations";
import { categories, type Category, type Location, type LostItem, requestApi } from "@/lib/find-you";
import { NeighborhoodSelect, regionPrefix } from "./select-fields";
import styles from "./lost-explorer.module.css";

const defaults = { q: "", region: "", location_id: "", category: "" as Category | "" };
const categoryKeys = Object.keys(categories) as Category[];

type SearchRequest = { filters: typeof defaults };
type SearchResult = { request: SearchRequest; items: LostItem[] | null };

function LostCard({ item }: { item: LostItem }) {
  const { icon: Icon, label } = categories[item.category];
  const locationLabel = `${item.location.region} ${item.location.dong}`;
  const date = item.event_date.replaceAll("-", ". ");

  return (
    <li>
      <article className="lost-card">
        <div className={styles.cardVisual} data-category={item.category}>
          <Icon className={styles.cardIcon} size={50} strokeWidth={1.5} aria-hidden />
          <span className={`item-status ${item.status}`}>
            {item.status === "searching" ? "찾는 중" : "반환 완료"}
          </span>
        </div>
        <div className="item-content">
          <p className="item-category">{label}</p>
          <h3>{item.title}</h3>
          <div className="item-meta">
            <span><MapPin size={15} aria-hidden />{locationLabel}</span>
            <span><CalendarDays size={15} aria-hidden /><time dateTime={item.event_date}>{date} 분실</time></span>
          </div>
        </div>
      </article>
    </li>
  );
}

export function LostExplorer({ initialItems, initialLocations }: {
  initialItems: LostItem[] | null;
  initialLocations: Location[] | null;
}) {
  const [keyword, setKeyword] = useState("");
  const [request, setRequest] = useState<SearchRequest>();
  const [result, setResult] = useState<SearchResult>();
  const [categoriesOpen, setCategoriesOpen] = useState(true);
  const keywordInput = useRef<HTMLInputElement>(null);
  const { locations, loading: locationsLoading, error: locationsError, retry: retryLocations } = useLocations(initialLocations);
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

  const current = !request ? { items: initialItems } : result?.request === request ? result : undefined;
  const neighborhood = filters.region ? `${regionPrefix}${filters.region}` : filters.location_id;
  const neighborhoodName = filters.region || locations.find(({ location_id }) => location_id === filters.location_id)?.dong;
  const hasFilters = Boolean(neighborhood || filters.category || filters.q);
  const resultsSubject = [neighborhoodName, filters.category && categories[filters.category].label].filter(Boolean).join(" ");
  const resultsTitle = filters.q ? `‘${filters.q}’ 검색 결과` : `${resultsSubject || "공개"} 분실글`;

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRequest({ filters: { ...filters, q: keyword.trim() } });
  }

  function reset() {
    setKeyword("");
    setRequest({ filters: defaults });
    keywordInput.current?.focus();
  }

  function changeNeighborhood(value: string) {
    const isRegion = value.startsWith(regionPrefix);
    const region = isRegion ? value.slice(regionPrefix.length) : "";
    const location_id = isRegion ? "" : value;
    setRequest({ filters: { ...filters, region, location_id } });
  }

  function changeCategory(category: Category | "") {
    if (category !== filters.category) setRequest({ filters: { ...filters, category } });
  }

  return (
    <main className="shell explorer">
      <section className={styles.hero} aria-labelledby="search-heading">
        <div className={styles.heroContent}>
          <h1 id="search-heading">우리 동네 <span>분실물 찾기</span></h1>
          <p className={styles.heroDescription}>동네를 고르고 잃어버린 물건을 찾아보세요.</p>
        </div>
        <div className={styles.heroArt} aria-hidden="true">
          <Image src="/images/neighborhood-search.webp" alt="" width={960} height={640} unoptimized loading="eager" />
        </div>
      </section>

      <form className={styles.searchBar} role="search" aria-label="공개 분실글" onSubmit={search}>
        <div className={styles.neighborhood}>
          <label className="sr-only" htmlFor="filter-neighborhood">동네</label>
          <NeighborhoodSelect id="filter-neighborhood" value={neighborhood} locations={locations}
            placeholder={locationsLoading ? "동네 불러오는 중" : "전체 동네"} includeRegions
            disabled={locationsLoading || locationsError} onChange={(event) => changeNeighborhood(event.target.value)} />
        </div>
        <div className={styles.searchKeyword}>
          <Search size={19} aria-hidden />
          <label className="sr-only" htmlFor="keyword">공개 분실글 검색어</label>
          <input ref={keywordInput} id="keyword" name="q" type="search" value={keyword} maxLength={100}
            placeholder="예: 무선 이어폰, 검정 지갑" onChange={(event) => setKeyword(event.target.value)} />
          <button className="primary-button" type="submit">검색</button>
        </div>
      </form>
      {locationsError && <p className={styles.locationError} role="alert">
        동네 목록을 불러오지 못했습니다. <button className="text-button" type="button" onClick={retryLocations}>다시 불러오기</button>
      </p>}

      <div className={styles.catalog}>
        <aside className={styles.categories} aria-labelledby="category-heading">
          <div className={styles.categoriesHeading}>
            <h2 id="category-heading">물건 종류</h2>
            <button className={styles.categoryToggle} type="button" aria-expanded={categoriesOpen}
              aria-controls="category-options" onClick={() => setCategoriesOpen(!categoriesOpen)}>
              {categoriesOpen ? "접기" : "펼치기"}<ChevronDown size={16} aria-hidden />
            </button>
          </div>
          <div id="category-options" className={styles.categoryList} data-expanded={categoriesOpen} role="group" aria-labelledby="category-heading">
            <button className={styles.categoryButton} type="button" aria-pressed={!filters.category} onClick={() => changeCategory("")}>
              <LayoutGrid size={18} strokeWidth={1.8} aria-hidden />전체
            </button>
            {categoryKeys.map((category) => {
              const { icon: Icon, label } = categories[category];
              return <button className={styles.categoryButton} type="button" key={category} aria-pressed={filters.category === category}
                onClick={() => changeCategory(category)}>
                <Icon size={18} strokeWidth={1.8} aria-hidden />{label}
              </button>;
            })}
          </div>
        </aside>

        <section className={styles.results} aria-labelledby="results-heading">
          <div className="results-heading">
            <div className="results-title">
              <h2 id="results-heading">{resultsTitle}</h2>
              <span role="status" className="result-count">{current?.items && `${current.items.length}건`}</span>
            </div>
            <div className={styles.resultsTools}>
              {(hasFilters || keyword) && <button className="quiet-button" type="button" onClick={reset}>
                <RotateCcw size={15} aria-hidden />초기화
              </button>}
              {current?.items && current.items.length > 0 && <span className="sort-label">최근 분실일순</span>}
            </div>
          </div>
          <div aria-busy={!current}>
            {!current && <p className="result-message" role="status">분실글을 불러오는 중입니다.</p>}
            {current?.items === null && <div className="result-message" role="alert">
              <TriangleAlert size={25} aria-hidden />
              <p>분실글 검색에 실패했습니다.</p>
              <button type="button" className="secondary-button" onClick={() => setRequest({ filters })}>다시 검색</button>
            </div>}
            {current?.items?.length === 0 && <div className="result-message" role="status">
              <PackageSearch size={30} aria-hidden />
              <p>{hasFilters ? "조건에 맞는 분실글이 없어요." : "등록된 공개 분실글이 없어요."}</p>
              <button type="button" className="secondary-button" onClick={reset}>검색·필터 초기화</button>
            </div>}
            {current?.items && current.items.length > 0 && (
              <ul className={`result-list ${styles.cardGrid}`} role="list">
                {current.items.map((item) => <LostCard key={item.item_id} item={item} />)}
              </ul>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
