# HSM Integration Guide

## Overview
Hardware Security Module (HSM) integration for cryptographic key management and signing operations.

## Supported HSM Providers
- AWS CloudHSM
- Azure Dedicated HSM
- Thales Luna HSM
- Utimaco HSM
- nCipher nShield

## Architecture

```
[Application] → [PKCS#11 Library] → [HSM Client] → [HSM Device]
```

## Use Cases in ZimAI Trader

1. **Order Signing**: Cryptographically sign all trade orders before submission to brokers
2. **Key Storage**: Store encryption keys for data at rest
3. **Certificate Management**: Store TLS/SSL private keys
4. **Payment Authorization**: Sign payment transactions
5. **Audit Log Integrity**: Sign audit log entries for non-repudiation

## Setup: AWS CloudHSM

### Step 1: Provision CloudHSM Cluster
```bash
aws cloudhsmv2 create-cluster \
  --hsm-type hsm1.medium \
  --subnet-ids subnet-12345 subnet-67890 \
  --region us-east-1
```

### Step 2: Initialize HSM
```bash
# Create HSM
aws cloudhsmv2 create-hsm \
  --cluster-id cluster-xyz \
  --availability-zone us-east-1a

# Initialize and activate
cloudhsm-cli configure-cli
cloudhsm-cli activate
```

### Step 3: Create Crypto User
```bash
# In HSM shell
cloudhsm> create-user CU trade_user <password>
cloudhsm> set-password CU trade_user <new-password>
```

### Step 4: Configure Application

#### Edge Function Example
```typescript
// supabase/functions/sign-order/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// PKCS#11 integration via Deno FFI or external binary
const HSM_CONFIG = {
  library: "/opt/cloudhsm/lib/libcloudhsm_pkcs11.so",
  slot: 0,
  pin: Deno.env.get("HSM_PIN"),
};

async function signWithHSM(data: Uint8Array): Promise<Uint8Array> {
  // Call HSM signing via PKCS#11
  // Implementation depends on chosen library
  
  const command = new Deno.Command("/usr/local/bin/hsm-sign", {
    args: ["--slot", String(HSM_CONFIG.slot), "--data", "-"],
    stdin: "piped",
    stdout: "piped",
    env: { HSM_PIN: HSM_CONFIG.pin },
  });

  const process = command.spawn();
  const writer = process.stdin.getWriter();
  await writer.write(data);
  await writer.close();

  const output = await process.output();
  return output.stdout;
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
    const { orderData } = await req.json();
    
    // Convert order to signable format
    const orderBytes = new TextEncoder().encode(JSON.stringify(orderData));
    
    // Sign with HSM
    const signature = await signWithHSM(orderBytes);
    
    // Attach signature to order
    const signedOrder = {
      ...orderData,
      signature: Array.from(signature),
      signedAt: new Date().toISOString(),
      signingMethod: "HSM_RSA_2048_SHA256",
    };

    return new Response(JSON.stringify(signedOrder), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
```

## Key Management Operations

### Generate Key Pair
```typescript
interface HSMKeyPair {
  keyId: string;
  publicKey: string;
  algorithm: "RSA_2048" | "ECDSA_P256";
  createdAt: string;
}

async function generateKeyPair(label: string): Promise<HSMKeyPair> {
  // PKCS#11 C_GenerateKeyPair call
  const response = await hsmClient.generateKeyPair({
    label,
    algorithm: "RSA",
    keySize: 2048,
    extractable: false, // Key never leaves HSM
  });
  
  return {
    keyId: response.keyId,
    publicKey: response.publicKeyPEM,
    algorithm: "RSA_2048",
    createdAt: new Date().toISOString(),
  };
}
```

### Sign Data
```typescript
async function signData(keyId: string, data: Uint8Array): Promise<Uint8Array> {
  return await hsmClient.sign({
    keyId,
    mechanism: "RSA_PKCS_SHA256",
    data,
  });
}
```

### Verify Signature
```typescript
async function verifySignature(
  keyId: string, 
  data: Uint8Array, 
  signature: Uint8Array
): Promise<boolean> {
  return await hsmClient.verify({
    keyId,
    mechanism: "RSA_PKCS_SHA256",
    data,
    signature,
  });
}
```

## Key Rotation Policy

```typescript
// Automated key rotation (runs monthly)
async function rotateOrderSigningKey() {
  const currentKey = await getActiveKey("order_signing");
  
  // Generate new key
  const newKey = await generateKeyPair("order_signing_" + Date.now());
  
  // Update key registry
  await supabase.from("hsm_keys").insert({
    key_id: newKey.keyId,
    label: "order_signing",
    status: "active",
    algorithm: newKey.algorithm,
    created_at: newKey.createdAt,
  });
  
  // Deprecate old key (keep for verification of old signatures)
  await supabase.from("hsm_keys").update({
    status: "deprecated",
    deprecated_at: new Date().toISOString(),
  }).eq("key_id", currentKey.keyId);
  
  // Log audit event
  await logAuditEvent("key_rotation", {
    oldKeyId: currentKey.keyId,
    newKeyId: newKey.keyId,
  });
}
```

## Monitoring & Alerts

### HSM Health Checks
```typescript
async function checkHSMHealth(): Promise<boolean> {
  try {
    // Attempt to access HSM
    const info = await hsmClient.getInfo();
    
    // Check capacity
    if (info.availableStorage < 10) {
      await alertOps("HSM storage critically low");
    }
    
    // Check connectivity
    if (info.clusterStatus !== "active") {
      await alertOps("HSM cluster not active");
      return false;
    }
    
    return true;
  } catch (error) {
    await alertOps("HSM unreachable: " + error.message);
    return false;
  }
}

// Run every 60 seconds
setInterval(checkHSMHealth, 60000);
```

## Backup & Recovery

### Key Backup
```bash
# Export wrapped key backup (encrypted with another HSM key)
cloudhsm> export-key \
  --key-id <key-id> \
  --wrap-key-id <backup-key-id> \
  --output /secure/backup/key-backup.bin

# Store in encrypted vault with multiple custodians
```

### Disaster Recovery
1. Provision new HSM cluster in DR region
2. Import wrapped keys from secure backup
3. Verify key functionality with test signatures
4. Update application HSM endpoints
5. Run validation suite

## Compliance

### Audit Requirements
- All HSM operations logged with timestamps
- Key usage tracked (which orders signed with which keys)
- Access logs reviewed weekly
- Annual HSM security audit

### Access Control
- Separate crypto officers (CO) and crypto users (CU)
- M-of-N authentication for sensitive operations
- Hardware token + PIN for administrator access

## Security Best Practices

1. **Never export private keys** - Keys generated in HSM stay in HSM
2. **Use secure channels** - TLS between app and HSM, mTLS in production
3. **Implement rate limiting** - Prevent HSM exhaustion attacks
4. **Monitor for anomalies** - Alert on unusual signing patterns
5. **Regular firmware updates** - Keep HSM firmware patched
6. **Physical security** - HSM devices in secure data center with access logs

## Cost Optimization

- **AWS CloudHSM**: ~$1.60/hour per HSM + $0.00 per API call
- **Azure Dedicated HSM**: ~$4.84/hour
- **On-premise HSM**: High upfront cost, lower operational cost

Consider starting with CloudHSM for flexibility, migrate to on-premise for cost savings at scale.

## Integration Checklist

- [ ] HSM cluster provisioned and initialized
- [ ] Network connectivity verified (security groups, VPN)
- [ ] Crypto users created with strong PINs
- [ ] Key pairs generated for signing operations
- [ ] Application integrated with PKCS#11 library
- [ ] Key rotation policy implemented
- [ ] HSM health monitoring configured
- [ ] Backup and recovery procedures tested
- [ ] Audit logging enabled
- [ ] Incident response procedures documented
