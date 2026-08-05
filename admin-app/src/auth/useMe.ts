import { useQuery } from "@tanstack/react-query";
import { get, ApiError } from "@/lib/api";
import type { Me } from "@/lib/types";

/** Loads the current session from /api/auth/me. Never retries on 401. */
export function useMe() {
  return useQuery<Me>({
    queryKey: ["me"],
    queryFn: () => get<Me>("/api/auth/me"),
    retry: (count, err) => !(err instanceof ApiError && err.status === 401) && count < 1,
    staleTime: 5 * 60 * 1000,
  });
}
