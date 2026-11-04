import Ajv2020 from "ajv/dist/2020.js";
import schema from "../schema/scene.schema.json" with { type: "json" };
import type { Scene } from "./generated/scene.schema";

const ajv = new Ajv2020({ allErrors: true });
const validate = ajv.compile<Scene>(schema);

export type SceneValidation = { ok: true; scene: Scene } | { ok: false; errors: string[] };

/** JSON を Scene のスキーマで検証する。pipeline も同じ `schema/scene.schema.json` を読む。 */
export function validateScene(json: unknown): SceneValidation {
  if (validate(json)) return { ok: true, scene: json };
  return {
    ok: false,
    errors: (validate.errors ?? []).map((e) => `${e.instancePath || "/"} ${e.message}`),
  };
}
