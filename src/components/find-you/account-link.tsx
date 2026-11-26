"use client";

import { UserRound } from "lucide-react";
import Link from "next/link";
import { useSession } from "@/hooks/use-session";

export function AccountLink() {
  const session = useSession();

  return (
    <Link className="nav-link account-link" href="/login">
      <UserRound size={17} aria-hidden />
      {session?.user ? "내 계정" : "로그인"}
    </Link>
  );
}
