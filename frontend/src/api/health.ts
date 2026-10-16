import { getJson } from "@/api/http";

export function getHealth() {
  return getJson<{ status: string }>("/healthz");
}
