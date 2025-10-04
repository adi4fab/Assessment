output "instance_id" {
  value = aws_instance.web.id
}

output "public_ip" {
  value = aws_instance.web.public_ip
}

output "public_dns" {
  value = aws_instance.web.public_dns
}

output "ssh_command" {
  value = "ssh -i ./ec2_key.pem ec2-user@${aws_instance.web.public_dns}"
}

output "test_url" {
  value = "http://${aws_instance.web.public_dns}"
}