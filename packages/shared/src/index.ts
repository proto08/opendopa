// 生成した型(`mise run gen-types`)をまとめて公開する。手で型を書かないこと。
export type * from "./generated/scene.schema";
export { validateScene } from "./validate";
export type { SceneValidation } from "./validate";
