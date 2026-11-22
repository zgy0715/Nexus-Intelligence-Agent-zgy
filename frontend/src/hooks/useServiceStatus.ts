/**
 * useServiceStatus — 顶栏模型芯片与设置页共享的服务状态轮询（60s）。
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useServiceStatus() {
  return useQuery({
    queryKey: ["service-status"],
    queryFn: api.getServiceStatus,
    refetchInterval: 60_000,
  });
}
