# Helm Deployment Guide

This guide explains how to deploy route-llm-gateway on Kubernetes using Helm.

## Prerequisites

- Kubernetes cluster (1.19+)
- `kubectl` configured to access your cluster
- `helm` 3.x installed
- Container registry access (Docker Hub, GHCR, etc.)
- PostgreSQL and Redis instances (or use external services)

## Quick Start

1. **Build and push Docker images:**
   ```bash
   # Build images
   docker build -f deploy/docker/backend.Dockerfile -t your-registry/route-llm-gateway-backend:0.5.0 .
   docker build -f deploy/docker/frontend.Dockerfile -t your-registry/route-llm-gateway-frontend:0.5.0 .
   
   # Push to registry
   docker push your-registry/route-llm-gateway-backend:0.5.0
   docker push your-registry/route-llm-gateway-frontend:0.5.0
   ```

2. **Create Kubernetes secrets:**
   ```bash
   kubectl create secret generic route-llm-gateway-secrets \
     --from-literal=openai-api-key=sk-... \
     --from-literal=anthropic-api-key=sk-ant-...
   ```

3. **Customize values:**
   ```bash
   cp deploy/helm/route-llm-gateway/values.yaml my-values.yaml
   # Edit my-values.yaml with your image repositories and configuration
   ```

4. **Install the chart:**
   ```bash
   helm install route-llm-gateway ./deploy/helm/route-llm-gateway \
     --values my-values.yaml \
     --namespace route-llm-gateway \
     --create-namespace
   ```

5. **Verify deployment:**
   ```bash
   kubectl get pods -n route-llm-gateway
   kubectl get services -n route-llm-gateway
   ```

## Configuration

### Image Configuration

Edit `values.yaml` or create a custom values file:

```yaml
image:
  backend:
    repository: your-registry/route-llm-gateway-backend
    tag: "0.5.0"
    pullPolicy: Always
  
  frontend:
    repository: your-registry/route-llm-gateway-frontend
    tag: "0.5.0"
    pullPolicy: Always
  
  worker:
    repository: your-registry/route-llm-gateway-backend
    tag: "0.5.0"
    pullPolicy: Always
```

### Environment Variables

Configure database and Redis URLs:

```yaml
env:
  databaseUrl: "postgresql+psycopg2://user:pass@postgres-service:5432/route_llm"
  redisUrl: "redis://redis-service:6379/0"
  openaiDefaultModel: "gpt-4o-mini"
  anthropicDefaultModel: "claude-3-5-haiku-20241022"
```

### Secrets

Create Kubernetes secrets for API keys:

```bash
kubectl create secret generic route-llm-gateway-secrets \
  --from-literal=openai-api-key=sk-... \
  --from-literal=anthropic-api-key=sk-ant-... \
  --from-literal=deepseek-api-key=sk-... \
  --from-literal=gemini-api-key=...
```

Then reference in values.yaml:

```yaml
secrets:
  openaiApiKey: "route-llm-gateway-secrets"
  anthropicApiKey: "route-llm-gateway-secrets"
  # ... etc
```

**Note**: The chart expects secrets to be created separately. Update the secret template or use external secret management.

### Service Configuration

```yaml
service:
  backend:
    type: ClusterIP  # Internal only
    port: 8000
  
  frontend:
    type: LoadBalancer  # Or NodePort, ClusterIP
    port: 80
```

### Ingress

Enable ingress for frontend:

```yaml
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: route-llm-gateway.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: route-llm-gateway-tls
      hosts:
        - route-llm-gateway.example.com
```

### Resource Limits

Adjust resource requests and limits:

```yaml
resources:
  backend:
    requests:
      memory: "512Mi"
      cpu: "200m"
    limits:
      memory: "1Gi"
      cpu: "1000m"
```

### Replica Counts

Scale services:

```yaml
replicaCount:
  backend: 2
  worker: 3
  frontend: 2
```

## Deployment Steps

### 1. Prepare Dependencies

**PostgreSQL:**
- Use managed service (AWS RDS, Google Cloud SQL, etc.)
- Or deploy using PostgreSQL Helm chart:
  ```bash
  helm repo add bitnami https://charts.bitnami.com/bitnami
  helm install postgres bitnami/postgresql
  ```

**Redis:**
- Use managed service (AWS ElastiCache, Google Cloud Memorystore, etc.)
- Or deploy using Redis Helm chart:
  ```bash
  helm install redis bitnami/redis
  ```

### 2. Install the Chart

```bash
helm install route-llm-gateway ./deploy/helm/route-llm-gateway \
  --values my-values.yaml \
  --namespace route-llm-gateway \
  --create-namespace
```

### 3. Access the Application

**Frontend:**
- If using LoadBalancer: `kubectl get svc -n route-llm-gateway` to get external IP
- If using Ingress: Access via configured hostname
- If using NodePort: `kubectl get svc -n route-llm-gateway` to get node port

**Backend API:**
- Port-forward for testing:
  ```bash
  kubectl port-forward -n route-llm-gateway svc/route-llm-gateway-backend 8000:8000
  ```
- Then access: http://localhost:8000/docs

## Upgrading

```bash
helm upgrade route-llm-gateway ./deploy/helm/route-llm-gateway \
  --values my-values.yaml \
  --namespace route-llm-gateway
```

## Uninstalling

```bash
helm uninstall route-llm-gateway --namespace route-llm-gateway
```

## Troubleshooting

### Pods not starting
```bash
kubectl describe pod <pod-name> -n route-llm-gateway
kubectl logs <pod-name> -n route-llm-gateway
```

### Database connection issues
- Verify DATABASE_URL is correct
- Check PostgreSQL service is accessible from pods
- Test connection: `kubectl exec -it <backend-pod> -- python -c "from app.db import get_db; ..."`

### Worker not processing jobs
- Check worker logs: `kubectl logs -f <worker-pod> -n route-llm-gateway`
- Verify Redis connection: Check REDIS_URL and Redis service accessibility

### Frontend can't reach backend
- Verify backend service is running: `kubectl get svc -n route-llm-gateway`
- Check CORS configuration in backend
- Ensure frontend is configured with correct backend URL

## Production Considerations

1. **Use managed databases**: Prefer managed PostgreSQL and Redis services
2. **Enable TLS**: Configure ingress with TLS certificates
3. **Resource limits**: Set appropriate resource requests/limits
4. **Monitoring**: Integrate with Prometheus/Grafana
5. **Logging**: Use centralized logging (ELK, Loki, etc.)
6. **Backups**: Set up database backups
7. **Secrets management**: Use external secret management (Sealed Secrets, Vault, etc.)
8. **High availability**: Deploy multiple replicas across nodes

