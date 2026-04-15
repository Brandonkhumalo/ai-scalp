variable "project_name" {
  description = "Prefix used for naming AWS resources."
  type        = string
  default     = "ai-scalp"
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "ec2_instance_type" {
  description = "EC2 instance size for the app server."
  type        = string
  default     = "t3.small"
}

variable "ec2_root_volume_size" {
  description = "Root EBS volume size (GB) for EC2."
  type        = number
  default     = 30
}

variable "key_pair_name" {
  description = "AWS EC2 key pair name to create."
  type        = string
}

variable "public_key_path" {
  description = "Local path to your SSH public key file (for example ~/.ssh/id_ed25519.pub)."
  type        = string
}

variable "ssh_allowed_cidr" {
  description = "CIDR that is allowed to SSH to EC2."
  type        = string
  default     = "0.0.0.0/0"
}

variable "web_allowed_cidr" {
  description = "CIDR allowed to access website and API on EC2 port 80."
  type        = string
  default     = "0.0.0.0/0"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Initial PostgreSQL database name."
  type        = string
  default     = "ai_scalp"
}

variable "db_username" {
  description = "Master username for PostgreSQL."
  type        = string
  default     = "ai_scalp_admin"
}

variable "db_password" {
  description = "Master password for PostgreSQL."
  type        = string
  sensitive   = true
}

variable "db_deletion_protection" {
  description = "Enable deletion protection on RDS."
  type        = bool
  default     = false
}
