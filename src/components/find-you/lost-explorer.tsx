"use client";

import { CalendarDays, ChevronDown, Compass, MapPin, PackageSearch, RotateCcw, Search, SlidersHorizontal, TriangleAlert } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useLocations } from "@/hooks/use-locations";
import { categories, type Location, type LostItem, requestApi } from "@/lib/find-you";
import { CategorySelect, NeighborhoodSelect, regionPrefix } from "./select-fields";

const defaults = { q: "", region: "", location_id: "", category: "" };

type SearchRequest = { filters: typeof defaults };
type SearchResult = { request: SearchRequest; items: LostItem[] | null };

function LostCard({ item }: { item: LostItem }) {
  const { icon: Icon, label } = categories[item.category];
  const locationLabel = `${item.location.region} ${item.location.dong}`;
  const date = item.event_date.replaceAll("-", ". ");

  return (
    <li>
      <article className="lost-card">
        <div className={`item-icon item-icon-${item.category}`}><Icon size={27} strokeWidth={1.7} aria-hidden /></div>
        <div className="item-content">
          <p className="item-category">{label}</p>
          <h3>{item.title}</h3>
          <div className="item-meta">
            <span><MapPin size={15} aria-hidden />{locationLabel}</span>
            <span><CalendarDays size={15} aria-hidden /><time dateTime={item.event_date}>{date} 분실</time></span>
          </div>
        </div>
        <span className={`item-status ${item.status}`}>
          {item.status === "searching" ? "찾는 중" : "반환 완료"}
        </span>
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
  const [filtersOpen, setFiltersOpen] = useState(false);
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

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRequest({ filters: { ...filters, q: keyword.trim() } });
  }

  function reset() {
    setKeyword("");
    setRequest({ filters: defaults });
  }

  function changeNeighborhood(value: string) {
    const isRegion = value.startsWith(regionPrefix);
    const region = isRegion ? value.slice(regionPrefix.length) : "";
    const location_id = isRegion ? "" : value;
    setRequest({ filters: { ...filters, region, location_id } });
  }

  return (
    <main className="shell explorer">
      <section className="search-hero" aria-labelledby="search-heading">
        <div className="hero-content">
          <h1 id="search-heading">분실물 찾기</h1>
          <p>동네에서 잃어버린 물건을 찾아보세요.</p>
          <form className="search-form" role="search" onSubmit={search}>
            <Search className="search-icon" size={21} aria-hidden />
            <label className="sr-only" htmlFor="keyword">공개 분실글 검색어</label>
            <input id="keyword" name="q" type="search" value={keyword} maxLength={100}
              placeholder="예: 이어폰, 연남동" onChange={(event) => setKeyword(event.target.value)} />
            <button className="primary-button" type="submit">검색</button>
          </form>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="map-disk map-disk-outer" />
          <div className="map-disk map-disk-inner" />
          <div className="map-route" />
          <span className="map-pin"><MapPin size={57} strokeWidth={1.6} /></span>
          <span className="map-compass"><Compass size={25} strokeWidth={1.6} /></span>
        </div>
      </section>

      <section className="filter-section" aria-label="검색 필터">
        <div className={`filter-bar${filtersOpen ? " is-open" : ""}`}>
          <div className="filter-control">
            <label htmlFor="filter-neighborhood">동네</label>
            <NeighborhoodSelect id="filter-neighborhood" value={neighborhood} locations={locations}
              placeholder="전체 동네" includeRegions disabled={locationsLoading || locationsError}
              onChange={(event) => changeNeighborhood(event.target.value)} />
          </div>
          <button className="filter-toggle" type="button" aria-expanded={filtersOpen} aria-controls="filter-options"
            aria-label={filters.category ? "필터, 물건 종류 적용 중" : undefined}
            onClick={() => setFiltersOpen(!filtersOpen)}>
            <SlidersHorizontal size={18} aria-hidden /> 필터 {filters.category && <span className="filter-indicator" aria-hidden />}
            <ChevronDown className="filter-toggle-chevron" size={17} aria-hidden />
          </button>
          <div className="filter-options" id="filter-options">
            <div className="filter-control">
              <label htmlFor="filter-category">물건 종류</label>
              <CategorySelect id="filter-category" value={filters.category} placeholder="전체 물건 종류"
                onChange={(event) => setRequest({ filters: { ...filters, category: event.target.value } })} />
            </div>
            <button type="button" className="quiet-button filter-reset" onClick={reset} disabled={!neighborhood && !filters.category && !keyword && !filters.q}>
              <RotateCcw size={15} aria-hidden /> 초기화
            </button>
          </div>
        </div>
        {locationsLoading && <p className="filter-message" role="status">동네 목록을 불러오는 중입니다.</p>}
        {locationsError && <p className="filter-message" role="alert">
          동네 목록을 불러오지 못했습니다. <button className="text-button" onClick={retryLocations}>다시 불러오기</button>
        </p>}
      </section>

      <section className="results" aria-labelledby="results-heading" aria-busy={!current}>
        <div className="results-heading">
          <div className="results-title">
            <h2 id="results-heading">{filters.q ? `‘${filters.q}’ 검색 결과` : "공개 분실글"}</h2>
            {current?.items && <span role="status" className="result-count">{current.items.length}건</span>}
          </div>
          {current?.items && current.items.length > 0 && <span className="sort-label">최근 분실일순</span>}
        </div>
        {!current && <p className="result-message" role="status">분실글을 불러오는 중입니다.</p>}
        {current?.items === null && <div className="result-message" role="alert">
          <TriangleAlert size={25} aria-hidden />
          <p>분실글 검색에 실패했습니다.</p>
          <button type="button" className="secondary-button" onClick={() => setRequest({ filters })}>다시 검색</button>
        </div>}
        {current?.items?.length === 0 && <div className="result-message" role="status">
          <PackageSearch size={30} aria-hidden />
          <p>{neighborhood || filters.category || filters.q ? "조건에 맞는 분실글이 없어요." : "등록된 공개 분실글이 없어요."}</p>
          <button type="button" className="secondary-button" onClick={reset}>검색·필터 초기화</button>
        </div>}
        {current?.items && current.items.length > 0 && (
          <ul className="result-list" role="list">{current.items.map((item) => <LostCard key={item.item_id} item={item} />)}</ul>
        )}
      </section>
    </main>
  );
}
