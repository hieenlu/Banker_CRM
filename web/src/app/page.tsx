"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function HomePage() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.ready) return;
    router.replace(auth.username ? "/clients" : "/login");
  }, [auth.ready, auth.username, router]);

  return (
    <div className="boot-screen">
      <p className="brand-mark">Banker CRM</p>
      <p className="muted">Loading desk…</p>
    </div>
  );
}
