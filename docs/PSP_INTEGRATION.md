# Payment Service Provider (PSP) Integration

## Overview
Tokenized payment integration for secure deposit/withdrawal processing with PCI-DSS compliance.

## Supported PSPs (Zimbabwe Context)

### 1. Paynow (Primary - Zimbabwe)
- Mobile money (EcoCash, OneMoney, Telecash)
- Bank transfers
- Credit/Debit cards
- ZIPIT integration

### 2. Stripe (International)
- Cards (Visa, Mastercard, Amex)
- Bank transfers (ACH, SEPA)
- Digital wallets (Apple Pay, Google Pay)

### 3. Paystack (Africa)
- Cards and mobile money
- Bank transfers
- USSD payments

## Architecture

```
[User] → [Frontend] → [Edge Function] → [PSP API]
                            ↓
                    [Payment Tokenization]
                            ↓
                      [Database]
                            ↓
                    [Reconciliation Engine]
```

## Payment Flow (Tokenized)

### 1. Deposit Initiation
```typescript
// supabase/functions/initiate-deposit/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface DepositRequest {
  amount: number;
  currency: "USD" | "ZWL";
  paymentMethod: "mobile_money" | "card" | "bank_transfer";
  phone?: string; // For mobile money
}

serve(async (req) => {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  };

  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // Get authenticated user
    const authHeader = req.headers.get("Authorization")!;
    const token = authHeader.replace("Bearer ", "");
    const { data: { user }, error: authError } = await supabase.auth.getUser(token);
    
    if (authError || !user) {
      throw new Error("Unauthorized");
    }

    const { amount, currency, paymentMethod, phone }: DepositRequest = await req.json();

    // Validate amount
    if (amount <= 0 || amount > 100000) {
      throw new Error("Invalid amount");
    }

    // Generate unique transaction reference
    const txnRef = `DEP-${Date.now()}-${user.id.substring(0, 8)}`;

    // Create transaction record
    const { data: transaction, error: txnError } = await supabase
      .from("transactions")
      .insert({
        user_id: user.id,
        type: "deposit",
        amount,
        currency,
        payment_method: paymentMethod,
        reference: txnRef,
        status: "pending",
      })
      .select()
      .single();

    if (txnError) throw txnError;

    // Initiate payment with PSP
    let paymentResponse;
    
    if (paymentMethod === "mobile_money" && phone) {
      // Paynow mobile money
      paymentResponse = await initiatePaynowMobilePayment({
        amount,
        phone,
        reference: txnRef,
        returnUrl: `${Deno.env.get("APP_URL")}/deposit/callback`,
      });
    } else if (paymentMethod === "card") {
      // Stripe or Paynow card (tokenized)
      paymentResponse = await initiateStripePayment({
        amount: amount * 100, // Cents
        currency: currency.toLowerCase(),
        customerId: user.id,
        metadata: { transactionId: transaction.id },
      });
    }

    // Update transaction with PSP reference
    await supabase.from("transactions").update({
      notes: JSON.stringify({ pspReference: paymentResponse.reference }),
    }).eq("id", transaction.id);

    return new Response(JSON.stringify({
      transactionId: transaction.id,
      paymentUrl: paymentResponse.paymentUrl,
      reference: txnRef,
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error("Deposit initiation error:", error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});

async function initiatePaynowMobilePayment(params: {
  amount: number;
  phone: string;
  reference: string;
  returnUrl: string;
}): Promise<{ reference: string; paymentUrl: string }> {
  const paynowId = Deno.env.get("PAYNOW_ID")!;
  const paynowKey = Deno.env.get("PAYNOW_KEY")!;

  const response = await fetch("https://www.paynow.co.zw/interface/initiatetransaction", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      id: paynowId,
      reference: params.reference,
      amount: params.amount.toFixed(2),
      additionalinfo: "ZimAI Trader Deposit",
      returnurl: params.returnUrl,
      resulturl: `${Deno.env.get("SUPABASE_URL")}/functions/v1/paynow-webhook`,
      authemail: "",
      phone: params.phone,
      method: "ecocash", // or onemoney, telecash
    }),
  });

  const text = await response.text();
  const data = parsePaynowResponse(text);

  if (data.status !== "Ok") {
    throw new Error(`Paynow error: ${data.error}`);
  }

  return {
    reference: data.pollurl,
    paymentUrl: data.browserurl,
  };
}

async function initiateStripePayment(params: {
  amount: number;
  currency: string;
  customerId: string;
  metadata: Record<string, string>;
}): Promise<{ reference: string; paymentUrl: string }> {
  const stripeKey = Deno.env.get("STRIPE_SECRET_KEY")!;

  const response = await fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${stripeKey}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      "payment_method_types[]": "card",
      "line_items[0][price_data][currency]": params.currency,
      "line_items[0][price_data][product_data][name]": "ZimAI Trader Deposit",
      "line_items[0][price_data][unit_amount]": params.amount.toString(),
      "line_items[0][quantity]": "1",
      "mode": "payment",
      "success_url": `${Deno.env.get("APP_URL")}/deposit/success`,
      "cancel_url": `${Deno.env.get("APP_URL")}/deposit/cancel`,
      "client_reference_id": params.customerId,
      "metadata[transaction_id]": params.metadata.transactionId,
    }),
  });

  const data = await response.json();

  return {
    reference: data.id,
    paymentUrl: data.url,
  };
}

function parsePaynowResponse(text: string): Record<string, string> {
  const lines = text.split("\n");
  const result: Record<string, string> = {};
  lines.forEach(line => {
    const [key, value] = line.split("=");
    if (key && value) result[key.toLowerCase()] = value;
  });
  return result;
}
```

### 2. Payment Webhook Handler
```typescript
// supabase/functions/paynow-webhook/index.ts
serve(async (req) => {
  try {
    const formData = await req.formData();
    const reference = formData.get("reference");
    const paynowReference = formData.get("paynowreference");
    const amount = formData.get("amount");
    const status = formData.get("status");
    const hash = formData.get("hash");

    // Verify hash (security)
    const computedHash = await verifyPaynowHash({
      reference,
      paynowReference,
      amount,
      status,
    });

    if (hash !== computedHash) {
      throw new Error("Invalid hash");
    }

    // Update transaction
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const newStatus = status === "Paid" ? "completed" : "failed";

    const { data: transaction } = await supabase
      .from("transactions")
      .update({ status: newStatus, updated_at: new Date().toISOString() })
      .eq("reference", reference)
      .select()
      .single();

    if (newStatus === "completed" && transaction) {
      // Credit user balance
      await supabase.rpc("credit_balance", {
        p_user_id: transaction.user_id,
        p_amount: parseFloat(amount),
        p_currency: transaction.currency,
      });

      // Log audit event
      await supabase.from("audit_logs").insert({
        user_id: transaction.user_id,
        action: "deposit_completed",
        resource_type: "transaction",
        resource_id: transaction.id,
        details: { amount, reference, paynowReference },
      });
    }

    return new Response("OK", { status: 200 });
  } catch (error) {
    console.error("Webhook error:", error);
    return new Response("Error", { status: 500 });
  }
});

async function verifyPaynowHash(data: Record<string, string>): Promise<string> {
  const paynowKey = Deno.env.get("PAYNOW_KEY")!;
  const values = Object.values(data).join("");
  const message = values + paynowKey;
  
  const encoder = new TextEncoder();
  const msgBuffer = encoder.encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-512", msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
  
  return hashHex.toUpperCase();
}
```

### 3. Card Tokenization (Stripe)
```typescript
// Frontend: Never send raw card data to backend
// Use Stripe Elements for PCI-compliant tokenization

import { loadStripe } from "@stripe/stripe-js";
import { Elements, CardElement, useStripe, useElements } from "@stripe/react-stripe-js";

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY);

function CheckoutForm() {
  const stripe = useStripe();
  const elements = useElements();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) return;

    // Create payment method (tokenized, no raw card data)
    const { error, paymentMethod } = await stripe.createPaymentMethod({
      type: "card",
      card: elements.getElement(CardElement)!,
    });

    if (error) {
      console.error(error);
      return;
    }

    // Send only token to backend
    const response = await supabase.functions.invoke("initiate-deposit", {
      body: {
        amount: 100,
        currency: "USD",
        paymentMethod: "card",
        paymentMethodId: paymentMethod.id, // Token, not card details
      },
    });

    // Handle response...
  };

  return (
    <form onSubmit={handleSubmit}>
      <CardElement />
      <button type="submit" disabled={!stripe}>Pay</button>
    </form>
  );
}
```

## Withdrawal Flow

### 1. Withdrawal Request
```typescript
// supabase/functions/initiate-withdrawal/index.ts
interface WithdrawalRequest {
  amount: number;
  currency: "USD" | "ZWL";
  method: "mobile_money" | "bank_transfer";
  destination: {
    phone?: string;
    bankAccount?: {
      accountNumber: string;
      bankCode: string;
      accountName: string;
    };
  };
}

serve(async (req) => {
  // Similar structure to deposit
  // But includes additional checks:
  
  // 1. KYC verification
  const { data: kyc } = await supabase
    .from("kyc_records")
    .select("status")
    .eq("user_id", user.id)
    .single();

  if (kyc?.status !== "approved") {
    throw new Error("KYC verification required");
  }

  // 2. Balance check
  const { data: profile } = await supabase
    .from("profiles")
    .select("usd_balance, zwl_balance")
    .eq("user_id", user.id)
    .single();

  const balance = currency === "USD" ? profile.usd_balance : profile.zwl_balance;
  if (balance < amount) {
    throw new Error("Insufficient balance");
  }

  // 3. Daily limit check
  const todayWithdrawals = await getTodayWithdrawals(user.id);
  if (todayWithdrawals + amount > 10000) {
    throw new Error("Daily withdrawal limit exceeded");
  }

  // 4. AML screening
  if (amount > 5000) {
    await createAMLAlert(user.id, amount, "large_withdrawal");
  }

  // Create withdrawal transaction
  const { data: transaction } = await supabase
    .from("transactions")
    .insert({
      user_id: user.id,
      type: "withdrawal",
      amount,
      currency,
      status: "pending_approval", // Manual approval required
      payment_method: method,
      reference: `WD-${Date.now()}-${user.id.substring(0, 8)}`,
    })
    .select()
    .single();

  return new Response(JSON.stringify({ transactionId: transaction.id }), {
    headers: { "Content-Type": "application/json" },
  });
});
```

### 2. Manual Approval (Compliance)
Compliance officers approve withdrawals via the Compliance dashboard UI.

### 3. Payout Execution
```typescript
// supabase/functions/execute-payout/index.ts
// Called by compliance after approval

async function executePaynowPayout(params: {
  phone: string;
  amount: number;
  reference: string;
}): Promise<void> {
  // Use Paynow disbursement API
  const response = await fetch("https://www.paynow.co.zw/interface/payout", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      id: Deno.env.get("PAYNOW_ID")!,
      key: Deno.env.get("PAYNOW_KEY")!,
      reference: params.reference,
      destination: params.phone,
      amount: params.amount.toFixed(2),
      reason: "ZimAI Trader Withdrawal",
    }),
  });

  // Handle response and update transaction
}
```

## Reconciliation

### Daily Reconciliation Job
```typescript
// supabase/functions/daily-reconciliation/index.ts
async function reconcilePayments(): Promise<void> {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);

  // Get all transactions from yesterday
  const { data: transactions } = await supabase
    .from("transactions")
    .select("*")
    .gte("created_at", yesterday.toISOString())
    .in("status", ["pending", "completed"]);

  // Query PSP for transaction statuses
  for (const txn of transactions!) {
    const pspStatus = await queryPSPStatus(txn.reference);
    
    if (pspStatus !== txn.status) {
      // Mismatch detected
      await supabase.from("aml_alerts").insert({
        user_id: txn.user_id,
        alert_type: "unusual_pattern",
        severity: "high",
        status: "open",
        transaction_id: txn.id,
        details: {
          reason: "Status mismatch",
          internalStatus: txn.status,
          pspStatus,
        },
      });

      // Update status
      await supabase.from("transactions").update({
        status: pspStatus,
        updated_at: new Date().toISOString(),
      }).eq("id", txn.id);
    }
  }
}

// Run daily at 2 AM
Deno.cron("daily-reconciliation", "0 2 * * *", reconcilePayments);
```

## Security Best Practices

1. **Never store raw card data** - Use PSP tokenization
2. **PCI-DSS Scope Reduction** - Offload card handling to Stripe/PSP
3. **Webhook signature verification** - Validate all webhooks
4. **Idempotency** - Use unique transaction references
5. **Rate limiting** - Prevent payment endpoint abuse
6. **Amount validation** - Min/max limits, currency checks
7. **KYC gates** - Require verification for withdrawals
8. **Manual approval** - For large transactions
9. **Daily reconciliation** - Detect mismatches
10. **Audit all payments** - Immutable logs

## Integration Checklist

- [ ] PSP credentials obtained and secured (secrets)
- [ ] Webhook endpoints configured and verified
- [ ] Tokenization implemented (no raw card data)
- [ ] KYC verification enforced for withdrawals
- [ ] Balance checks and daily limits implemented
- [ ] Manual approval workflow for large withdrawals
- [ ] AML screening rules configured
- [ ] Reconciliation job scheduled
- [ ] Audit logging enabled
- [ ] PCI-DSS compliance validated
- [ ] Penetration testing completed on payment flows
