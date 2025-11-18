export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "13.0.5"
  }
  public: {
    Tables: {
      aml_alerts: {
        Row: {
          alert_type: string
          assigned_to: string | null
          created_at: string
          details: Json
          id: string
          resolution_notes: string | null
          resolved_at: string | null
          severity: string
          status: string
          transaction_id: string | null
          user_id: string
        }
        Insert: {
          alert_type: string
          assigned_to?: string | null
          created_at?: string
          details: Json
          id?: string
          resolution_notes?: string | null
          resolved_at?: string | null
          severity?: string
          status?: string
          transaction_id?: string | null
          user_id: string
        }
        Update: {
          alert_type?: string
          assigned_to?: string | null
          created_at?: string
          details?: Json
          id?: string
          resolution_notes?: string | null
          resolved_at?: string | null
          severity?: string
          status?: string
          transaction_id?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "aml_alerts_transaction_id_fkey"
            columns: ["transaction_id"]
            isOneToOne: false
            referencedRelation: "transactions"
            referencedColumns: ["id"]
          },
        ]
      }
      audit_logs: {
        Row: {
          action: string
          details: Json | null
          id: string
          ip_address: string | null
          resource_id: string | null
          resource_type: string
          session_id: string | null
          timestamp: string
          user_agent: string | null
          user_id: string
        }
        Insert: {
          action: string
          details?: Json | null
          id?: string
          ip_address?: string | null
          resource_id?: string | null
          resource_type: string
          session_id?: string | null
          timestamp?: string
          user_agent?: string | null
          user_id: string
        }
        Update: {
          action?: string
          details?: Json | null
          id?: string
          ip_address?: string | null
          resource_id?: string | null
          resource_type?: string
          session_id?: string | null
          timestamp?: string
          user_agent?: string | null
          user_id?: string
        }
        Relationships: []
      }
      kyc_records: {
        Row: {
          address: string
          created_at: string
          date_of_birth: string
          full_name: string
          id: string
          id_number: string
          id_type: string
          pep_check_result: string | null
          phone: string
          rejection_reason: string | null
          reviewed_at: string | null
          reviewed_by: string | null
          sanctions_check_result: string | null
          status: string
          updated_at: string
          user_id: string
          verification_documents: Json | null
        }
        Insert: {
          address: string
          created_at?: string
          date_of_birth: string
          full_name: string
          id?: string
          id_number: string
          id_type: string
          pep_check_result?: string | null
          phone: string
          rejection_reason?: string | null
          reviewed_at?: string | null
          reviewed_by?: string | null
          sanctions_check_result?: string | null
          status?: string
          updated_at?: string
          user_id: string
          verification_documents?: Json | null
        }
        Update: {
          address?: string
          created_at?: string
          date_of_birth?: string
          full_name?: string
          id?: string
          id_number?: string
          id_type?: string
          pep_check_result?: string | null
          phone?: string
          rejection_reason?: string | null
          reviewed_at?: string | null
          reviewed_by?: string | null
          sanctions_check_result?: string | null
          status?: string
          updated_at?: string
          user_id?: string
          verification_documents?: Json | null
        }
        Relationships: []
      }
      model_registry: {
        Row: {
          approval_status: string
          approved_at: string | null
          approved_by: string | null
          deployed_at: string
          deployed_by: string
          hyperparameters: Json | null
          id: string
          model_name: string
          notes: string | null
          performance_metrics: Json | null
          status: string
          training_data_id: string | null
          validation_results: Json | null
          version: string
        }
        Insert: {
          approval_status?: string
          approved_at?: string | null
          approved_by?: string | null
          deployed_at?: string
          deployed_by: string
          hyperparameters?: Json | null
          id?: string
          model_name: string
          notes?: string | null
          performance_metrics?: Json | null
          status?: string
          training_data_id?: string | null
          validation_results?: Json | null
          version: string
        }
        Update: {
          approval_status?: string
          approved_at?: string | null
          approved_by?: string | null
          deployed_at?: string
          deployed_by?: string
          hyperparameters?: Json | null
          id?: string
          model_name?: string
          notes?: string | null
          performance_metrics?: Json | null
          status?: string
          training_data_id?: string | null
          validation_results?: Json | null
          version?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          created_at: string
          id: string
          updated_at: string
          usd_balance: number
          user_id: string
          zwl_balance: number
        }
        Insert: {
          created_at?: string
          id?: string
          updated_at?: string
          usd_balance?: number
          user_id: string
          zwl_balance?: number
        }
        Update: {
          created_at?: string
          id?: string
          updated_at?: string
          usd_balance?: number
          user_id?: string
          zwl_balance?: number
        }
        Relationships: []
      }
      trades: {
        Row: {
          closed_at: string | null
          confidence: number | null
          contract_size: number | null
          created_at: string
          entry_price: number
          exit_price: number | null
          expiry_date: string | null
          id: string
          instrument_type: string | null
          option_type: string | null
          pnl: number | null
          premium: number | null
          quantity: number
          side: string
          status: string
          strike_price: number | null
          symbol: string
          underlying_asset: string | null
          user_id: string
        }
        Insert: {
          closed_at?: string | null
          confidence?: number | null
          contract_size?: number | null
          created_at?: string
          entry_price: number
          exit_price?: number | null
          expiry_date?: string | null
          id?: string
          instrument_type?: string | null
          option_type?: string | null
          pnl?: number | null
          premium?: number | null
          quantity: number
          side: string
          status?: string
          strike_price?: number | null
          symbol: string
          underlying_asset?: string | null
          user_id: string
        }
        Update: {
          closed_at?: string | null
          confidence?: number | null
          contract_size?: number | null
          created_at?: string
          entry_price?: number
          exit_price?: number | null
          expiry_date?: string | null
          id?: string
          instrument_type?: string | null
          option_type?: string | null
          pnl?: number | null
          premium?: number | null
          quantity?: number
          side?: string
          status?: string
          strike_price?: number | null
          symbol?: string
          underlying_asset?: string | null
          user_id?: string
        }
        Relationships: []
      }
      transactions: {
        Row: {
          amount: number
          created_at: string
          currency: string
          id: string
          notes: string | null
          payment_method: string | null
          reference: string | null
          status: string
          type: string
          updated_at: string
          user_id: string
        }
        Insert: {
          amount: number
          created_at?: string
          currency: string
          id?: string
          notes?: string | null
          payment_method?: string | null
          reference?: string | null
          status?: string
          type: string
          updated_at?: string
          user_id: string
        }
        Update: {
          amount?: number
          created_at?: string
          currency?: string
          id?: string
          notes?: string | null
          payment_method?: string | null
          reference?: string | null
          status?: string
          type?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          assigned_at: string
          assigned_by: string | null
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          assigned_at?: string
          assigned_by?: string | null
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          assigned_at?: string
          assigned_by?: string | null
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
    }
    Enums: {
      app_role: "admin" | "trader" | "auditor" | "compliance" | "operator"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "trader", "auditor", "compliance", "operator"],
    },
  },
} as const
