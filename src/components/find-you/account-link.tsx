"use client";

import { UserRound } from "lucide-react";
import Link from "next/link";
import { useSession } from "@/hooks/use-session";

export function AccountLink({ className = "nav-link account-link", showIcon = true }: {
  className?: string;
  showIcon?: boolean;
}) {
  const session = useSession();

  return (
    <Link className={className} href="/login">
      {showIcon && <UserRound size={17} aria-hidden />}
      {session?.user ? "내 계정" : "로그인"}
    </Link>
  );
}
