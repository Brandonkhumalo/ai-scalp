output "ec2_instance_id" {
  description = "EC2 instance ID for the app host."
  value       = aws_instance.app.id
}

output "ec2_elastic_ip" {
  description = "Elastic IP for website access (and optional direct /api access)."
  value       = aws_eip.app.public_ip
}

output "website_url" {
  description = "Website URL via EC2 Elastic IP."
  value       = "http://${aws_eip.app.public_ip}"
}

output "api_url" {
  description = "API URL via EC2 Elastic IP."
  value       = "http://${aws_eip.app.public_ip}/api"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint host."
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS PostgreSQL port."
  value       = aws_db_instance.postgres.port
}

output "database_url_template" {
  description = "Copy this and replace <PASSWORD> with your DB password in backend/.env."
  value       = "postgresql://${var.db_username}:<PASSWORD>@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${var.db_name}"
}
