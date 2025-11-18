import { apiClient } from "@/lib/api-client";

interface AuditLogParams {
  action: string;
  resource_type: string;
  resource_id?: string;
  details?: Record<string, any>;
}

export const useAuditLog = () => {
  const logAction = async (params: AuditLogParams) => {
    try {
      if (!apiClient.isAuthenticated()) return;

      await apiClient.createAuditLog({
        action: params.action,
        resource_type: params.resource_type,
        resource_id: params.resource_id,
        details: params.details,
        user_agent: navigator.userAgent,
      });
    } catch (error) {
      console.error('Failed to log audit action:', error);
    }
  };

  return { logAction };
};
