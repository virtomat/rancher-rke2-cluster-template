# Load Balancer Operating Status ERROR - Security Group Issue

## Problem Statement

When creating a Kubernetes (RKE2) cluster using this Helm chart, a load balancer is automatically provisioned by OpenStack Octavia for the NGINX ingress controller. However, the load balancer shows:

```
Provisioning Status: ACTIVE
Operating Status: ERROR
```

All pool members also show `ERROR` status, preventing the load balancer from functioning.

## Root Cause

The issue occurs due to **security group isolation** between the Octavia amphora (load balancer instance) and the Kubernetes worker nodes:

1. **Octavia amphora** gets created with its own per-load-balancer security group (e.g., `lb-846bd1e4-5196-4d99-9cee-486936d444ff`)
2. **Kubernetes worker nodes** use the project's **"default" security group**
3. The default security group only allows ingress traffic **from itself** (same security group members)
4. The amphora has a **different security group**, so all health checks and traffic forwarding attempts are **blocked by the firewall**

### Why This Happens

When OpenStack creates VMs without explicit security group assignment, they get the project's "default" security group, which typically has restrictive rules:
- **Ingress**: Only from same security group
- **Egress**: All traffic allowed

This works fine for VM-to-VM communication within the same group, but breaks when external components (like Octavia amphorae) need to reach these VMs.

## Technical Details

### Components Involved

| Component | IP Address | Security Group | Ports |
|-----------|------------|----------------|-------|
| Octavia Amphora | 10.0.17.218 | `lb-<uuid>` (per-LB, dynamic) | N/A |
| K8s Worker Node | 10.0.17.117 | `default` (project default) | 30690, 32169 (NodePorts) |
| Load Balancer VIP | 10.0.17.53 | N/A | 80, 443 |

### Network Architecture

```
[User] ’ [LB VIP: 10.0.17.53] ’ [Amphora: 10.0.17.218] ’ [Worker: 10.0.17.117:30690/32169]
                                          “
                                   Health Checks
                                   (TCP to NodePorts)
```

The amphora needs to:
1. Send TCP health checks to backend members
2. Forward incoming traffic to backend members

Both operations require **ingress access** to the worker nodes on the NodePort range.

### Security Group Analysis

**Amphora Security Group (`lb-<uuid>`):**
```bash
$ openstack security group rule list 69715f59-38f9-4759-9a06-e2f17a78ee98
# Allows egress to anywhere (0.0.0.0/0)
# Allows ingress on ports 80, 443, 1025 for client traffic
```

**Worker Node Security Group (`default`):**
```bash
$ openstack security group rule list 4e6d1d22-043d-4bca-9e37-6bbb315b2dc5 --ingress
# Only allows ingress from same security group (self-reference)
# BLOCKS traffic from amphora security group
```

## Diagnostic Commands

### 1. List Load Balancers and Check Status

```bash
source ~/.openstack/admin-openrc.sh
openstack loadbalancer list
```

Look for `operating_status: ERROR`

### 2. Get Detailed Load Balancer Information

```bash
LB_ID="846bd1e4-5196-4d99-9cee-486936d444ff"  # Replace with your LB ID
openstack loadbalancer show $LB_ID
```

Note the `pools` and `vip_address`.

### 3. Check Pool and Member Status

```bash
# List pools
openstack loadbalancer pool list

# Check specific pool
POOL_ID="4ca7f602-6a57-46fb-b33d-41bb029b77de"  # Replace with your pool ID
openstack loadbalancer pool show $POOL_ID

# Check pool members
openstack loadbalancer member list $POOL_ID
openstack loadbalancer member show $POOL_ID <MEMBER_ID>
```

Look for `operating_status: ERROR` on members.

### 4. Identify the Amphora Instance

```bash
openstack loadbalancer amphora list
```

Note the `lb_network_ip` and `ha_ip` (VIP).

### 5. Find Backend Servers and Their Security Groups

```bash
# Find the backend server by IP
BACKEND_IP="10.0.17.117"  # From pool member
openstack server list --all-projects | grep $BACKEND_IP

# Get server details
SERVER_ID="a0a95d9b-5fd2-4c03-b336-7f9f63a4b06d"  # From previous command
openstack server show $SERVER_ID

# Get port and security group
openstack port list --server $SERVER_ID
PORT_ID="71e43abe-5e50-495d-b4da-79b921df6450"  # From previous command
openstack port show $PORT_ID -c security_group_ids -f value
```

### 6. Check Security Group Rules

```bash
# Check the default security group
SG_ID="4e6d1d22-043d-4bca-9e37-6bbb315b2dc5"  # From port show
openstack security group show $SG_ID

# List ingress rules
openstack security group rule list $SG_ID --ingress

# Check if it allows traffic from the amphora's subnet
# Look for rules with remote_ip_prefix: 10.0.17.0/24
```

### 7. Check Octavia Logs (Optional)

```bash
# SSH to control plane node
ssh virt-epoxy-1

# Find Octavia container
lxc-ls -f | grep octavia

# Check health manager logs
lxc-attach -n epoxy-dev-1-octavia-server-container-3aa720c0 -- \
  journalctl -u octavia-health-manager -n 100 --no-pager

# Check worker logs for errors
lxc-attach -n epoxy-dev-1-octavia-server-container-3aa720c0 -- \
  journalctl -u octavia-worker --since '2025-11-25 12:00' --no-pager
```

## Solution

### The Fix: Allow Subnet Traffic

Add a security group rule to allow all TCP traffic from the load balancer subnet (`10.0.17.0/24`) to the worker nodes.

**Why this approach:**
-  Works for any future load balancer (no per-LB intervention needed)
-  Works for any NodePort allocation (ports are dynamic)
-  No changes needed when creating new clusters
-  Still secure (only project resources in that subnet have access)

### Apply the Fix

**Important:** Replace the security group ID with your project's default security group ID.

```bash
# Source admin credentials
source ~/.openstack/admin-openrc.sh

# Identify the user's project
PROJECT_NAME="John.Doe-ws"  # Or use project ID directly
PROJECT_ID=$(openstack project show $PROJECT_NAME -c id -f value)

# Find the default security group for the project
SG_ID=$(openstack security group list --project $PROJECT_ID | grep "default" | awk '{print $2}')

# Verify you have the right security group
openstack security group show $SG_ID

# Add the rule to allow TCP traffic from the subnet
openstack security group rule create \
  --ingress \
  --protocol tcp \
  --remote-ip 10.0.17.0/24 \
  $SG_ID
```

**Single command if you know the security group ID:**
```bash
openstack security group rule create --ingress --protocol tcp --remote-ip 10.0.17.0/24 4e6d1d22-043d-4bca-9e37-6bbb315b2dc5
```

### Trigger Load Balancer Failover

After adding the security group rule, trigger a failover to recreate the amphora and apply the new rules:

```bash
LB_ID="846bd1e4-5196-4d99-9cee-486936d444ff"  # Replace with your LB ID
openstack loadbalancer failover $LB_ID
```

### Verify the Fix

Monitor the failover process:

```bash
# Watch amphora status (new one will boot, old one will be deleted)
watch -n 5 'openstack loadbalancer amphora list'

# Check load balancer status (wait for ACTIVE/ONLINE)
openstack loadbalancer show $LB_ID -c provisioning_status -c operating_status

# Verify pools are healthy
openstack loadbalancer pool list
openstack loadbalancer pool show <POOL_ID> -c operating_status

# Verify members are healthy
openstack loadbalancer member list <POOL_ID>
openstack loadbalancer member show <POOL_ID> <MEMBER_ID> -c operating_status
```

**Expected results after failover completes (~2-3 minutes):**
- Load Balancer: `provisioning_status: ACTIVE`, `operating_status: ONLINE`
- Pools: `operating_status: ONLINE`
- Members: `operating_status: ONLINE`

## Alternative Solutions

### Option 1: Dedicated Security Group for Workers

Instead of modifying the default security group, create a dedicated security group for Kubernetes workers:

```bash
# Create a dedicated security group
openstack security group create k8s-worker \
  --description "Security group for Kubernetes worker nodes" \
  --project $PROJECT_ID

# Add the subnet rule
openstack security group rule create \
  --ingress \
  --protocol tcp \
  --remote-ip 10.0.17.0/24 \
  k8s-worker

# Add any other necessary rules (SSH, etc.)
openstack security group rule create \
  --ingress \
  --protocol tcp \
  --dst-port 22 \
  --remote-ip 0.0.0.0/0 \
  k8s-worker
```

Then modify the cluster creation to assign this security group to worker nodes.

### Option 2: Allow Specific Ports Only

If you prefer more restrictive rules, allow only the NodePort range:

```bash
# Allow NodePort range (30000-32767) from subnet
openstack security group rule create \
  --ingress \
  --protocol tcp \
  --dst-port 30000:32767 \
  --remote-ip 10.0.17.0/24 \
  $SG_ID
```

**Note:** This is more restrictive but still requires manual intervention if you use custom port ranges.

## Context and Background

### Why Admin vs. User Behaves Differently

If testing as admin worked but user deployments failed, it's likely due to:

1. **Different default security group rules** - Admin project may have more permissive defaults
2. **Pre-existing rules** - Admin project may have been manually configured previously
3. **Different network architecture** - Admin might be using shared/provider networks with different security models

### Kubernetes NodePort Services

Kubernetes exposes services using NodePorts (default range: 30000-32767). The NGINX ingress controller uses NodePort services:
- Port 30690 ’ HTTP (80)
- Port 32169 ’ HTTPS (443)

These ports are dynamically allocated and **change with each cluster deployment**, making port-specific rules impractical.

### Octavia Amphora Security Groups

OpenStack Octavia creates a **unique security group per load balancer** with naming pattern `lb-<uuid>`. This design:
- Isolates each load balancer's traffic
- Allows fine-grained per-LB rules
- Makes it difficult to write rules that reference "all amphorae"

This is why **subnet-based rules** are the recommended approach for Kubernetes integration.

### Network Isolation

The subnet `10.0.17.0/24` (`local-net`) is:
- **Project-specific** - Only accessible by resources in the user's project
- **Private** - Not routable from external networks
- **Trusted** - All resources (VMs, amphorae) are created by the same project owner

This makes subnet-based security rules safe for intra-project communication.

## Prevention

To prevent this issue in future cluster deployments:

1. **Apply the fix once** using the commands in the Solution section
2. **Document in cluster creation guides** that users need this security group rule
3. **Automate in Terraform/Ansible** if using infrastructure-as-code
4. **Create cluster templates** with pre-configured security groups
5. **Use dedicated security groups** for Kubernetes workers (Option 1 above)

## Related Issues

- Octavia health checks timing out
- Load balancer stuck in `PENDING_UPDATE` state
- Pool members showing `NO_MONITOR` or `OFFLINE` status
- Kubernetes services of type `LoadBalancer` not accessible

All of these may be related to security group misconfigurations preventing amphora-to-backend communication.

## References

- [OpenStack Octavia Documentation](https://docs.openstack.org/octavia/latest/)
- [Kubernetes NodePort Service](https://kubernetes.io/docs/concepts/services-networking/service/#type-nodeport)
- [OpenStack Security Groups](https://docs.openstack.org/nova/latest/admin/security-groups.html)
