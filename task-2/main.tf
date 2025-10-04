# Get your public IP (for SSH)
data "http" "myip" {
  url = "https://checkip.amazonaws.com/"
}

locals {
  my_ip_cidr = trimspace(data.http.myip.response_body) != "" ? "${trimspace(data.http.myip.response_body)}/32" : "0.0.0.0/0"
}

# Find latest Amazon Linux 2 AMI (x86_64)
data "aws_ami" "amzn2" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
  filter {
    name   = "state"
    values = ["available"]
  }
}

# Generate SSH keypair
resource "tls_private_key" "ssh" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "local_file" "ssh_private_key_pem" {
  content              = tls_private_key.ssh.private_key_pem
  filename             = "${path.module}/ec2_key.pem"
  file_permission      = "0400"
  directory_permission = "0700"
}

resource "aws_key_pair" "generated" {
  key_name   = "tf-ec2-key"
  public_key = tls_private_key.ssh.public_key_openssh
}

# Security Group for the EC2
resource "aws_security_group" "web_sg" {
  name        = "tf-web-sg"
  description = "Allow SSH from my IP and HTTP from anywhere"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from my IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [local.my_ip_cidr]
  }

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "tf-web-sg"
  }
}

# Default VPC / Subnet
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# EC2 instance (t2.micro)
resource "aws_instance" "web" {
  ami                    = data.aws_ami.amzn2.id
  instance_type          = "t2.micro"
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.web_sg.id]
  key_name               = aws_key_pair.generated.key_name
  associate_public_ip_address = true

  user_data = <<-EOF
    #!/bin/bash
    set -euxo pipefail
    yum update -y
    yum install -y httpd
    systemctl enable httpd
    systemctl start httpd
    echo "Hello, DevOps!" > /var/www/html/index.html
  EOF

  tags = {
    Name = "tf-web-hello"
  }
}

