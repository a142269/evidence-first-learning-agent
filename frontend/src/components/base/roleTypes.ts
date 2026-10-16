export type RoleKind = "student" | "teacher" | "admin";

export interface RoleCard {
  kind: RoleKind;
  index: string;
  title: string;
  subtitle: string;
  account: string;
}
