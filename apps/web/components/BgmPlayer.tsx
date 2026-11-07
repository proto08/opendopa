"use client";

import { useEffect, useRef, useState } from "react";
import { Bgm } from "@/lib/bgm";
import "./bgm.css";

const STORAGE_KEY = "opendopa.bgm.muted";

/** BGM を流し、画面の左下にミュートのボタンを出す。タブが隠れている間は止める */
export function BgmPlayer({ url, volume }: { url: string; volume: number }) {
  const bgmRef = useRef<Bgm | null>(null);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    let initialMuted = false;
    try {
      initialMuted = localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      // 保存できなくても再生は続ける
    }
    setMuted(initialMuted);
    const bgm = new Bgm(new Audio(), window, url, volume);
    bgm.setMuted(initialMuted);
    bgm.start();
    bgmRef.current = bgm;
    const onVisibility = () => {
      if (document.visibilityState === "hidden") bgm.stop();
      else bgm.start();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      bgm.stop();
      bgmRef.current = null;
    };
  }, [url, volume]);

  const toggle = () => {
    const next = !muted;
    setMuted(next);
    bgmRef.current?.setMuted(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // 保存できなくても切り替えは効く
    }
  };

  return (
    <button
      type="button"
      className="bgmToggle"
      aria-pressed={muted}
      aria-label={muted ? "BGMをオンにする" : "BGMをミュートする"}
      onClick={toggle}
    >
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M9 18V6l10-2v12" />
        <circle cx="7" cy="18" r="2" fill="currentColor" />
        <circle cx="17" cy="16" r="2" fill="currentColor" />
        {muted ? <path d="M3 3l18 18" /> : null}
      </svg>
      <span>BGM {muted ? "オフ" : "オン"}</span>
    </button>
  );
}
