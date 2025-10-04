1) VPC setup for a simple web application

High-level design
	•	VPC CIDR: 10.0.0.0/16
	•	AZs: Use at least two Availability Zones (e.g., us-east-1a, us-east-1b) for resilience.
	•	Subnets:
	•	Public subnets (x2): For internet-facing components like an Application Load Balancer (ALB) and NAT Gateways.
	•	10.0.1.0/24 (AZ-a), 10.0.2.0/24 (AZ-b)
	•	Private app subnets (x2): For EC2 app instances (no public IPs).
	•	10.0.11.0/24 (AZ-a), 10.0.12.0/24 (AZ-b)
	•	(Optional) Private data subnets (x2): For databases, caches.
	•	10.0.21.0/24 (AZ-a), 10.0.22.0/24 (AZ-b)
	•	Internet Gateway (IGW): Required for inbound/outbound internet to public subnets.
	•	NAT Gateways: One per public subnet to provide outbound internet from private subnets.
	•	Route Tables:
	•	Public RT: Default route to the IGW. Associated with public subnets.
	•	Private App RT(s): Default route to the NAT Gateway in the same AZ. Associated with private app subnets.
	•	Private Data RT(s): Typically no default internet route; add VPC endpoints instead for AWS services.

Concrete routing

Public route table
	•	10.0.0.0/16 → local
	•	0.0.0.0/0 → IGW
	•	::/0 → Egress-only IGW (if using IPv6)

Private app route table (per AZ)
	•	10.0.0.0/16 → local
	•	0.0.0.0/0 → NAT Gateway in same AZ
	•	(Optional) S3/DynamoDB gateway endpoints so traffic stays on AWS network, not internet.

Private data route table (strict)
	•	10.0.0.0/16 → local
	•	No 0.0.0.0/0
	•	Add VPC endpoints (S3, CloudWatch Logs, ECR, SSM) as needed.

Subnet settings
	•	Public subnets: Auto-assign public IPv4 enabled (for ALB/NAT, not for instances unless needed).
	•	Private subnets: Auto-assign public IPv4 disabled. Instances have only private IPs.

Security Groups (stateful)

Create a few small, focused SGs:
	•	ALB-SG (public):
	•	Inbound: TCP 80/443 from 0.0.0.0/0 (or restrict by IP ranges if you know the clients).
	•	Outbound: 0.0.0.0/0 (default), or restrict to app ports/security groups.
	•	App-SG (private EC2):
	•	Inbound: TCP 80/443 from ALB-SG (use SG reference, not CIDR).
Add admin ports only via SSM (recommended), not SSH from the internet.
	•	Outbound: Allow only what’s needed:
	•	TCP 443 to 0.0.0.0/0 (for OS/package updates via NAT), or further restrict with prefix lists / endpoints.
	•	DB-SG (optional data tier):
	•	Inbound: DB port (e.g., 5432) from App-SG only.
	•	Outbound: Default or restrict to required services.

Network ACLs (stateless)
	•	Keep default NACLs (allow all in/out) initially; NACL micro-segmentation is advanced and easy to misconfigure.
	•	If you do use NACLs, mirror ephemeral port ranges (1024-65535) appropriately for return traffic.

Useful endpoints (keep traffic off the internet)

Add VPC endpoints:
	•	Gateway endpoints: S3, DynamoDB (route-table-based).
	•	Interface endpoints: CloudWatch Logs, ECR API/DKR, SSM/SSM Messages, EC2 Messages, STS.
This lets private instances reach AWS services without public internet.

Optional
	•	AWS WAF on the ALB.
	•	ACM certificate for HTTPS on the ALB.
	•	SSM Session Manager for shell access (no inbound SSH at all).
	•	VPC Flow Logs + ALB/NLB access logs to S3/CloudWatch.
	•	IMDSv2 enforced on EC2, disable public metadata hop limit issues.
	•	Auto Scaling Group for app instances across the two private subnets.

⸻

2) Securing communication between EC2 and the internet

Inbound (from internet → your workloads)
	1.	Terminate TLS at the ALB
	•	Use ACM for TLS certs.
	•	ALB listens on 443 (and optionally 80 for redirect to 443).
	2.	Restrict entry to the ALB only
	•	Public subnets host the ALB.
	•	ALB-SG allows 443 from the world (or a narrowed CIDR).
	3.	Lock down app instances
	•	No public IPs on EC2.
	•	App-SG inbound only from ALB-SG on app port (e.g., 80/443 or your custom port).
	•	No SSH from the internet; use SSM Session Manager instead.
	4.	Web-layer protections
	•	Add AWS WAF rules (rate limiting, geo/IP allow/deny, managed rule groups).
	•	Optionally add a CloudFront layer in front of ALB for extra shielding and caching.

Outbound (your instances → internet)
	1.	Use NAT Gateways
	•	Private instances reach the internet for updates/3rd-party APIs via NAT in public subnets.
	•	One NAT per AZ to avoid cross-AZ data charges and single-AZ failure.
	2.	Least-privilege egress
	•	In App-SG outbound, avoid 0.0.0.0/0 where possible.
	•	Prefer port-restricted rules (443 only).
	•	For well-known services (S3, DynamoDB, ECR, CloudWatch, SSM), use VPC endpoints so traffic never hits the public internet.
	3.	DNS and TLS
	•	Use Route 53 resolver (VPC-provided).
	•	Enforce HTTPS for all external calls; verify certs. Consider certificate pinning for critical dependencies.
	4.	IPv6
	•	If you enable IPv6, put an egress-only IGW for outbound-only IPv6 from private subnets (no inbound). Update SGs accordingly.
	5.	Monitoring & controls
	•	VPC Flow Logs: observe unusual egress.
	•	GuardDuty: detects anomalous traffic.
	•	AWS Config: rules for SGs (e.g., no 0.0.0.0/0 on sensitive ports).
	•	CloudWatch alarms on NAT/Data transfer spikes.

Admin & maintenance access (secure)
	•	No bastion needed if you use SSM Session Manager:
	•	Attach AmazonSSMManagedInstanceCore to instances.
	•	Open no inbound admin ports at all.
	•	For patching/builds: pull from S3/ECR over endpoints; only allow 443 egress when needed.
	•	Rotate instance roles and secrets with IAM roles + Parameter Store/Secrets Manager (never hard-code keys).