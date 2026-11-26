import type { Category } from "./find-you";

export type ClaimQuery = { location_id: string; category: string; features: string };

export type OwnedItem = {
  item_id: string;
  kind: "lost" | "found";
  title: string;
  category: Category;
  event_date: string;
  location_id: string;
  region: string;
  dong: string;
  features: string | null;
  status: "searching" | "held" | "returned";
  consent_to_publish: boolean;
  photo_positions: number[];
  locked: boolean;
};

export const claimLabels = {
  pending: "검토 대기",
  approved: "소유 확인 승인",
  rejected: "확인 종료",
  returned: "반환 완료",
};

export type Claim = {
  claim_id: string;
  category: Category;
  region: string;
  dong: string;
  proof: string;
  features: string;
  status: keyof typeof claimLabels;
  created_at: string;
  reply: string | null;
};

export type ReviewClaim = Claim & {
  claimant: string;
  approved_item_id: string | null;
  candidates: {
    item_id: string;
    title: string;
    features: string;
    event_date: string;
    photo_positions: number[];
  }[];
};
