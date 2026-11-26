import type { Metadata } from "next";
import { GoogleLoginPanel } from "@/components/find-you/google-login";
import styles from "@/components/find-you/google-login.module.css";

export const metadata: Metadata = {
  title: "로그인",
  referrer: "no-referrer-when-downgrade",
};

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;

  return (
    <main className={`shell ${styles.page}`} aria-labelledby="login-heading">
      <h1 id="login-heading" className={styles.title}>로그인</h1>
      <GoogleLoginPanel googleError={error === "google"} />
    </main>
  );
}
