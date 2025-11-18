# Penetration Testing Guide

## Overview
Comprehensive security testing plan for ZimAI Trader platform.

## Testing Scope

### In-Scope
- Web application (React frontend)
- API endpoints (Edge Functions)
- Authentication and authorization
- Database access (RLS policies)
- Payment flows
- File uploads (if implemented)
- Admin interfaces

### Out-of-Scope
- Third-party services (Supabase infrastructure, PSPs, brokers)
- Physical security
- Social engineering
- Denial of Service (DoS) attacks

## Testing Methodology

### 1. Information Gathering
- [ ] Enumerate all subdomains and endpoints
- [ ] Identify technology stack and versions
- [ ] Map application architecture
- [ ] Review public code repositories
- [ ] Check for exposed credentials or secrets

### 2. Authentication Testing
- [ ] Brute force attack on login
- [ ] Password policy bypass
- [ ] Session fixation
- [ ] Session timeout validation
- [ ] MFA bypass attempts
- [ ] OAuth/OIDC flow vulnerabilities
- [ ] JWT token manipulation
- [ ] Privilege escalation (user → admin)

### 3. Authorization Testing
- [ ] Horizontal privilege escalation (access other users' data)
- [ ] Vertical privilege escalation (access admin functions)
- [ ] IDOR (Insecure Direct Object References)
- [ ] RLS policy bypass attempts
- [ ] Role manipulation in client storage

### 4. Input Validation
- [ ] SQL injection (database queries)
- [ ] Cross-Site Scripting (XSS)
- [ ] Command injection
- [ ] Path traversal
- [ ] XML/JSON injection
- [ ] Server-Side Request Forgery (SSRF)
- [ ] File upload vulnerabilities

### 5. Business Logic Flaws
- [ ] Race conditions in balance updates
- [ ] Negative amount deposits/withdrawals
- [ ] Currency manipulation
- [ ] Order manipulation (price, quantity)
- [ ] Referral/bonus abuse
- [ ] KYC bypass
- [ ] Transaction replay attacks

### 6. API Security
- [ ] Missing authentication on endpoints
- [ ] Rate limiting bypass
- [ ] Mass assignment vulnerabilities
- [ ] GraphQL introspection abuse
- [ ] API key leakage
- [ ] CORS misconfiguration

### 7. Client-Side Security
- [ ] Local storage manipulation
- [ ] Client-side validation bypass
- [ ] Sensitive data exposure in browser
- [ ] Cross-Site Request Forgery (CSRF)
- [ ] Clickjacking

### 8. Cryptography
- [ ] Weak encryption algorithms
- [ ] Insecure random number generation
- [ ] Hard-coded secrets
- [ ] Certificate validation issues

### 9. Payment Security
- [ ] Payment amount manipulation
- [ ] Webhook signature bypass
- [ ] Replay attacks on payment callbacks
- [ ] Race conditions in payment processing

### 10. Model Security (AI Specific)
- [ ] Model poisoning attempts
- [ ] Adversarial inputs to trading models
- [ ] Model extraction attempts
- [ ] Training data leakage

## Testing Tools

### Automated Scanners
```bash
# OWASP ZAP
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://trade.zimaibank.com

# Burp Suite Professional
# (Manual configuration required)

# Nuclei
nuclei -u https://trade.zimaibank.com -t cves/ -t vulnerabilities/

# SQLMap
sqlmap -u "https://trade.zimaibank.com/api/endpoint?id=1" \
  --batch --level=5 --risk=3
```

### Manual Testing
```bash
# JWT manipulation
echo "eyJhbGc..." | base64 -d  # Decode JWT
# Modify payload, re-encode, test

# IDOR testing
curl -H "Authorization: Bearer $TOKEN" \
  https://trade.zimaibank.com/api/transactions/OTHER_USER_ID

# SQL injection
curl "https://trade.zimaibank.com/api/search?q=' OR 1=1--"

# XSS testing
<script>alert(document.cookie)</script>
```

## Critical Test Cases

### Test Case 1: Unauthorized Balance Manipulation
```bash
# Attempt to update another user's balance
curl -X POST https://trade.zimaibank.com/api/profiles \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user_id": "victim-uuid", "usd_balance": 999999}'
```
**Expected**: 403 Forbidden (RLS policy blocks)

### Test Case 2: Role Escalation
```bash
# Attempt to assign admin role to self
curl -X POST https://trade.zimaibank.com/api/user-roles \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user_id": "attacker-uuid", "role": "admin"}'
```
**Expected**: 403 Forbidden (only admins can assign roles)

### Test Case 3: Payment Webhook Spoofing
```bash
# Send fake payment confirmation
curl -X POST https://trade.zimaibank.com/api/paynow-webhook \
  -d "reference=DEP-123&status=Paid&amount=1000&hash=FAKEHASH"
```
**Expected**: 401 Unauthorized (hash verification fails)

### Test Case 4: KYC Bypass
```bash
# Attempt withdrawal without KYC
curl -X POST https://trade.zimaibank.com/api/withdraw \
  -H "Authorization: Bearer $TOKEN_NO_KYC" \
  -d '{"amount": 100, "currency": "USD"}'
```
**Expected**: 403 Forbidden (KYC required)

### Test Case 5: Audit Log Tampering
```bash
# Attempt to delete audit logs
curl -X DELETE https://trade.zimaibank.com/api/audit-logs/123 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```
**Expected**: 403 Forbidden (audit logs immutable)

### Test Case 6: SQL Injection in Search
```bash
# Inject SQL in search parameter
curl "https://trade.zimaibank.com/api/transactions?search=' UNION SELECT * FROM profiles--"
```
**Expected**: No data leakage (parameterized queries)

### Test Case 7: XSS in Profile Name
```javascript
// Submit malicious profile name
await supabase.from('profiles').update({
  display_name: '<img src=x onerror=alert(1)>'
})
```
**Expected**: Escaped/sanitized in UI

### Test Case 8: IDOR on Transactions
```bash
# Access another user's transaction
curl https://trade.zimaibank.com/api/transactions/victim-txn-id \
  -H "Authorization: Bearer $TOKEN"
```
**Expected**: 403 Forbidden or 404 Not Found

### Test Case 9: Race Condition on Deposit
```bash
# Submit same deposit twice simultaneously
for i in {1..2}; do
  curl -X POST https://trade.zimaibank.com/api/deposit \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"amount": 100, "reference": "DEP-RACE"}' &
done
```
**Expected**: Only one deposit credited (idempotency)

### Test Case 10: Model Input Manipulation
```bash
# Send adversarial input to trading model
curl -X POST https://trade.zimaibank.com/api/predict \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"features": [999999, -999999, NaN, Infinity]}'
```
**Expected**: Input validation rejects invalid values

## Reporting

### Severity Levels
- **Critical**: Direct financial loss, full account takeover, data breach
- **High**: Privilege escalation, authentication bypass
- **Medium**: Information disclosure, XSS, CSRF
- **Low**: Information leakage, minor configuration issues

### Report Template
```markdown
# Vulnerability Report

## Title
[Short description]

## Severity
[Critical/High/Medium/Low]

## Affected Component
[API endpoint, page, function]

## Description
[Detailed explanation of vulnerability]

## Steps to Reproduce
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Proof of Concept
```
[Code or screenshots]
```

## Impact
[What can attacker achieve?]

## Remediation
[How to fix]

## References
[CWE, OWASP links]
```

## Remediation Timeline

- **Critical**: Fix within 24 hours
- **High**: Fix within 7 days
- **Medium**: Fix within 30 days
- **Low**: Fix within 90 days

## Retest

After fixes deployed:
- [ ] Verify vulnerability is patched
- [ ] Check for regressions
- [ ] Update test suite with new test cases
- [ ] Update security documentation

## Continuous Testing

### Scheduled Scans
```yaml
# GitHub Actions / GitLab CI
name: Security Scan
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run OWASP ZAP
        run: |
          docker run -v $(pwd):/zap/wrk/:rw \
            owasp/zap2docker-stable \
            zap-baseline.py -t $APP_URL -r report.html
      - name: Upload Report
        uses: actions/upload-artifact@v2
        with:
          name: zap-report
          path: report.html
```

## Bug Bounty Program (Optional)

If offering public bug bounty:
- **Scope**: [Define in-scope assets]
- **Rewards**: Critical: $5000, High: $2000, Medium: $500, Low: $100
- **Rules**: No DoS, no social engineering, report responsibly
- **Platform**: HackerOne, Bugcrowd, or self-hosted

## Compliance

Penetration testing satisfies requirements for:
- PCI-DSS (quarterly scans)
- SOC2 (annual pen tests)
- ISO 27001 (periodic security assessments)

## Checklist

- [ ] Pen test scope defined and approved
- [ ] Testing team/vendor selected
- [ ] Pre-test backup created
- [ ] Pen test executed
- [ ] Vulnerabilities documented
- [ ] Remediation plan created
- [ ] Fixes deployed
- [ ] Retest completed
- [ ] Final report delivered
- [ ] Executive summary presented to stakeholders
