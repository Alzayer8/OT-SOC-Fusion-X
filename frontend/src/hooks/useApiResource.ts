import { useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";

export type ResourceState<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; message: string; statusCode?: number; requestId?: string };

export function useApiResource<T>(
  key: string,
  loader: (signal: AbortSignal) => Promise<T>,
  refreshMilliseconds = 0,
): ResourceState<T> {
  const loaderRef = useRef(loader);
  const [state, setState] = useState<ResourceState<T>>({ status: "loading" });

  useEffect(() => {
    loaderRef.current = loader;
  }, [loader]);

  useEffect(() => {
    let mounted = true;
    let controller: AbortController | undefined;

    const load = () => {
      controller?.abort();
      controller = new AbortController();
      void loaderRef
        .current(controller.signal)
        .then((data) => {
          if (mounted) setState({ status: "success", data });
        })
        .catch((error: unknown) => {
          if (!mounted || (error instanceof DOMException && error.name === "AbortError")) return;
          if (error instanceof ApiError) {
            setState({
              status: "error",
              message: error.message,
              statusCode: error.status,
              requestId: error.requestId,
            });
          } else {
            setState({ status: "error", message: "The requested data is unavailable." });
          }
        });
    };

    queueMicrotask(() => {
      if (mounted) setState({ status: "loading" });
    });
    load();
    const interval =
      refreshMilliseconds > 0
        ? window.setInterval(() => {
            if (document.visibilityState === "visible") load();
          }, refreshMilliseconds)
        : undefined;
    return () => {
      mounted = false;
      controller?.abort();
      if (interval !== undefined) window.clearInterval(interval);
    };
  }, [key, refreshMilliseconds]);

  return state;
}
