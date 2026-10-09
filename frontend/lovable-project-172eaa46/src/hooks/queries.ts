import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  accountService, marketDataService, orderService, positionService, riskService, strategyService,
} from "@/services";
import type { Timeframe } from "@/types";

export const useAccount = () => useQuery({ queryKey: ["account"], queryFn: accountService.getAccountSummary });
export const usePnlHistory = () => useQuery({ queryKey: ["pnl"], queryFn: accountService.getPnlHistory });
export const useCandles = (symbol: string, tf: Timeframe) =>
  useQuery({ queryKey: ["candles", symbol, tf], queryFn: () => marketDataService.getCandles(symbol, tf) });
export const useStrategies = () => useQuery({ queryKey: ["strategies"], queryFn: strategyService.getStrategies });
export const useStrategy = (id: string) => useQuery({ queryKey: ["strategies", id], queryFn: () => strategyService.getStrategy(id) });
export const useOrders = () => useQuery({ queryKey: ["orders"], queryFn: orderService.getOrders });
export const usePositions = () => useQuery({ queryKey: ["positions"], queryFn: positionService.getPositions });
export const useRiskStatus = () => useQuery({ queryKey: ["risk"], queryFn: riskService.getRiskStatus });
export const useRiskEvents = () => useQuery({ queryKey: ["riskEvents"], queryFn: riskService.getRiskEvents });
export const useKillSwitch = () => useQuery({ queryKey: ["killSwitch"], queryFn: riskService.getKillSwitch });

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "candles" });
}

export function useStrategyAction() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "subscribe" | "start" | "stop" }) => strategyService[action](id),
    onSuccess: inv,
  });
}

export function useKillSwitchActions() {
  const inv = useInvalidateAll();
  const activate = useMutation({ mutationFn: riskService.activateKillSwitch, onSuccess: inv });
  const reset = useMutation({ mutationFn: riskService.resetKillSwitch, onSuccess: inv });
  return { activate, reset };
}
