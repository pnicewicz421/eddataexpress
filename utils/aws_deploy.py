#!/usr/bin/env python3
"""
AWS Deployment Utility for ED Data Express Archive

This script helps configure and deploy the ED Data Express Archive to AWS:
- EC2 instance for hosting the web application
- S3 bucket for storing large media and data files
- RDS database (optional) for more advanced data querying

Usage:
    python aws_deploy.py --configure
    python aws_deploy.py --deploy
    python aws_deploy.py --update
"""

import os
import sys
import argparse
import json
import boto3
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aws_deploy.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("aws_deploy")

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
CONFIG_FILE = PROJECT_ROOT / "utils" / "aws_config.json"

def parse_arguments():
    """Parse command line arguments for deployment."""
    parser = argparse.ArgumentParser(description="AWS Deployment Utility for ED Data Express Archive")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--configure",
        action="store_true",
        help="Configure AWS deployment settings"
    )
    group.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy the application to AWS (initial deployment)"
    )
    group.add_argument(
        "--update",
        action="store_true",
        help="Update an existing deployment"
    )
    
    return parser.parse_args()

def load_config():
    """Load AWS configuration from file."""
    if not CONFIG_FILE.exists():
        logger.error(f"Configuration file not found: {CONFIG_FILE}")
        logger.info("Please run with --configure first")
        sys.exit(1)
    
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    """Save AWS configuration to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Configuration saved to {CONFIG_FILE}")

def configure():
    """Interactive configuration for AWS deployment."""
    config = {}
    
    # Load existing config if available
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    
    print("\n--- AWS Deployment Configuration ---\n")
    
    # AWS credentials and region
    print("\n-- AWS Credentials --")
    config["aws_region"] = input(f"AWS Region [default: us-east-1]: ") or "us-east-1"
    
    # EC2 Configuration
    print("\n-- EC2 Configuration --")
    config["ec2"] = config.get("ec2", {})
    config["ec2"]["instance_type"] = input(f"EC2 Instance Type [default: t2.medium]: ") or "t2.medium"
    config["ec2"]["key_name"] = input(f"EC2 Key Pair Name: ") or config["ec2"].get("key_name")
    
    # S3 Configuration
    print("\n-- S3 Configuration --")
    config["s3"] = config.get("s3", {})
    default_bucket = f"eddataexpress-archive-{config['aws_region']}"
    config["s3"]["bucket_name"] = input(f"S3 Bucket Name [default: {default_bucket}]: ") or default_bucket
    
    # Application Configuration
    print("\n-- Application Configuration --")
    config["app"] = config.get("app", {})
    config["app"]["name"] = input(f"Application Name [default: EDDataExpressArchive]: ") or "EDDataExpressArchive"
    config["app"]["domain"] = input(f"Domain Name (optional): ") or config["app"].get("domain", "")
    
    # Save configuration
    save_config(config)
    print("\nConfiguration complete! You can now run with --deploy to deploy to AWS.")

def deploy():
    """Deploy the application to AWS using Terraform."""
    config = load_config()
    
    logger.info("Starting deployment to AWS...")
    
    # Check if terraform is installed
    try:
        subprocess.run(["terraform", "--version"], check=True, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("Terraform not found. Please install Terraform first: https://www.terraform.io/downloads.html")
        sys.exit(1)
    
    # Create terraform directory if it doesn't exist
    terraform_dir = PROJECT_ROOT / "terraform"
    terraform_dir.mkdir(exist_ok=True)
    
    # Create main.tf
    main_tf = terraform_dir / "main.tf"
    with open(main_tf, "w") as f:
        f.write(f"""
provider "aws" {{
  region = "{config['aws_region']}"
}}

# S3 bucket for storing data and media files
resource "aws_s3_bucket" "eddataexpress_archive" {{
  bucket = "{config['s3']['bucket_name']}"
  
  tags = {{
    Name        = "{config['app']['name']}"
    Environment = "production"
  }}
}}

# Enable public read access for the bucket
resource "aws_s3_bucket_policy" "allow_public_read" {{
  bucket = aws_s3_bucket.eddataexpress_archive.id
  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Principal = "*"
        Action = [
          "s3:GetObject",
        ]
        Effect = "Allow"
        Resource = [
          "${{aws_s3_bucket.eddataexpress_archive.arn}}/*",
        ]
      }},
    ]
  }})
}}

# EC2 instance for the web application
resource "aws_instance" "web_server" {{
  ami                    = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2 AMI (adjust for your region)
  instance_type          = "{config['ec2']['instance_type']}"
  key_name               = "{config['ec2']['key_name']}"
  vpc_security_group_ids = [aws_security_group.web_sg.id]
  
  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              yum install -y python3 python3-pip git
              pip3 install --upgrade pip
              
              # Clone the repository
              git clone https://github.com/yourusername/eddataexpress.git /home/ec2-user/eddataexpress
              
              # Install dependencies
              cd /home/ec2-user/eddataexpress
              pip3 install -r requirements.txt
              
              # Configure and start the application
              python3 main.py --only-html &
              
              # Start the web application
              cd webapp
              nohup python3 app.py > /home/ec2-user/webapp.log 2>&1 &
              EOF
  
  tags = {{
    Name = "{config['app']['name']}-WebServer"
  }}
}}

# Security group for the web server
resource "aws_security_group" "web_sg" {{
  name        = "{config['app']['name']}-WebSG"
  description = "Security group for ED Data Express Archive web server"
  
  ingress {{
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH access"
  }}
  
  ingress {{
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP access"
  }}
  
  ingress {{
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Flask application"
  }}
  
  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }}
}}

output "web_server_public_ip" {{
  value = aws_instance.web_server.public_ip
}}

output "s3_bucket_name" {{
  value = aws_s3_bucket.eddataexpress_archive.bucket
}}
""")
    
    # Initialize and apply Terraform
    os.chdir(terraform_dir)
    
    try:
        logger.info("Initializing Terraform...")
        subprocess.run(["terraform", "init"], check=True)
        
        logger.info("Creating deployment plan...")
        subprocess.run(["terraform", "plan", "-out=eddataexpress.tfplan"], check=True)
        
        logger.info("Applying deployment plan...")
        subprocess.run(["terraform", "apply", "eddataexpress.tfplan"], check=True)
        
        logger.info("Deployment completed successfully!")
        
        # Get outputs
        result = subprocess.run(["terraform", "output", "-json"], check=True, capture_output=True, text=True)
        outputs = json.loads(result.stdout)
        
        print("\n--- Deployment Information ---")
        print(f"Web Server Public IP: {outputs['web_server_public_ip']['value']}")
        print(f"S3 Bucket Name: {outputs['s3_bucket_name']['value']}")
        print(f"Web Application URL: http://{outputs['web_server_public_ip']['value']}:5000")
        
    except subprocess.SubprocessError as e:
        logger.error(f"Deployment failed: {str(e)}")
        sys.exit(1)

def update_deployment():
    """Update an existing AWS deployment."""
    config = load_config()
    
    logger.info("Updating AWS deployment...")
    
    # Check if terraform directory exists
    terraform_dir = PROJECT_ROOT / "terraform"
    if not terraform_dir.exists() or not (terraform_dir / "terraform.tfstate").exists():
        logger.error("No existing deployment found. Please run --deploy first.")
        sys.exit(1)
    
    # Run terraform apply to update the deployment
    os.chdir(terraform_dir)
    
    try:
        logger.info("Creating update plan...")
        subprocess.run(["terraform", "plan", "-out=eddataexpress-update.tfplan"], check=True)
        
        logger.info("Applying update plan...")
        subprocess.run(["terraform", "apply", "eddataexpress-update.tfplan"], check=True)
        
        logger.info("Update completed successfully!")
        
    except subprocess.SubprocessError as e:
        logger.error(f"Update failed: {str(e)}")
        sys.exit(1)

def main():
    """Main execution function."""
    args = parse_arguments()
    
    if args.configure:
        configure()
    elif args.deploy:
        deploy()
    elif args.update:
        update_deployment()

if __name__ == "__main__":
    main() 