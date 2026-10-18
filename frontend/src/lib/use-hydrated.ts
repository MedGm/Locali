import { useQuery, type QueryKey, type UseQueryOptions } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

const noSubscription = () => () => {};

// False during the server render and the first browser render, true after.
export function useHydrated() {
  return useSyncExternalStore(noSubscription, () => true, () => false);
}

// useQuery for page bodies. The sidebar fetches some of the same data, and with streaming it can
// arrive before a page hydrates; the server rendered that page without it. Until hydration this
// reports no data, not loading and no error, exactly like the server did.
export function useApiQuery<T>(options: UseQueryOptions<T, Error, T, QueryKey>) {
  const query = useQuery(options);
  const hydrated = useHydrated();
  return hydrated ? query : { ...query, data: undefined, isLoading: false, isError: false, error: null };
}
