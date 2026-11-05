import { notFound } from "next/navigation";
import { validateScene } from "@opendopa/shared";
import accident from "@opendopa/shared/fixtures/accident-0001.json";
import mapPoints from "@opendopa/shared/fixtures/map-points.json";
import mapPolygon from "@opendopa/shared/fixtures/map-polygon.json";
import mapRoute from "@opendopa/shared/fixtures/map-route.json";
import { StageDev } from "./StageDev";
import "./dev.css";

export const metadata = { title: "ステージの確認(開発用)" };

const files = {
  "accident-0001": accident,
  "map-points": mapPoints,
  "map-polygon": mapPolygon,
  "map-route": mapRoute,
};

/** 確認用ページ。本番ビルドでは出さない(404) */
export default function DevStagePage() {
  if (process.env.NODE_ENV === "production") notFound();

  const fixtures = Object.entries(files).map(([name, json]) => {
    const result = validateScene(json);
    if (!result.ok) throw new Error(`フィクスチャ ${name} が不正: ${result.errors.join(", ")}`);
    return { name, scene: result.scene };
  });

  return <StageDev fixtures={fixtures} />;
}
