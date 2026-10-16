/**
 * Cockpit 聚合端点 API 封装
 * 端点契约：docs/api/cockpit-endpoint.md
 */
import { getJson } from "@/api/http";
import type {
  CockpitQuery,
  CockpitResponse,
  CounterfactualResponse,
} from "@/types/cockpit";

/**
 * GET /api/v1/cockpit/student/{user_id}
 * 一次取回 profile/kg/forecast/attribution/cov/debate/safety/ledger 8 子块。
 * 任一子块失败时整体仍 200，子块内附 error 字段（前端按 error 降级渲染）。
 */
export function fetchCockpit(userId: string, query?: CockpitQuery) {
  return getJson<CockpitResponse>(
    `/api/v1/cockpit/student/${encodeURIComponent(userId)}`,
    query as Record<string, string | number | boolean | undefined> | undefined,
  );
}

/**
 * GET /api/v1/cockpit/schema
 * 自描述端点（查询参数与字段说明），开发期参考用。
 */
export function fetchCockpitSchema() {
  return getJson<Record<string, unknown>>("/api/v1/cockpit/schema");
}

/**
 * GET /api/v1/cognitive/counterfactual
 * P1.4 反事实独立端点（baseline vs recommended 双曲线）。
 */
export function fetchCounterfactual(params: {
  user_id: string;
  kp_id: string;
  horizon_days?: number;
}) {
  return getJson<CounterfactualResponse>("/api/v1/cognitive/counterfactual", {
    user_id: params.user_id,
    kp_id: params.kp_id,
    horizon_days: params.horizon_days ?? 14,
  });
}
