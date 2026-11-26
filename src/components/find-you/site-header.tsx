import { LocateFixed, MapPin, Plus, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { AccountLink } from "./account-link";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link href="/" className="brand" aria-label="Find you 홈">
          <span className="brand-mark"><MapPin size={23} strokeWidth={2.4} aria-hidden /></span>
          <span>Find <span className="brand-accent">you</span></span>
        </Link>
        <AccountLink />
        <nav className="header-nav" aria-label="주요 메뉴">
          <Link href="/match" className="nav-link"><LocateFixed size={17} aria-hidden />특징으로 찾기</Link>
          <Link href="/found/new" className="nav-link"><ShieldCheck size={17} aria-hidden />습득물 비공개 등록</Link>
          <Link href="/lost/new" className="nav-link nav-primary"><Plus size={17} aria-hidden />분실물 등록</Link>
        </nav>
      </div>
    </header>
  );
}
