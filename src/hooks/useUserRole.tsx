import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type AppRole = 'admin' | 'trader' | 'auditor' | 'compliance' | 'operator';

export const useUserRole = () => {
  return useQuery({
    queryKey: ['userRole'],
    queryFn: async () => {
      if (!apiClient.isAuthenticated()) return [];

      try {
        const { roles } = await apiClient.getMe();
        return roles as AppRole[];
      } catch {
        return [];
      }
    },
  });
};

export const useHasRole = (requiredRole: AppRole) => {
  const { data: roles, isLoading } = useUserRole();
  return {
    hasRole: roles?.includes(requiredRole) || false,
    isLoading,
  };
};

export const useHasAnyRole = (requiredRoles: AppRole[]) => {
  const { data: roles, isLoading } = useUserRole();
  return {
    hasRole: roles?.some(role => requiredRoles.includes(role)) || false,
    isLoading,
  };
};
