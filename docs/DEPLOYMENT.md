# Production Deployment Guide

## Overview
This guide covers deploying ZimAI Trader to production infrastructure for bank-grade operations.

## Prerequisites
- Kubernetes cluster (EKS, GKE, or AKS)
- Container registry (ECR, GCR, ACR, or private registry)
- DNS management
- SSL/TLS certificates
- Load balancer / Ingress controller

## Architecture

```
[WAF / API Gateway] 
        ↓
[Load Balancer] 
        ↓
[Kubernetes Cluster]
├── Web Application (React/Vite)
├── Supabase (self-hosted or managed)
├── Edge Functions
└── Service Mesh (Istio/Linkerd)
```

## Step 1: Build Production Images

```bash
# Build optimized production image
docker build -t zimaitrader/web:${VERSION} \
  --build-arg NODE_ENV=production \
  --target production .

# Scan for vulnerabilities
trivy image zimaitrader/web:${VERSION}

# Sign image (Sigstore/Cosign)
cosign sign --key cosign.key zimaitrader/web:${VERSION}

# Push to registry
docker push zimaitrader/web:${VERSION}
```

## Step 2: Kubernetes Deployment

### Namespace Setup
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: zimaitrader-prod
  labels:
    istio-injection: enabled
```

### Deployment Configuration
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zimaitrader-web
  namespace: zimaitrader-prod
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: zimaitrader-web
  template:
    metadata:
      labels:
        app: zimaitrader-web
        version: v1
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: web
        image: zimaitrader/web:${VERSION}
        ports:
        - containerPort: 8080
          protocol: TCP
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        env:
        - name: VITE_SUPABASE_URL
          valueFrom:
            secretKeyRef:
              name: supabase-config
              key: url
        - name: VITE_SUPABASE_PUBLISHABLE_KEY
          valueFrom:
            secretKeyRef:
              name: supabase-config
              key: anon-key
```

### Service and Ingress
```yaml
apiVersion: v1
kind: Service
metadata:
  name: zimaitrader-web
  namespace: zimaitrader-prod
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: zimaitrader-web
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: zimaitrader-ingress
  namespace: zimaitrader-prod
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - trade.zimaibank.com
    secretName: zimaitrader-tls
  rules:
  - host: trade.zimaibank.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: zimaitrader-web
            port:
              number: 80
```

## Step 3: Secrets Management

```bash
# Create secrets from HSM/Vault
kubectl create secret generic supabase-config \
  --from-literal=url=${SUPABASE_URL} \
  --from-literal=anon-key=${SUPABASE_ANON_KEY} \
  -n zimaitrader-prod

# Seal secrets for GitOps
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml
```

## Step 4: Multi-Region Setup

```yaml
# Primary region deployment
apiVersion: v1
kind: ConfigMap
metadata:
  name: region-config
  namespace: zimaitrader-prod
data:
  region: "us-east-1"
  failover_region: "eu-west-1"
  replication_enabled: "true"
```

## Step 5: Monitoring & Observability

```yaml
# ServiceMonitor for Prometheus
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: zimaitrader-metrics
  namespace: zimaitrader-prod
spec:
  selector:
    matchLabels:
      app: zimaitrader-web
  endpoints:
  - port: metrics
    interval: 30s
```

## Step 6: Disaster Recovery

### Backup Schedule
```yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: zimaitrader-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"
  template:
    includedNamespaces:
    - zimaitrader-prod
    ttl: 720h0m0s
```

### Failover Procedure
1. Detect primary region failure via health checks
2. Update DNS to point to DR region
3. Activate standby Supabase instance
4. Verify data replication lag < 5 minutes
5. Enable traffic to DR cluster

## Step 7: CI/CD Pipeline

```yaml
# GitLab CI / GitHub Actions example
stages:
  - build
  - test
  - scan
  - deploy

build:
  stage: build
  script:
    - docker build -t $IMAGE_TAG .
    - docker push $IMAGE_TAG

security-scan:
  stage: scan
  script:
    - trivy image $IMAGE_TAG
    - snyk test --docker $IMAGE_TAG

deploy-production:
  stage: deploy
  script:
    - kubectl set image deployment/zimaitrader-web web=$IMAGE_TAG -n zimaitrader-prod
    - kubectl rollout status deployment/zimaitrader-web -n zimaitrader-prod
  when: manual
  only:
    - main
```

## Step 8: Network Security

### Network Policies
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: zimaitrader-netpol
  namespace: zimaitrader-prod
spec:
  podSelector:
    matchLabels:
      app: zimaitrader-web
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 5432  # Supabase DB
    - protocol: TCP
      port: 443   # External APIs
```

## Step 9: Compliance & Audit

- Enable audit logging on Kubernetes API server
- Configure pod security policies
- Implement mTLS between services (service mesh)
- Regular vulnerability scanning (daily)
- Immutable infrastructure (no SSH access)

## Step 10: Production Checklist

- [ ] Multi-AZ deployment configured
- [ ] Auto-scaling enabled (HPA)
- [ ] Backup and restore tested
- [ ] DR failover drill completed
- [ ] Security scanning in CI/CD
- [ ] Network policies enforced
- [ ] Secrets from HSM/Vault
- [ ] mTLS enabled
- [ ] WAF configured
- [ ] Rate limiting active
- [ ] Monitoring and alerting configured
- [ ] Incident response runbooks ready
- [ ] On-call rotation established

## Support

For deployment issues, contact DevOps team or refer to internal runbooks.
