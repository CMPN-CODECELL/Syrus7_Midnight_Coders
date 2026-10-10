import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  accountService, marketDataService, orderService, positionService, riskService, strategyService,
} from "@/services";
import type { Timeframe } from "@/types";

export const useAccount = () => useQuery({ queryKey: ["account"], queryFn: accountService.getAccountSummary, refetchInterval: 3000 });
export const usePnlHistory = () => useQuery({ queryKey: ["pnl"], queryFn: accountService.getPnlHistory, refetchInterval: 5000 });
export const useCandles = (symbol: string, tf: Timeframe) =>
  useQuery({ queryKey: ["candles", symbol, tf], queryFn: () => marketDataService.getCandles(symbol, tf), refetchInterval: 2500 });
export const useInstruments = () =>
  useQuery({ queryKey: ["instruments"], queryFn: marketDataService.getInstruments, refetchInterval: 10000 });

export const useStrategies = () => useQuery({ queryKey: ["strategies"], queryFn: strategyService.getStrategies, refetchInterval: 3000 });
export const useStrategy = (id: string) => useQuery({ queryKey: ["strategies", id], queryFn: () => strategyService.getStrategy(id), refetchInterval: 3000 });
export const useOrders = () => useQuery({ queryKey: ["orders"], queryFn: orderService.getOrders, refetchInterval: 3000 });
export const usePositions = () => useQuery({ queryKey: ["positions"], queryFn: positionService.getPositions, refetchInterval: 3000 });
export const useRiskStatus = () => useQuery({ queryKey: ["risk"], queryFn: riskService.getRiskStatus, refetchInterval: 3000 });
export const useRiskEvents = () => useQuery({ queryKey: ["riskEvents"], queryFn: riskService.getRiskEvents, refetchInterval: 3000 });
export const useKillSwitch = () => useQuery({ queryKey: ["killSwitch"], queryFn: riskService.getKillSwitch, refetchInterval: 3000 });

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "candles" });
}

export function useStrategyAction() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "subscribe" | "unsubscribe" | "start" | "stop" }) => strategyService[action](id),
    onSuccess: inv,
  });
}

export function useKillSwitchActions() {
  const inv = useInvalidateAll();
  const activate = useMutation({
    mutationFn: (options?: { scope?: string | undefined; reason?: string | undefined; targetId?: string | undefined; cooldownMinutes?: number | undefined }) =>
      riskService.activateKillSwitch(options),
    onSuccess: inv,
  });
  const reset = useMutation({ mutationFn: riskService.resetKillSwitch, onSuccess: inv });
  return { activate, reset };
}

export function useKillSwitchIncidents() {
  return useQuery({
    queryKey: ["killSwitchIncidents"],
    queryFn: riskService.getKillSwitchIncidents,
    refetchInterval: 4000,
  });
}

export function useUpdateAutoKillRules() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: (rules: any) => riskService.updateAutoKillRules(rules),
    onSuccess: inv,
  });
}

export function useUpdateRiskLimits() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: (limits: { maxDailyLoss?: number; maxPositionSize?: number; maxOrdersPerMinute?: number }) =>
      riskService.updateRiskLimits(limits),
    onSuccess: inv,
  });
}

export function usePlaceOrder() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: orderService.placeOrder,
    onSuccess: inv,
  });
}

export function useUpdateStrategyParameters() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: ({ id, parameters, limits }: { id: string; parameters: Record<string, any>; limits?: any }) =>
      strategyService.updateParameters(id, parameters, limits),
    onSuccess: inv,
  });
}

export function useSquareOffStrategy() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: (id: string) => strategyService.squareOff(id),
    onSuccess: inv,
  });
}

export function useManualTradeStrategy() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: ({ id, side, quantity }: { id: string; side: "BUY" | "SELL"; quantity?: number }) =>
      strategyService.manualTrade(id, side, quantity),
    onSuccess: inv,
  });
}

export function useResetStrategy() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: (id: string) => strategyService.reset(id),
    onSuccess: inv,
  });
}

export function useCreateStrategy() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: (payload: {
      name: string;
      strategy_type: string;
      symbol: string;
      description?: string;
      parameters: Record<string, any>;
      limits?: any;
    }) => strategyService.create(payload),
    onSuccess: inv,
  });
}

export function useDeleteStrategy() {
  const inv = useInvalidateAll();
  return useMutation({
    mutationFn: (id: string) => strategyService.delete(id),
    onSuccess: inv,
  });
}

