#!/bin/bash
# Scintilla Deployment Script
# Supports multiple deployment methods: Terraform, Docker, and AWS native services

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Default values
ENVIRONMENT="development"
AWS_REGION="us-east-1"
SKIP_BUILD=false
SKIP_TESTS=false
DRY_RUN=false
FORCE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Scintilla Deployment Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -e, --environment ENV       Deployment environment (development|staging|production)
    -r, --region REGION         AWS region (default: us-east-1)
    -s, --skip-build           Skip building frontend
    -t, --skip-tests           Skip running tests
    -d, --dry-run              Show what would be deployed without executing
    -f, --force                Force deployment even with warnings
    -h, --help                 Show this help message

EXAMPLES:
    # Deploy to development
    $0 -e development

    # Deploy to production in us-west-2
    $0 -e production -r us-west-2

    # Dry run for staging environment
    $0 -e staging --dry-run

ENVIRONMENTS:
    development - Single instance, minimal resources
    staging     - Multi-instance, moderate resources
    production  - High availability, full resources

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -s|--skip-build)
            SKIP_BUILD=true
            shift
            ;;
        -t|--skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    log_error "Must be one of: development, staging, production"
    exit 1
fi

# AWS deployment using Terraform (single method)

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_tools=()
    
    # Check common tools
    command -v git >/dev/null 2>&1 || missing_tools+=("git")
    command -v python3 >/dev/null 2>&1 || missing_tools+=("python3")
    command -v node >/dev/null 2>&1 || missing_tools+=("node")
    command -v npm >/dev/null 2>&1 || missing_tools+=("npm")
    
    # Check AWS deployment tools
    command -v terraform >/dev/null 2>&1 || missing_tools+=("terraform")
    command -v aws >/dev/null 2>&1 || missing_tools+=("aws-cli")
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error "Please install missing tools and try again"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_error "AWS credentials not configured or invalid"
        log_error "Please configure AWS credentials and try again"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Run tests
run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log_warning "Skipping tests (--skip-tests flag)"
        return
    fi
    
    log_info "Running tests..."
    cd "$PROJECT_ROOT"
    
    # Python tests
    if [[ -f "tests/run_tests.py" ]]; then
        python3 tests/run_tests.py
    else
        log_warning "No test runner found, skipping Python tests"
    fi
    
    # Frontend tests (if configured)
    if [[ -f "web/package.json" ]] && grep -q '"test"' web/package.json; then
        cd web
        npm test -- --watchAll=false
        cd "$PROJECT_ROOT"
    else
        log_warning "No frontend tests configured"
    fi
    
    log_success "Tests completed successfully"
}

# Build application
build_application() {
    if [[ "$SKIP_BUILD" == "true" ]]; then
        log_warning "Skipping build (--skip-build flag)"
        return
    fi
    
    log_info "Building application..."
    cd "$PROJECT_ROOT"
    
    # Build frontend
    log_info "Building frontend..."
    cd web
    npm ci  # Install all dependencies including devDependencies (needed for vite build)
    npm run build
    cd "$PROJECT_ROOT"
    
    # No Docker build needed for EC2 deployment
    
    log_success "Build completed successfully"
}

# Deploy to AWS using Terraform
deploy_aws() {
    log_info "Deploying using Terraform..."
    cd "$SCRIPT_DIR/terraform"
    
    # Initialize Terraform
    terraform init
    
    # Create workspace for environment if it doesn't exist
    terraform workspace select "$ENVIRONMENT" 2>/dev/null || terraform workspace new "$ENVIRONMENT"
    
    # Plan deployment
    log_info "Planning Terraform deployment..."
    if [[ -f "terraform.tfvars" ]]; then
        terraform plan -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION"
    else
        log_warning "No terraform.tfvars found, using defaults"
        terraform plan -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION"
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Dry run completed. Deployment plan shown above."
        return
    fi
    
    # Apply deployment
    if [[ "$FORCE" == "true" ]]; then
        terraform apply -auto-approve -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION"
    else
        terraform apply -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION"
    fi
    
    # Show outputs
    log_success "AWS deployment completed!"
    log_info "Deployment outputs:"
    terraform output
}

# Main deployment function
main() {
    log_info "Starting Scintilla AWS deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Region: $AWS_REGION"
    log_info "Timestamp: $TIMESTAMP"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "DRY RUN MODE - No actual deployment will occur"
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Run tests
    run_tests
    
    # Build application
    build_application
    
    # Deploy to AWS using Terraform
    deploy_aws
    
    log_success "Deployment completed successfully!"
    
    # Show next steps
    log_info "Next steps:"
    log_info "1. Configure environment variables (API keys, OAuth credentials)"
    log_info "2. Test the application health endpoint"
    log_info "3. Configure monitoring and alerting"
    log_info "4. Set up SSL certificate (if using custom domain)"
}

# Run main function
main "$@" 